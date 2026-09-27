from django.conf import settings
from django.db import models


class PayrollExport(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    class Format(models.TextChoices):
        EXCEL = "EXCEL", "Excel"
        PDF = "PDF", "PDF"

    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    month = models.DateField(help_text="First day of month for payroll")
    format = models.CharField(max_length=10, choices=Format.choices)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    celery_task_id = models.CharField(max_length=100, blank=True)
    file = models.FileField(upload_to="payroll_exports/", blank=True, null=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"Export {self.month:%Y-%m} {self.format} by {self.requested_by} [{self.status}]"
