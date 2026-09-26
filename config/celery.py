import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("salary_management")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# fallback to eager if broker not available is handled in settings
@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
