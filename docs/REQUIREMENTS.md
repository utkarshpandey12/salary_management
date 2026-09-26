# Salary Management Tool — Requirements Document

**Version:** 1.0 — 26 Sep 2026  
**Author:** Salary Management Team  
**Status:** Approved for Build

---

## 1. Goal

Replace ACME Org's Excel-based salary management for **10,000 employees across multiple countries** with a secure, web-based system that lets an **HR Manager** manage employee & compensation data and answer "how we pay people" in seconds. Employees get self-service access to their own data and reimbursement workflows.

Success = HR can create/update/delete employees, browse by department/team, inspect & edit granular salary structures with tax computed automatically, view salary analytics (min/max/avg/median by country/title/department), and export a monthly payroll. All interactions feel instant (<200ms for list/search, <1s for analytics) even at 10k scale.

## 2. Scope & Features

### 2.1 User Roles
| Role | Auth | Capabilities |
|------|------|--------------|
| **HR Manager** | Username/password (Django session + DRF token) | Full CRUD on employees & salary components; view all analytics; approve/reject reimbursements; export payroll |
| **Employee** | Same | View own profile + own salary (read-only); view other employees' *non-salary* profile; edit only own `address`, `phone`; create reimbursement requests; view own reimbursement status |

Permission enforcement is server-side (DRF permission classes + Django view mixins), not just UI hiding.

### 2.2 Employee Management
- **Data captured:** `employee_id` (unique, searchable, e.g. ACME-00001), `full_name` (first+last from seed lists), `job_title`, `country`, `department/team`, `email`, `phone`, `address`, `date_of_joining`, `employment_type` (full-time/contract), `manager` (self-FK), `status` (active/inactive), `created_at/updated_at`.
- **HR operations (UI + API):** Create, list with search/pagination/filter, retrieve by ID, update (profile & salary), delete. List is paginated (25/page) with HTMX search/filter without full page reload. Optimised queries via `select_related`/`prefetch_related`, DB indexes on `employee_id`, `country`, `job_title`, `department`.
- **Employee view:** "My Details" page; directory of other employees (salary redacted).

### 2.3 Salary Structure & Tax
Per-employee `SalaryStructure` (1:1):
`basic_salary`, `house_rent_allowance`, `dearness_allowance`, `transport_allowance`, `telephone_allowance`, `special_allowance`, `pf_deduction`, `professional_tax`.

Computed (stored + recomputed on save):
- `gross = sum(allowances + basic)`
- `tax_deduction` via **country-specific TaxBracket** table (e.g. slabs 0-5L/5%, 5-10L/10%, 10L+20%) — simple progressive calculation.
- `total_comp = gross`
- `net_in_hand = gross - pf_deduction - professional_tax - tax_deduction`

HR can edit any component on the employee detail salary tab (HTMX inline form); totals recompute atomically and reflect immediately in payroll export.

### 2.4 Department / Team Browsing
- Departments seeded (Engineering, Sales, HR, Finance, Marketing, Support, Ops, Product, Design, Legal, ...)
- View employees by department with same ID-click → detail pattern. Each department row shows headcount and avg salary for quick scanning.

### 2.5 Salary Insights / Analytics (HR only, UI + API)
- **By country:** min, max, avg, median, headcount, total payroll.
- **By job title × country:** avg salary for a given title in a given country.
- **By department:** min, max, avg, median, p25/p75, total cost, distribution histogram; country/job-title breakdowns.
- Endpoints aggregate in-DB (`Avg`, `Min`, `Max`, `Count`; median via ordered percentile) to avoid loading 10k rows into Python.

### 2.6 Reimbursements
Employee creates: `title`, `purpose`, `amount`, `expense_date`, `receipt` (PDF/image upload via MinIO/S3-compatible, filesystem fallback). Status `pending → approved/rejected`. HR sees queue, can view receipt, approve/reject with audit (`reviewed_by`, `reviewed_at`). Employee sees status update. HTMX polling for status.

### 2.7 Monthly Payroll
Page: table `empID | salary_amount (net_in_hand) | reimbursement_amount (sum of approved in month) | total_amount`. Computed live via annotated query: `salary.net_in_hand + Coalesce(Sum(approved reimbursements))`. Supports month selector. Export to **Excel (openpyxl)** and **PDF (ReportLab)** via **Celery background task** (eager in dev, Redis in prod) — HR clicks Export → task queued → polling → download. Recomputing after any salary edit is implicit (no stale snapshot; snapshot table optional for audit but v1 computes live).

