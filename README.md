# ACME Pay — Salary Management for 10,000 Employees

HR web app to replace Excel-based salary management. Built with **Django 5 + DRF + HTMX + Celery + MinIO (fallback to filesystem) + SQLite**, managed via **uv**. Handles 10,000 employees with fast search, department browsing, salary analytics, reimbursements, and monthly payroll exports (Excel/PDF).

**Demo credentials after seeding:** `hr_admin / hr12345` (HR Manager) · `employee_demo / emp12345` (Employee)

---

## Quick Start (uv, no Docker needed)

```bash
# 1. Install deps (creates .venv)
uv sync

# 2. Migrate
uv run python manage.py migrate

# 3. Seed 10,000 employees (optimized: bulk_create batch 1000, ~4-6s)
uv run python manage.py seed_employees --count 10000 --clear
# smaller demo: --count 1000 --clear
# Uses first_names.txt / last_names.txt if present; otherwise bundled fallback lists

# 4. Run server
uv run python manage.py runserver
# → http://127.0.0.1:8000/accounts/login/
```

Optional services (Celery + MinIO) — project runs without them (Celery eager, filesystem storage):

```bash
# Redis for async Celery
CELERY_BROKER_URL=redis://localhost:6379/0 uv run celery -A config worker -l info
# MinIO
USE_MINIO=1 MINIO_ENDPOINT=http://localhost:9000 MINIO_ACCESS_KEY=minioadmin MINIO_SECRET_KEY=minioadmin uv run python manage.py runserver
docker compose up -d   # if you add a compose file with redis/minio
```

## Users & Permissions

| User | Login | What they see |
|------|-------|---------------|
| HR Manager | `hr_admin / hr12345` | All employees CRUD, all salaries, analytics (min/max/avg/median by country/title/dept), approve/reject reimbursements, payroll exports |
| Employee | `employee_demo / emp12345` (linked to ACME-00001) | Own profile + own salary (read-only); other employees' *public* profiles (salary hidden); edit own `phone, address, city`; create reimbursements; view own reimbursement status |

All enforcement is server-side (DRF `IsHR`, `IsOwnerOrHR`, Django `UserPassesTestMixin`).

## Features

- **Employee Directory:** Search by `employee_id` (e.g. `ACME-00042`), name, email, job title; filter by department/country/title; HTMX live search (400 ms debounce) + pagination 25; click name → detail.
- **Employee Detail:** Profile (contact, dept, manager) + **Salary Structure** (basic, HRA, DA, TA, telephone, special, PF, professional tax, tax via brackets, gross, net in-hand). HR can edit any component → recompute; employee can edit only `phone, address, city` on own profile.
- **Department Browse:** `/departments/` shows headcount/avg/max; `/departments/<id>/` lists members paginated, stats min/max/avg/median.
- **Salary Insights:** `/analytics/` — overall min/max/avg/median/p25/p75/total, plus `by_country`, `by_department`, `by_job_title`; filtered by country/title/department; specific `avg for job title in country` highlighted. Backed by `/api/employees/analytics/`.
- **Reimbursements:** Employee form `title, purpose, amount, expense_date, receipt (PDF/image → MinIO or media/)`. Status `PENDING → APPROVED/REJECTED`. HR queue with inline `Approve/Reject` (HTMX swaps row). Status polls via HTMX.
- **Monthly Payroll:** `/payroll/?month=YYYY-MM` table `empID | salary_amount (net) | reimbursement_amount (sum APPROVED in month) | total` (50/page, totals footer). `Export Excel`/`Export PDF` queues Celery task → HTMX polling `every 2s` → download. Live recompute after any salary edit.

## API (DRF, session auth)

