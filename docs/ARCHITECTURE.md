# Architecture — ACME Salary Management

## 1. Overview

HR-centric salary management for 10,000 employees, built as a **server-rendered Django app with HTMX interactivity + DRF API layer**, SQLite for simplicity, Celery for payroll exports, and MinIO/S3 for receipt storage (filesystem fallback).

```
Browser (HTMX)
   │
   ├─► Django Views (UI) ── login_required + Role checks ──► Templates (Tailwind + HTMX)
   │        │  HTMX partials: employee_table, reimbursement_row, payroll_table, export_status
   │        └─► ORM (select_related/prefetch, indexes, annotated aggregates)
   │
   ├─► DRF API (/api/*) ── SessionAuth + IsAuthenticated + IsHR / IsOwnerOrHR ──► ViewSets (mixins)
   │        │  ListModelMixin, RetrieveModelMixin, CreateModelMixin, UpdateModelMixin, DestroyModelMixin
   │        └─► Serializers (hide salary for non-HR viewing others)
   │
   └─► Celery (eager in dev, Redis in prod) ──► PayrollExport tasks (Excel/PDF)
                           └─► MinIO (boto3) or MEDIA_ROOT fallback

DB: SQLite (WAL, 20s timeout, indexed on employee_id, country, job_title, department)
```

## 2. Project Layout

```
config/                # settings, urls, wsgi/asgi, celery, api_urls
apps/
  accounts/            # User (role HR/EMPLOYEE), auth views, permissions
  employees/           # Department, Employee, SalaryStructure, TaxBracket, seed command, UI + API
  reimbursements/      # Reimbursement (status machine), UI + API, upload_to employee_id/
  payroll/             # PayrollExport, tasks (get_payroll_rows + generate_export), UI + API
templates/
  base.html, dashboard.html, accounts/login.html,
  employees/*, reimbursements/*, payroll/*
static/                # Tailwind CDN (no build step for assessment speed)
docs/                  # REQUIREMENTS.md, ARCHITECTURE.md
manage.py, pyproject.toml (uv), db.sqlite3, media/
```

**Separation:** `views_ui.py` vs `views_api.py` and `urls_ui.py` vs `urls_api.py` in each app — API and UI share models/services but have distinct permission/serialization layers.

## 3. Domain Models & Decisions

### User (accounts.User)
- Extends `AbstractUser`, adds `role` (HR/EMPLOYEE). `is_hr` property. No extra groups/permissions table — YAGNI for 2 roles, trivial to extend via django-guardian later.
- Linked 1:1 to `Employee` for the `employee_demo` account; HR accounts generally have no employee profile (they manage).

### Department
- `name` unique, `code` unique, `description`. Annotated with headcount/avg salary via `Count/Avg` in queries.

### Employee
- `employee_id` (unique, indexed, regex `ACME-\\d{5,}`), `first_name`, `last_name`, `full_name` (auto in `save()`), `email` unique, `phone`, `address`, `city`, `country` (char, indexed), `job_title` (indexed), `department` FK PROTECT, `employment_type`, `status` (ACTIVE/INACTIVE/ON_LEAVE), `date_of_joining`, `manager` (self-FK SET_NULL), `user` 1:1 nullable.
- Indexes: `(country, job_title)`, `(department, country)`, `full_name`, `status`. Enables fast analytics and list filtering without full scans.
- `full_name` denormalized for fast search (`icontains` on one column vs concat).

### SalaryStructure (1:1 Employee)
- Components: `basic_salary`, `house_rent_allowance`, `dearness_allowance`, `transport_allowance`, `telephone_allowance`, `special_allowance`, deductions `pf_deduction`, `professional_tax`; computed `gross_salary`, `tax_deduction`, `net_in_hand`, `total_compensation`.
- `recompute()` on `save()`: `gross = sum(allowances+basic)`, `annual_gross = gross*12`, `annual_tax = TaxBracket.compute_tax(country, annual_gross)`, `monthly_tax = annual_tax/12`, `net = gross - pf - prof_tax - monthly_tax`. Stored for fast payroll aggregation (no per-row Python in payroll queries).
- Validation: non-negative components, MinValueValidator.

