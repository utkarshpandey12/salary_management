from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.employees.models import Department, Employee, SalaryStructure
from apps.reimbursements.forms import ReimbursementForm
from apps.reimbursements.models import Reimbursement

User = get_user_model()


@pytest.mark.django_db
class TestFutureExpenseDateRejected:
    def setup_method(self):
        self.dept = Department.objects.create(name="Eng", code="ENG")
        self.emp_user = User.objects.create_user(username="emp", password="pass", role="EMPLOYEE")
        self.emp = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="John",
            last_name="Doe",
            email="john@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
            user=self.emp_user,
        )
        SalaryStructure.objects.create(employee=self.emp, basic_salary=Decimal("50000"))

    def test_model_rejects_future_expense_date(self):
        tomorrow = timezone.now().date() + timedelta(days=1)
        r = Reimbursement(
            employee=self.emp,
            title="Future trip",
            amount=Decimal("100"),
            expense_date=tomorrow,
        )
        with pytest.raises(ValidationError):
            r.full_clean()

    def test_api_rejects_future_expense_date(self):
        tomorrow = (timezone.now().date() + timedelta(days=5)).isoformat()
        c = APIClient()
        c.force_authenticate(user=self.emp_user)
        resp = c.post(
            "/api/reimbursements/",
            {
                "title": "Future",
                "purpose": "x",
                "amount": "100.00",
                "expense_date": tomorrow,
            },
            format="json",
        )
        assert resp.status_code == 400
        assert "expense_date" in resp.data

    def test_form_rejects_future_expense_date(self):
        tomorrow = timezone.now().date() + timedelta(days=2)
        form = ReimbursementForm(
            data={
                "title": "Future",
                "purpose": "x",
                "amount": "100",
                "expense_date": tomorrow.isoformat(),
            },
            user=self.emp_user,
        )
        assert not form.is_valid()
        assert "expense_date" in form.errors

    def test_today_expense_date_allowed(self):
        today = timezone.now().date()
        r = Reimbursement(
            employee=self.emp,
            title="Today",
            amount=Decimal("100"),
            expense_date=today,
        )
        r.full_clean()  # should not raise
        assert True

    def test_far_future_rejected_with_message(self):
        far = timezone.now().date() + timedelta(days=365)
        r = Reimbursement(
            employee=self.emp,
            title="Far",
            amount=Decimal("100"),
            expense_date=far,
        )
        try:
            r.full_clean()
            raise AssertionError("future date should be rejected")
        except ValidationError as e:
            assert "expense_date" in e.message_dict