```
GET  /api/employees/                     # list, ?search=&department=&country=&job_title=&employee_id=
POST /api/employees/                     # HR only
GET  /api/employees/<id>/                # detail (salary hidden for non-HR viewing others)
PATCH /api/employees/<id>/               # HR full, employee limited to own phone/address/city
GET/PUT/PATCH /api/employees/<id>/salary/
GET  /api/employees/analytics/?country=India&job_title=Software+Engineer
GET  /api/employees/departments/         # with employee_count
GET  /api/reimbursements/                # employee sees own, HR sees all; ?status=PENDING
POST /api/reimbursements/                # employee auto-linked, HR may specify employee
POST /api/reimbursements/<id>/approve/   # HR
POST /api/reimbursements/<id>/reject/    # HR
GET  /api/payroll/data/?month=2026-09&page_size=50
POST /api/payroll/exports/ {month, format: EXCEL|PDF}
GET  /api/payroll/exports/               # list, ? for status
```

All list endpoints use `ListModelMixin` + `PageNumberPagination (25)`, plus search/ordering filters.

## Seeding (Performance)

```bash
uv run python manage.py seed_employees --count 10000 --clear --batch-size 1000
```

- Combines `first_names.txt` + `last_names.txt` (500+ names) × countries × titles × departments.
- Salary bands per title × country multipliers, randomized components, progressive tax via `TaxBracket` (5 slabs per country).
- `bulk_create(batch_size=1000)` + `transaction.atomic` + no per-row `save()`; salaries computed in Python then bulk-created; manager assignment via pure-Python dict (no N+1 queries). Result: 10k employees + 10k salaries in ~4-6s on SQLite.

## Testing

```bash
uv run pytest -q
# 28 tests in ~6s — models, API permissions, reimbursement state machine, payroll totals/exports, analytics
uv run pytest -v   # detailed
uv run coverage run -m pytest && uv run coverage report # optional
```

Tests are deterministic (seeded random), no network, no mocks for DB.

## Project Structure

```
config/                # settings, urls, celery, api_urls
apps/accounts/         # User, permissions, login views
apps/employees/        # Department, Employee, SalaryStructure, TaxBracket, seed, UI+API
apps/reimbursements/   # Reimbursement, UI+API
apps/payroll/          # PayrollExport, tasks, UI+API
templates/             # base, dashboard, employees/*, reimbursements/*, payroll/*
docs/REQUIREMENTS.md   # 1-page scope + out-of-scope
docs/ARCHITECTURE.md   # decisions, diagrams, performance
```

## Trade-offs & Out-of-Scope (see docs/REQUIREMENTS.md)

No React SPA (HTMX gives same interactivity with server render, smaller build), no multi-currency/FX, no leave/attendance, no salary history (seam via django-simple-history), no email/Slack notifications (Celery ready), no SSO, SQLite not Postgres (switch via DATABASES).

## Demo Video Script (60s)

1. Login as `hr_admin` → dashboard totals (10k, avg, depts).
2. Search `ACME-00042` → detail → edit salary TA from 1200 to 5000 → net recomputes.
3. Browse Engineering dept → click member → detail.
4. Analytics → filter `Country=India, Job Title=Software Engineer` → avg shown.
5. Reimbursements → HR queue → approve `Travel`.
6. Payroll → month picker → totals → Export Excel → polling → download → open file.
7. Logout, login as `employee_demo` → My Dashboard → view own salary, edit phone, create reimbursement, see status.

## Troubleshooting

- `Forbidden` on API → ensure you seeded and use `hr_admin` for HR-gated endpoints.
- Celery export stuck PENDING → running with `CELERY_ALWAYS_EAGER=1` (default) it completes inline; if you set `CELERY_ALWAYS_EAGER=0` you need Redis.
- MinIO upload fails → `USE_MINIO=0` (default) falls back to `media/` — no setup needed.

## Artifacts & Commits

`git log --oneline` shows incremental commits (`requirements → models+seed → api → ui → payroll+tests → polish`). See `docs/` for prompts/notes.

---
Built with Django 5, DRF `RetrieveModelMixin/ListModelMixin/...`, django-htmx, Celery, openpyxl, ReportLab, uv.
