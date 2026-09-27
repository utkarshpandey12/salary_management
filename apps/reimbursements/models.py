from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def reimbursement_upload_to(instance, filename):
    return f"reimbursements/{instance.employee.employee_id}/{filename}"


class Reimbursement(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    employee = models.ForeignKey(
        "employees.Employee", on_delete=models.CASCADE, related_name="reimbursements"
    )
    title = models.CharField(max_length=200)
    purpose = models.TextField(blank=True, help_text="Reason for reimbursement")
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    expense_date = models.DateField()
    receipt = models.FileField(
        upload_to=reimbursement_upload_to,
        blank=True,
        null=True,
        help_text="Bill/Receipt PDF or image",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_reimbursements",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["employee", "status"]),
            models.Index(fields=["expense_date"]),
        ]

    def __str__(self):
        return f"{self.title} — {self.employee.employee_id} — {self.amount} ({self.status})"

    def clean(self):
        super().clean()
        if self.expense_date and self.expense_date > timezone.now().date():
            raise ValidationError({"expense_date": "Expense date cannot be in the future."})

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING
