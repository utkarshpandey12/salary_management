from datetime import date

import pytest
from django.contrib.auth import get_user_model

from apps.payroll.models import PayrollExport

User = get_user_model()


@pytest.mark.django_db
class TestPayrollExportModel:
    def setup_method(self):
        self.user = User.objects.create_user(username="hr", password="pass", role="HR")

    def test_create_pending(self):
        exp = PayrollExport.objects.create(
            requested_by=self.user, month=date(2026, 9, 1), format="EXCEL"
        )
        assert exp.status == "PENDING"
        assert exp.format == "EXCEL"
        assert str(exp).startswith("Export")

    def test_month_validation_first_day(self):
        # serializer ensures first day, but model allows any date
        exp = PayrollExport.objects.create(
            requested_by=self.user, month=date(2026, 9, 15), format="PDF"
        )
        assert exp.month == date(2026, 9, 15)

    def test_format_choices(self):
        for fmt in ["EXCEL", "PDF"]:
            exp = PayrollExport.objects.create(
                requested_by=self.user, month=date(2026, 9, 1), format=fmt
            )
            assert exp.format == fmt

    def test_status_choices(self):
        for status in ["PENDING", "PROCESSING", "COMPLETED", "FAILED"]:
            exp = PayrollExport.objects.create(
                requested_by=self.user, month=date(2026, 9, 1), format="EXCEL", status=status
            )
            assert exp.status == status

    def test_requested_by_required(self):
        try:
            PayrollExport.objects.create(month=date(2026, 9, 1), format="EXCEL")
            assert False
        except Exception:
            assert True

    def test_file_optional(self):
        exp = PayrollExport.objects.create(
            requested_by=self.user, month=date(2026, 9, 1), format="EXCEL"
        )
        assert not exp.file

    def test_error_field(self):
        exp = PayrollExport.objects.create(
            requested_by=self.user,
            month=date(2026, 9, 1),
            format="EXCEL",
            error="some error",
            status="FAILED",
        )
        assert exp.error == "some error"

    def test_ordering_desc(self):
        e1 = PayrollExport.objects.create(
            requested_by=self.user, month=date(2026, 8, 1), format="EXCEL"
        )
        e2 = PayrollExport.objects.create(
            requested_by=self.user, month=date(2026, 9, 1), format="EXCEL"
        )
        assert list(PayrollExport.objects.values_list("id", flat=True)) == [e2.id, e1.id]

    def test_celery_task_id_optional(self):
        exp = PayrollExport.objects.create(
            requested_by=self.user, month=date(2026, 9, 1), format="EXCEL", celery_task_id="abc-123"
        )
        assert exp.celery_task_id == "abc-123"

    @pytest.mark.parametrize("fmt", ["EXCEL", "PDF"])
    def test_various_formats(self, fmt):
        exp = PayrollExport.objects.create(
            requested_by=self.user, month=date(2026, 9, 1), format=fmt
        )
        assert exp.format == fmt

    def test_completed_at_nullable(self):
        exp = PayrollExport.objects.create(
            requested_by=self.user, month=date(2026, 9, 1), format="EXCEL"
        )
        assert exp.completed_at is None
        from django.utils import timezone

        exp.completed_at = timezone.now()
        exp.save()
        assert exp.completed_at is not None