### 2.8 Seeding (10,000 employees)
- `python manage.py seed_employees --count 10000` reads `first_names.txt`/`last_names.txt` (fallback to generated lists if absent).
- Performance: `bulk_create(batch_size=1000)` + `select_related` seeding of departments/titles/countries, `transaction.atomic`, no per-row `save()` signals; salary structures bulk-created in same transaction. Measured target <15s for 10k on SQLite local.
- Idempotent-ish: `--clear` flag truncates; otherwise skips if count reached. Creates one `hr_admin` (hr / hr12345) and one `employee` demo user.

### 2.9 Technical Stack (as requested)
- **Backend:** Django 5.x + Django REST Framework (class-based views with `RetrieveModelMixin`, `ListModelMixin`, `CreateModelMixin`, `UpdateModelMixin`, `DestroyModelMixin`).
- **UI:** Django templates + `django-htmx` for dynamic search, inline edits, modals, polling — no full React SPA (HTMX gives same SPA feel with server rendering, faster to build & test).
- **DB:** SQLite (WAL mode, indexed), ORM optimised.
- **Package manager:** `uv`.
- **Async:** Celery (Redis broker if available; `task_always_eager` fallback).
- **Storage:** MinIO (S3 API via `boto3`/`django-storages`); local filesystem fallback so project runs without MinIO.
- **Project layout:** `config/` (settings/urls/celery), `apps/accounts`, `apps/employees`, `apps/reimbursements`, `apps/payroll`, `apps/analytics` + `api/` vs `views_ui/` separation.

## 3. Out of Scope — Deliberately Not Building (and Why)

| Not Building | Reason |
|---|---|
| **React/Next.js SPA** | Requirement says "HTMX as front-end with DRF for API" — HTMX+DRF already separates API/UI while keeping build small. SPA would double build/test surface for no product gain. |
| **Multi-currency & FX conversion, payroll bank integration** | High compliance risk; not needed to answer "how we pay" at v1. Store single-currency amounts; add FX later behind a service. |
| **Full leave/attendance/performance modules** | Scope creep — v1 is salary + reimbursements + payroll. These are separate domains. |
| **Advanced RBAC (managers, finance approvers, region admins)** | Only two roles needed to validate core flow. Extending to role-permission table is trivial later. |
| **Salary history / audit trail & approvals workflow** | Valuable but doubles model complexity. v1 stores `updated_at` + recomputes live; history can be added via `django-simple-history` without schema break. |
| **Real-time notifications (email/Slack) for reimbursements/payroll** | Celery infra is ready; wiring SMTP/Slack is config, not architecture. Deferred to avoid secrets/ops overhead in assessment. |
| **SSO / OAuth, 2FA** | Session auth suffices for demo; token auth for API. Pluggable via `dj-rest-auth` later. |
| **Horizontal scaling, Postgres, sharding, read replicas** | 10k rows is trivial for SQLite (indexes + pagination). Postgres is a config switch when needed. |
| **Complex tax engine (deductions, exemptions, country-specific rules beyond slabs)** | Simple progressive brackets cover the demo and prove the recomputation flow; real engine is a separate service. |

## 4. Non-Functional & Constraints
- **Performance:** List/search <200ms p95; analytics <500ms; seed 10k <15s. Achieved via pagination, DB aggregation, bulk ops, `select_related`, indexes.
- **Security:** Password hashing (PBKDF2), CSRF on HTMX forms, permission checks on every API/UI view, receipt uploads validated (MIME/size), MinIO presigned URLs.
- **Testing:** Unit tests for models (salary computation, tax), API permissions, analytics aggregation, reimbursement state machine, payroll totals — fast (<5s), deterministic, no network.
- **Readiness:** `uv sync && uv run python manage.py migrate && uv run python manage.py seed_employees && uv run python manage.py runserver` boots fully. Docker Compose for MinIO/Redis optional. Video demo + this doc committed.

## 5. Open Questions (Ask, Don't Assume)
- Approved list of countries/titles/departments or free-form? → Seeded enums, admin-editable.
- Currency assumption for "total_amount" export? → Single currency (USD) for v1.
- Payroll month = calendar month of `approved_at`/`expense_date`? → `expense_date` month with `approved` status.

---

*One page when printed (A4, 11pt). Full architecture & trade-offs in `docs/ARCHITECTURE.md`.*
