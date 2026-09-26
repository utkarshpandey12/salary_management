# AI Usage — Prompts & Approach

This project was built in an AI-driven workflow. The AI (Muse Spark via OpenCode) was used as a pair-programmer, not a blind generator — every AI output was reviewed, tested, and refined.

## How AI Was Delegated

- **Scaffold generation:** Prompted to create Django 5 + DRF + HTMX skeleton (settings, apps, celery, minio fallback) — then manually audited for industry practices (uv, WAL, indexes, pagination).
- **Model design:** Asked AI to draft `Employee`, `SalaryStructure`, `TaxBracket`, `Reimbursement`, `PayrollExport` with advanced types; revised to add `CheckConstraint(condition=)`, `full_name` denormalization, `recompute()` with annualization, and pure-Python manager assignment.
- **Seeding:** Delegated bulk-create optimization; benchmarked and fixed N+1 manager assignment after first 10k run timed out.
- **API:** Requested ViewSets with `ListModelMixin`/`RetrieveModelMixin` etc.; then fixed serializer `employee` required=False and `IsOwnerOrHR` object logic after test failures.
- **UI:** Generated Tailwind/HTMX templates, then hand-tuned for role-gated visibility (salary hidden) and `hx-target` partial swaps.
- **Tasks:** Delegated ReportLab/openpyxl export logic; tested eager fallback without Redis.

## Key Prompts (summarized)

- “Create Django project with `config.settings` (SQLite WAL, `AUTH_USER_MODEL=accounts.User`), `config.celery`, `config.urls` separating `api/` vs UI, using `uv` and `django-htmx`.”
- “Design Employee/SalaryStructure with Decimal fields, `recompute()` that calls `TaxBracket.compute_tax(country, annual_gross)`, store gross/tax/net for fast payroll.”
- “Seed 10k employees: read `first_names.txt`/`last_names.txt` if present, else fallback lists; `bulk_create(batch 1000)` + `transaction.atomic`; tax per country; manager via dict not queries.”
- “Build DRF ViewSets using mixins, `SearchFilter` + `OrderingFilter`, permission `IsHR`/`IsOwnerOrHR`, hide salary in `to_representation` for employees viewing others.”
- “HTMX UI: base Tailwind, `hx-get` live search delay 400ms, department detail median via Python, payroll export polling `every 2s`, receipt upload to MinIO fallback.”

## Verification Loop

- After each AI-generates block: `uv run python manage.py check`, `uv run python manage.py makemigrations/migrate`, `uv run pytest -q`, manual `Client().login` + API calls for permission/tax/payroll regression.
- Fixed Decimal*float bug in percentile (→ `Decimal(str(...))`), manager N+1 (→ dict), serializer required (→ `extra_kwargs`), and CheckConstraint deprecation (→ `condition`).

## Judgment Retained

- Chose HTMX over React SPA (smaller build, server-rendered, still SPA-feel).
- Kept SQLite + WAL for 10k (Postgres would add ops); left seam for switching via `DATABASES`.
- Left out multi-currency, history, notifications — kept Celery/MinIO wiring so they’re additive, not rewrites.