### TaxBracket
- `country`, `lower_limit`, `upper_limit` (null=infinity), `rate` (%) — progressive. `compute_tax(country, gross)` sums `taxable_in_bracket * rate`. Falls back to GLOBAL if country has no brackets, else 0. Seeded with 5 slabs per country (USA/Germany overrides).

### Reimbursement
- `employee` FK CASCADE, `title`, `purpose`, `amount` (>0), `expense_date`, `receipt` FileField (`upload_to=reimbursements/<empID>/`), `status` (PENDING/APPROVED/REJECTED), `reviewed_by` FK User, `reviewed_at`, timestamps. Indexes on `(status, created_at)`, `(employee, status)`, `expense_date`.
- State machine enforced in views: PENDING → APPROVED/REJECTED only, idempotent guard (`if not pending → 400`). Employee creates PENDING only; HR approves/rejects.

### PayrollExport
- `requested_by`, `month` (first day), `format` (EXCEL/PDF), `status` (PENDING→PROCESSING→COMPLETED/FAILED), `celery_task_id`, `file`, `error`, timestamps. Enables async polling via HTMX `hx-get every 2s`.

## 4. API Design (DRF)

- **Auth:** SessionAuthentication (HTMX) + Basic for API tests; `IsAuthenticated` default, `IsHR` for admin actions, `IsHROrReadOnly`, `IsOwnerOrHR` object-level.
- **ViewSets with mixins** as requested: `DepartmentViewSet(List,Retrieve,Create,Update)`, `EmployeeViewSet(List,Retrieve,Create,Update,Destroy)`, `TaxBracketViewSet`, `ReimbursementViewSet(List,Retrieve,Create + @action approve/reject)`, `PayrollExportViewSet`, `PayrollDataView(APIView)`, `AnalyticsViewSet(List)`.
- **Pagination:** PageNumber 25 (DRF) and 25/50 for UI.
- **Filtering:** SearchFilter on `employee_id, full_name, email, job_title`; query params `department`, `country`, `job_title`, `status`, `employee_id` (exact). Ordered via `select_related`.
- **Salary hiding:** `EmployeeDetailSerializer.to_representation()` drops `salary` if requester is employee viewing another employee.
- **Analytics:** Single endpoint `GET /api/employees/analytics/?country=&job_title=&department=&group_by=` aggregates via `Avg/Min/Max/Count/Sum` in-DB; median/p25/p75 computed by fetching sorted `net_in_hand` column only (not full objects). Breakdowns `by_country`, `by_department`, `by_job_title` via `values().annotate()`.

## 5. UI (HTMX)

- **Base:** Tailwind CDN, django-htmx middleware, CSRF via `hx-headers`. No SPA build step — server renders HTML, HTMX swaps partials.
- **Pages:**
  - `LoginView` (FormView) — demo creds shown.
  - `DashboardView` — HR: totals, avg, dept table, pending queue; Employee: my profile + salary (private) + directory link.
  - `EmployeeListView` — search `q` + filters (dept/country/title) with `hx-get delay:400ms`, partial `employee_table.html`, pagination via hx-get.
  - `EmployeeDetailView` — profile + salary tab (hidden for non-HR viewing others), inline edit links, quick ID lookup form, recent reimbursements.
  - `EmployeeCreate/Update` — HR full form, employee limited to `phone, address, city` (form fields popped).
  - `SalaryUpdateView` — HR only, recompute on save.
  - `DepartmentList/Detail` — annotate stats, median via Python, paginated members clickable to detail.
  - `AnalyticsView` — same aggregation as API but rendered; filters via GET, specifics `avg for title in country` highlighted.
  - `ReimbursementList/Create/Detail/Action` — HTMX inline approve/reject (`hx-post` swaps row), file upload handled via `multipart`, polling not needed (status instant).
  - `PayrollView` — month picker, table `empID | salary | reimb | total` paginated 50, totals, export buttons POST to `PayrollExportCreateView` (queues Celery), polling via `hx-get every 2s` on status partial.
- **Permissions:** `LoginRequiredMixin` + `HRRequiredMixin(UserPassesTestMixin)` for HR pages; employee detail/edit checks `user.employee_profile.id == obj.id` for self-service.

