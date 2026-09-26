#!/bin/bash
set -e

# Entrypoint for lean Docker image — runs migrations, optional seed, then server + celery
# Usage:
#   docker run -p 8000:8000 -e DJANGO_SECRET_KEY=... ghcr.io/...:latest            # server (celery eager)
#   docker run ... ghcr.io/...:latest celery                                          # only celery worker
#   docker run -e CELERY_ALWAYS_EAGER=0 -e CELERY_BROKER_URL=redis://... ghcr.io/...:latest server
#   docker run ... ghcr.io/...:latest bash

ROLE="${1:-server}"
echo "[entrypoint] ROLE=$ROLE DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE"

# Ensure DB migrations
echo "[entrypoint] migrate..."
python manage.py migrate --no-input

# Auto-seed if empty (idempotent, respects --count if env SEED_COUNT set)
EMP_COUNT=$(python -c "import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup();from apps.employees.models import Employee;print(Employee.objects.count())" 2>/dev/null || echo "0")
if [ "$EMP_COUNT" = "0" ] && [ "${AUTO_SEED:-1}" = "1" ]; then
  echo "[entrypoint] seeding ${SEED_COUNT:-10000} employees..."
  python manage.py seed_employees --count "${SEED_COUNT:-10000}" || echo "[entrypoint] seed failed, continuing"
else
  echo "[entrypoint] employees=$EMP_COUNT, skipping seed (AUTO_SEED=$AUTO_SEED)"
fi

# Static collection for prod (ignore errors in dev)
if [ "${DJANGO_DEBUG:-1}" = "0" ]; then
  python manage.py collectstatic --no-input || true
fi

case "$ROLE" in
  server)
    # If Celery is async (eager=0) and broker reachable, start worker in background, then server foreground
    if [ "${CELERY_ALWAYS_EAGER:-1}" = "0" ] && [ -n "${CELERY_BROKER_URL}" ]; then
      echo "[entrypoint] starting celery worker (queue=payroll) in background..."
      celery -A config worker -l info -Q payroll --concurrency=2 -n payroll@%h &
      CELERY_PID=$!
      echo "[entrypoint] celery pid $CELERY_PID"
      # trap to forward SIGTERM
      trap "kill $CELERY_PID; wait $CELERY_PID; exit" TERM INT
    fi
    echo "[entrypoint] starting django server on 0.0.0.0:8000..."
    # Prefer gunicorn if available, else runserver
    if python -c "import gunicorn" 2>/dev/null; then
      exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 2 --timeout 60 --access-logfile -
    else
      exec python manage.py runserver 0.0.0.0:8000
    fi
    ;;
  celery)
    echo "[entrypoint] starting celery worker only (queue=payroll)..."
    exec celery -A config worker -l info -Q payroll --concurrency=4 -n payroll@%h
    ;;
  celery-beat)
    exec celery -A config beat -l info
    ;;
  bash|sh|shell)
    exec /bin/bash
    ;;
  migrate)
    echo "[entrypoint] migrate done"
    ;;
  *)
    # arbitrary command
    exec "$@"
    ;;
esac
