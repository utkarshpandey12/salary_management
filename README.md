# ACME Pay — Salary Management for 10,000 Employees

> TDD rewrite in progress. Skeleton setup: Django 5 + DRF + HTMX + Celery + SQLite, managed via `uv`.
> Full docs (`docs/REQUIREMENTS.md` spec, `docs/ARCHITECTURE.md`) land in later TDD steps.

## Quick Start

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
# → http://127.0.0.1:8000/accounts/login/
```

See `docs/REQUIREMENTS.md` for goal, scope, and out-of-scope.