## 6. Performance & Scaling Trade-offs

| Concern | Decision | Why |
|---------|----------|-----|
| **10k seed speed** | `bulk_create(batch_size=1000)` in `transaction.atomic`, bypass `save()` signals, compute tax in Python loop then bulk-create salaries, manager assignment via pure-Python dict (no per-row queries) | 10k in <5s vs 60s+ with per-row `create()`; measured 0.88s for 100, ~4-6s for 10k on SQLite |
| **List/search** | Pagination 25, `select_related(department,salary,manager)`, indexes on search fields, `icontains` on indexed `full_name/employee_id` | Keeps p95 <100ms at 10k |
| **Analytics** | `Avg/Min/Max/Count/Sum` in DB, `values_list` for median (single column) not full ORM objects | Avoids loading 10k employees into Python; ~40ms for analytics |
| **Payroll** | `select_related(salary)`, iterator for rows, reimbursement sums via single `values().annotate(Sum)` grouped by `employee_id`, not N+1 | 10k rows streamed, ~250ms |
| **SQLite vs Postgres** | SQLite WAL, `timeout=20` | Sufficient for 10k, single-writer; Postgres is config switch later (no code change) |
| **Tax** | Progressive in Python `TaxBracket.compute_tax`, not DB function | Simple, testable, fast (51 brackets cached) |

## 7. Background Jobs (Celery)

- `CELERY_TASK_ALWAYS_EAGER=1` default so project runs without Redis. With `REDIS_URL` set, tasks run async.
- `generate_payroll_export(export_id)`: fetches `PayrollExport`, sets PROCESSING, calls `get_payroll_rows(month)`, then writes Excel (openpyxl: headers, auto-filter, freeze, col width) or PDF (ReportLab platypus Table with styled header, alternating rows, totals). Saves via `ContentFile` to `DEFAULT_FILE_STORAGE` (MinIO if `USE_MINIO=1` else `MEDIA_ROOT`).

## 8. Storage (MinIO)

- `USE_MINIO=1` switches `DEFAULT_FILE_STORAGE` to `S3Boto3Storage` with `AWS_S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, etc. Receipts `reimbursements/<empID>/file` and exports `payroll_exports/` stored via same API. Fallback to filesystem lets assessment run with `uv run ...` zero extra services. File validation (MIME/size) could be added via form `clean_receipt`.

## 9. Testing Strategy

- **pytest + pytest-django**, DB per test (transaction rollback), 28 tests in 6s.
- Models: salary recompute, tax fallback, full_name, constraints.
- API: HR vs employee permissions (create, salary visibility, update whitelist, department filter, search by ID, analytics auth).
- Reimbursements: employee create pending, visibility scope, HR approve/reject, double-approve guard, employee cannot approve.
- Payroll: rows sum, approved vs pending, HR gate, export eager completes, salary edit recomputes total, inactive excluded.
- No mocks for DB — real SQLite queries ensure ORM optimization is tested; no network calls.

## 10. What We Deliberately Left Out (see REQUIREMENTS.md) and Future Hooks

- SPA, multi-currency, leave/attendance, salary history, notifications, SSO — architecture has seam for each (e.g., `django-simple-history` for history, `dj-rest-auth` for SSO, `fx-service` for currency).

## 11. Diagrams

### Data Flow (Payroll Export)

```
HR clicks Export (Excel/PDF) → PayrollExportCreateView → PayrollExport(PENDING) → generate_payroll_export.delay()
    ├─ eager: runs inline → get_payroll_rows() → openpyxl/ReportLab → save file → COMPLETED
    └─ async: broker → worker → same steps → polling via HTMX hx-get every 2s → Download
Salary edit → SalaryStructure.save() → recompute() → next payroll export reflects new gross/net (no stale snapshot)
```

### Reimbursement Flow

```
Employee POST /reimbursements/create → Reimbursement(PENDING, receipt→MinIO) → HR queue /api/reimbursements/?status=PENDING
HR POST /reimbursements/{id}/approve → status APPROVED, reviewed_by, reviewed_at → Employee sees status via list/detail (HTMX swap)
Payroll next month: Sum(APPROVED where expense_date in month) added to salary total
```
