import pytest
from decimal import Decimal

from django.contrib.auth import get_user_model

from apps.employees.models import Department, Employee, SalaryStructure

User = get_user_model()


@pytest.mark.django_db
class TestSalaryHistoryAudit:
    def setup_method(self):
        self.dept = Department.objects.create(name="Eng", code="ENG")
        self.emp = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="John",
            last_name="Doe",
            email="john@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        self.salary = SalaryStructure.objects.create(
            employee=self.emp, basic_salary=Decimal("50000")
        )

    def test_history_model_exists(self):
        from apps.employees.models import SalaryHistory

        assert SalaryHistory is not None

    def test_update_creates_history_entry(self):
        from apps.employees.models import SalaryHistory

        before = SalaryHistory.objects.filter(employee=self.emp).count()
        self.salary.basic_salary = Decimal("70000")
        self.salary.save()
        after = SalaryHistory.objects.filter(employee=self.emp).count()
        assert after == before + 1

    def test_history_stores_old_and_new(self):
        from apps.employees.models import SalaryHistory

        old_basic = self.salary.basic_salary
        old_net = self.salary.net_in_hand
        self.salary.basic_salary = Decimal("80000")
        self.salary.save()
        entry = SalaryHistory.objects.filter(employee=self.emp).latest("created_at")
        assert entry.old_basic == old_basic
        assert entry.new_basic == Decimal("80000")
        assert entry.old_net == old_net
        assert entry.new_net == self.salary.net_in_hand

    def test_no_history_when_nothing_changed(self):
        from apps.employees.models import SalaryHistory

        before = SalaryHistory.objects.filter(employee=self.emp).count()
        self.salary.save()  # no field change
        after = SalaryHistory.objects.filter(employee=self.emp).count()
        assert after == before

    def test_history_ordering_and_employee_link(self):
        from apps.employees.models import SalaryHistory

        self.salary.basic_salary = Decimal("60000")
        self.salary.save()
        self.salary.basic_salary = Decimal("65000")
        self.salary.save()
        qs = SalaryHistory.objects.filter(employee=self.emp).order_by("-created_at")
        assert qs.count() >= 2
        assert qs[0].created_at >= qs[1].created_at
        assert all(h.employee_id == self.emp.id for h in qs[:2])
