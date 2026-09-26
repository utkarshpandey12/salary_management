# syntax=docker/dockerfile:1.6
# Lean multi-stage + uv cache, no dev deps in runtime
ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.9

# ---------- builder ----------
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm AS builder
ARG UV_VERSION
WORKDIR /app

# Enable uv cache via BuildKit
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock README.md ./

# Install prod deps into .venv (frozen, no dev)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Copy full source then install project itself
COPY config ./config
COPY apps ./apps
COPY templates ./templates
COPY static ./static
COPY manage.py ./
COPY first_names.txt last_names.txt* ./
# media is runtime volume, skip

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------- runtime ----------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

# Minimal OS deps: libpq not needed for sqlite, but need curl for healthcheck, and libexpat for xml
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r app && useradd -r -g app -m app

# Copy venv and source from builder (chown for lean)
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/config /app/config
COPY --from=builder --chown=app:app /app/apps /app/apps
COPY --from=builder --chown=app:app /app/templates /app/templates
COPY --from=builder --chown=app:app /app/static /app/static
COPY --chown=app:app manage.py pyproject.toml uv.lock first_names.txt last_names.txt ./
COPY --chown=app:app entrypoint.sh ./

# Create media/staticfiles dirs as app
RUN mkdir -p /app/media /app/staticfiles && chown -R app:app /app

USER app
EXPOSE 8000

# Healthcheck for k8s / compose-free deploys
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/accounts/login/ | grep -q "ACME" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
# Default: runserver + celery via entrypoint; override with `docker run ... celery` or `gunicorn`
CMD ["server"]
