# ACME Pay — Salary Management for 10,000 Employees

[![CI](https://github.com/utkarshpandey12/salary_management/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/utkarshpandey12/salary_management/actions/workflows/ci.yaml)
[![Build](https://github.com/utkarshpandey12/salary_management/actions/workflows/build.yaml/badge.svg?branch=main)](https://github.com/utkarshpandey12/salary_management/actions/workflows/build.yaml)
[![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen?logo=pytest)](https://github.com/utkarshpandey12/salary_management/actions/workflows/ci.yaml)
[![Tests](https://img.shields.io/badge/tests-299%20passed-brightgreen?logo=pytest)](https://github.com/utkarshpandey12/salary_management/actions/workflows/ci.yaml)
[![Python](https://img.shields.io/badge/python-3.12-blue?logo=python)](https://www.python.org)
[![Django](https://img.shields.io/badge/Django-5.2-092E20?logo=django)](https://www.djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.15-red?logo=django)](https://www.django-rest-framework.org)
[![HTMX](https://img.shields.io/badge/HTMX-1.9-3D72D7?logo=htmx)](https://htmx.org)
[![Celery](https://img.shields.io/badge/Celery-5.4-37814A?logo=celery)](https://celeryproject.org)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis)](https://redis.io)
[![MinIO](https://img.shields.io/badge/MinIO-S3-C72E49?logo=minio)](https://min.io)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite)](https://www.sqlite.org)
[![uv](https://img.shields.io/badge/uv-0.9-black?logo=astral)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/badge/Ruff-0.8-black?logo=ruff)](https://docs.astral.sh/ruff)
[![Docker](https://img.shields.io/badge/Docker-multi--stage-2496ED?logo=docker)](https://www.docker.com)
[![OpenPyXL](https://img.shields.io/badge/OpenPyXL-3.1-green)](https://openpyxl.readthedocs.io)
[![ReportLab](https://img.shields.io/badge/ReportLab-4.2-blue)](https://www.reportlab.com)

> HR web app to replace Excel-based salary management. Built with **Django 5 + DRF + HTMX + Celery + MinIO (S3 fallback to filesystem) + SQLite**, managed via **uv**. Handles **10,000 employees** with fast search, department browsing, salary analytics, reimbursements, and monthly payroll exports (Excel/PDF).

**Demo credentials after seeding:** `hr_admin / hr12345` (HR Manager) · `employee_demo / emp12345` (Employee — linked to `ACME-00001`)

---

## Quick Start (uv, no Docker)

```bash
# 1. Install deps (creates .venv, respects uv.lock)
uv sync

# 2. Migrate
uv run python manage.py migrate

# 3. Seed 10,000 employees (optimized: bulk_create batch 1000, ~4-6s)
uv run python manage.py seed_employees --count 10000 --clear
# smaller demo: --count 1000 --clear
# Reads first_names.txt / last_names.txt if present, else bundled fallback

# 4. Run server
uv run python manage.py runserver
# → http://127.0.0.1:8000/accounts/login/
```

Optional services (project runs without them — Celery eager + filesystem):

```bash
# Redis for async Celery (otherwise eager inline)
CELERY_BROKER_URL=redis://localhost:6379/0 uv run celery -A config worker -l info -Q payroll
# MinIO (S3)
USE_MINIO=1 MINIO_ENDPOINT=http://localhost:9000 MINIO_ACCESS_KEY=minioadmin MINIO_SECRET_KEY=minioadmin uv run python manage.py runserver
```

## Users & Permissions

| User | Login | What they see |
|------|-------|---------------|
| HR Manager | `hr_admin / hr12345` | All employees CRUD, all salaries, analytics (min/max/avg/median by country/title/dept), approve/reject reimbursements, payroll exports |
| Employee | `employee_demo / emp12345` (linked to `ACME-00001`) | Own profile + own salary (read-only); other employees' *public* profiles (salary hidden, no locked card); edit own `phone, address, city`; create reimbursements; view own status |

All enforcement is server-side (`apps/accounts/permissions.py:IsHR`, `IsOwnerOrHR`, `HRRequiredMixin`).

## Features

- **Employee Directory:** Search by `employee_id` (e.g. `ACME-00042`), name, email, job title; filter by department/country/title; HTMX live search (400 ms debounce) + pagination 25; click name → detail; manager link clickable for both roles.
- **Employee Detail:** Profile (contact, dept, clickable manager) + **Salary Structure** (basic, HRA, DA, TA, telephone, special, PF, professional tax, tax via brackets, gross, net). HR edits any component → recompute; employee edits only `phone, address, city` on own profile. Salary hidden completely for employees viewing others (no confidential card).
- **Department Browse:** `/departments/` — HR sees `Members/Avg/Max`, employee sees only `Members`; `/departments/<id>/` — HR sees `Avg/Median/Range` + `Net` column, employee sees only count + confidential note.
- **Salary Insights:** `/analytics/` (HR only) — overall min/max/avg/median/p25/p75/total, `by_country`/`by_department`/`by_job_title`; filtered by country/title/department; specific `avg for job title in country` highlighted. Backed by `/api/employees/analytics/`.
- **Reimbursements:** Employee form `title, purpose, amount, expense_date, receipt (PDF/image → MinIO or media/)`. Status `PENDING → APPROVED/REJECTED`. HR queue with inline `Approve/Reject` (HTMX swaps row).
- **Monthly Payroll:** `/payroll/?month=YYYY-MM` table `empID | salary_amount (net) | reimbursement_amount (sum APPROVED in month) | total` (50/page, totals footer). `Export Excel`/`Export PDF` queues Celery (`payroll` queue) → HTMX polling `every 2s` → download. Live recompute after salary edit.

## API (DRF, session auth — `ListModelMixin` etc.)

```
GET  /api/employees/                     # list, ?search=&department=&country=&job_title=&employee_id=
POST /api/employees/                     # HR only
GET  /api/employees/<id>/                # detail (salary hidden for non-HR viewing others via to_representation)
PATCH /api/employees/<id>/               # HR full, employee limited to own phone/address/city
GET/PUT/PATCH /api/employees/<id>/salary/ # HR only (recompute)
GET  /api/employees/analytics/?country=India&job_title=Software+Engineer  # HR only, aggregates in-DB
GET  /api/employees/departments/         # with employee_count
GET  /api/reimbursements/                # employee sees own, HR sees all; ?status=PENDING
POST /api/reimbursements/                # employee auto-linked, HR may specify employee
POST /api/reimbursements/<id>/approve/   # HR (state machine)
POST /api/reimbursements/<id>/reject/    # HR
GET  /api/payroll/data/?month=2026-09&page_size=50  # HR, totals
POST /api/payroll/exports/ {month, format: EXCEL|PDF}  # HR, queue=payroll
GET  /api/payroll/exports/               # HR
```

All list endpoints use DRF `PageNumberPagination (25)` + `SearchFilter`/`OrderingFilter`.

## Seeding (Performance)

```bash
uv run python manage.py seed_employees --count 10000 --clear --batch-size 1000
```

- Combines `first_names.txt` (170) + `last_names.txt` (130) × countries × titles × departments.
- Salary bands per title × country multipliers, randomized components, progressive tax via `TaxBracket` (5 slabs per country, `GLOBAL` fallback).
- `bulk_create(batch_size=1000)` + `transaction.atomic` + no per-row `save()`; salaries computed in Python then bulk-created; manager assignment via pure-Python dict (no N+1, now `10000/10000` mapped). **10k in ~4-6s on SQLite.**

## Testing — 299 tests, app-level, business-rule focused

Tests live **inside each app**, not a separate `tests/` folder:

- `apps/accounts/tests/test_models.py`, `test_permissions.py`, `test_views.py` — User roles, `is_hr`, permissions, login/logout, `me` API
- `apps/employees/tests/test_models.py`, `test_models_comprehensive.py`, `test_salary_logic.py`, `test_api.py`, `test_api_analytics.py`, `test_api_departments.py`, `test_views_ui_comprehensive.py` — Department uniqueness, Employee `full_name`, `employee_id` regex, manager FK, Salary recompute (gross/tax/net, country-specific, zero/precision), TaxBracket progressive, Department/Employee/Tax/Analytics API (HR vs employee, salary hiding, filters, pagination, htmx), UI department salary hiding, manager clickable
- `apps/reimbursements/tests/test_models_comprehensive.py`, `test_api.py`, `test_views_ui_comprehensive.py` — amount>0, status machine, receipt upload_to, employee vs HR queryset, approve/reject transitions, double-approve guard
- `apps/payroll/tests/test_models.py`, `test_payroll.py`, `test_api_comprehensive.py` — `PayrollExport` status, `get_payroll_rows` (approved vs pending, inactive excluded, month filter), export Excel/PDF via eager Celery, HR gate, pagination, totals

```bash
uv sync --group dev
uv run pytest -v                # 299 passed
uv run pytest --cov=apps --cov-report=term-missing --cov-report=html
uv run coverage report --fail-under=70
# All deterministic, no network, no mocks for DB
```

Each test verifies **business definitions**, e.g. `employee_cannot_access_other_employees_salary`, `hr_only_can_edit_employee_salary`, `reimbursement_pending_cannot_be_double_approved`, `payroll_total_equals_salary_plus_approved_reimbursement`, `department_salary_hidden_for_employee`.

## Pre-commit

```bash
uv sync --group dev
uv run pre-commit install
uv run pre-commit run --all-files   # ruff --fix, ruff-format, isort, trailing-whitespace, check-yaml, detect-private-key, mypy
```

Config: `.pre-commit-config.yaml` (ruff `v0.8.4`, isort `5.13.2`, pre-commit-hooks `v4.6.0`, mypy with `django-stubs`).

- **Ruff:** `uv run ruff check .` / `uv run ruff check . --fix`
- **Format:** `uv run ruff format .` / `uv run ruff format --check .`
- **Isort:** `uv run isort --profile black .` (via pre-commit)

`pyproject.toml` sets `tool.ruff` (line 100, py312, select E,F,I,B,C4,UP,W) and `tool.coverage` (fail_under 75).

## CI — `.github/workflows/ci.yaml`

Two jobs (lint → test), runs on `push`/`pull_request` to `main`:

1. **lint** — `uv sync --group dev`, `ruff check`, `ruff format --check`, `pre-commit run --all-files`
2. **test** — services `redis:7-alpine`, `migrate`, `pytest --cov=apps --cov-report=xml --cov-report=html -v`, `coverage report --fail-under=70`, upload `coverage.xml` + `htmlcov` artifacts, optional `codecov` step

```bash
# Locally mimic CI:
uv run ruff check . && uv run ruff format --check . && uv run pre-commit run --all-files
uv run pytest --cov=apps --cov-report=term-missing
```

Badge: `![CI](https://github.com/utkarshpandey12/salary_management/actions/workflows/ci.yaml/badge.svg?branch=main)`

## Build & Release — `.github/workflows/build.yaml` + `Dockerfile` + `entrypoint.sh` + `build.sh`

**Dockerfile** — lean multi-stage, BuildKit cache:

- `ARG PYTHON_VERSION=3.12`
- **builder** `ghcr.io/astral-sh/uv:python3.12-bookworm` — `COPY pyproject.toml uv.lock` then `uv sync --frozen --no-dev` (cached), then copy source + `uv sync --frozen --no-dev`
- **runtime** `python:3.12-slim-bookworm` — `curl` only, `user app`, `COPY --from=builder .venv`, `HEALTHCHECK` on `/accounts/login/`, `ENTRYPOINT ["./entrypoint.sh"]`, `EXPOSE 8000`

Caching: `--cache-from type=gha` / `--cache-to type=gha,mode=max`, platforms `linux/amd64,linux/arm64`, `UV_LINK_MODE=copy`, `UV_COMPILE_BYTECODE=1`, `.dockerignore` excludes `db.sqlite3, media, .venv, htmlcov`.

**entrypoint.sh** — handles `migrate`, auto-seed if empty (`AUTO_SEED=1`, `SEED_COUNT=10000`), `collectstatic` when `DJANGO_DEBUG=0`, then:

- `server` (default) — if `CELERY_ALWAYS_EAGER=0` starts `celery -A config worker -Q payroll` in background + `gunicorn` (or `runserver` fallback) on `0.0.0.0:8000`
- `celery` — worker only (`-Q payroll`)
- `bash`/`migrate` — pass-through

```bash
chmod +x entrypoint.sh
```

**Build script** — `build.sh` (executable, BuildKit + uv cache, prints SHA):

```bash
./build.sh [tag]              # default salary-management:local
./build.sh ghcr.io/utkarshpandey12/salary_management:latest --push
PUSH=1 ./build.sh
# Prints: Image ID (sha), Digest, Size, Run examples
# Outputs GITHUB_OUTPUT image/sha/digest in CI
```

**Build workflow** triggers on `push` to `main`/`tags v*` or manual dispatch; uses `docker/setup-qemu`, `docker/setup-buildx`, `docker/login-action` (GHCR), `docker/metadata-action` (tags: `branch`, `semver`, `sha`, `latest`), `docker/build-push-action` (`cache-from/to gha`, `platforms linux/amd64,linux/arm64`), prints `digest`/`tags` to logs + `$GITHUB_STEP_SUMMARY`, creates GitHub Release on `v*` via `softprops/action-gh-release`.

No `docker-compose.yml` — run via `docker run`:

```bash
# Eager (no Redis)
docker build -t salary-management:local . && ./build.sh
docker run -p 8000:8000 -e DJANGO_SECRET_KEY=dev-secret salary-management:local
# → http://localhost:8000/accounts/login/

# Async Celery + Redis + MinIO
docker run -p 8000:8000 \
  -e DJANGO_SECRET_KEY=prod-secret \
  -e CELERY_ALWAYS_EAGER=0 -e CELERY_BROKER_URL=redis://host.docker.internal:6379/0 \
  -e USE_MINIO=1 -e MINIO_ENDPOINT=http://host.docker.internal:9000 \
  salary-management:local
# Celery only
docker run salary-management:local celery
```

Workflow badges: `![Build](https://github.com/utkarshpandey12/salary_management/actions/workflows/build.yaml/badge.svg?branch=main)`; image SHA printed in build logs and release notes.

## Project Structure

```
config/                # settings, urls, wsgi, asgi, celery, api_urls
apps/
  accounts/            # User, permissions, login, tests/test_models|permissions|views
  employees/           # Department, Employee, SalaryStructure, TaxBracket, seed, UI+API, tests/* (models, salary_logic, api, analytics, views_ui)
  reimbursements/      # Reimbursement, UI+API, tests/* (models, api, views_ui)
  payroll/             # PayrollExport, tasks, UI+API, tests/* (models, payroll, api_comprehensive)
templates/             # base, dashboard, employees/*, reimbursements/*, payroll/* (HTMX partials)
static/                # Tailwind CDN (no build)
docs/
  REQUIREMENTS.md      # 1-page goal/scope/out-of-scope
  ARCHITECTURE.md      # decisions, diagrams, perf, Celery/MinIO
  PROMPTS.md           # AI prompts & verification loop
.github/workflows/
  ci.yaml              # lint (ruff/pre-commit) -> test (pytest coverage 70%)
  build.yaml           # docker buildx -> GHCR -> release -> print SHA
Dockerfile             # multi-stage, uv cache, lean slim, healthcheck
entrypoint.sh          # migrate, auto-seed, server+celery (queue=payroll)
build.sh               # docker buildx wrapper, prints SHA
.pre-commit-config.yaml # ruff, ruff-format, isort, mypy, trailing-whitespace
first_names.txt / last_names.txt  # 170/130 names for deterministic seeding
```

## Trade-offs & Out-of-Scope (see `docs/REQUIREMENTS.md`)

No React SPA (HTMX gives same SPA feel with server render), no multi-currency/FX, no leave/attendance, no salary history (seam via `django-simple-history`), no email/Slack notifications (Celery ready), no SSO, SQLite WAL not Postgres (switch via `DATABASES`), MinIO filesystem fallback.

## Demo Video Script (60s)

1. Login as `hr_admin` → dashboard totals (10k, avg, depts, pending queue).
2. Search `ACME-00042` → detail → edit salary TA → net recomputes.
3. Browse `Engineering` dept → HR sees Avg/Median/Net, employee sees only Members — click member → detail (manager link clickable, salary hidden for employee viewing other).
4. Analytics → filter `Country=India, Job Title=Software Engineer` → avg shown.
5. Reimbursements → create as employee → HR queue → approve (HTMX row swap).
6. Payroll → month picker → totals → Export Excel (queue=payroll, eager or `celery -A config worker -Q payroll`) → polling → download.
7. Logout, login `employee_demo` → My Dashboard → own salary, edit phone, create reimbursement, department tab shows no salary.

## Troubleshooting

- `Forbidden` on API → use `hr_admin` for HR-gated (`/api/employees/analytics`, `/api/payroll/*`).
- `Invalid filter: intcomma` → ensure `{% load humanize %}` in partials (fixed in `reimbursement_row.html`).
- Celery export stuck `PENDING` → default `CELERY_ALWAYS_EAGER=1` runs inline; for async set `CELERY_ALWAYS_EAGER=0` + `CELERY_BROKER_URL` + `uv run celery -A config worker -Q payroll`.
- MinIO upload fails → `USE_MINIO=0` falls back to `media/`; set `MINIO_ENDPOINT/KEYS` for S3.
- `TemplateSyntaxError` or `500` → `uv run python manage.py check` + `uv run pytest -q`.

## Artifacts & Commits

`git log --oneline` shows 8+ incremental commits (`requirements → models → api → ui → seed+tasks+tests → docs → fixtures → fixes → 299 tests → pre-commit/CI/build`). See `docs/` for prompts/notes + `build.sh` SHA output.

---

Built with Django 5, DRF `RetrieveModelMixin/ListModelMixin/...`, `django-htmx`, Celery (`payroll` queue), `boto3`/`django-storages`, `openpyxl`/`ReportLab`, `uv`, `ruff`, `pre-commit`, `pytest`/`coverage`, `gunicorn`, Docker multi-stage.
