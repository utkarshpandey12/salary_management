from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.employees.models import Department, Employee, SalaryStructure

User = get_user_model()


@pytest.mark.django_db
class TestFullTemplates:
    def setup_method(self):
        self.dept = Department.objects.create(name="Eng", code="ENG")
        self.hr = User.objects.create_user(username="hr", password="pass", role="HR")
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
        SalaryStructure.objects.create(
            employee=self.emp,
            basic_salary=Decimal("50000"),
            house_rent_allowance=Decimal("10000"),
        )

    def _login(self):
        c = Client()
        c.force_login(self.hr)
        return c

    def test_base_has_tailwind_and_htmx(self):
        resp = self._login().get("/employees/")
        assert b"tailwindcss" in resp.content
        assert b"htmx.org" in resp.content

    def test_base_has_nav_links(self):
        resp = self._login().get("/employees/")
        for link in [b"Employees", b"Departments", b"Analytics", b"Payroll", b"Reimbursements"]:
            assert link in resp.content

    def test_employee_list_has_live_search(self):
        resp = self._login().get("/employees/")
        assert b"hx-get" in resp.content
        assert b"ACME-00001" in resp.content

    def test_employee_detail_full_salary_breakdown(self):
        resp = self._login().get("/employees/ACME-00001/")
        for s in [b"House (HRA)", b"Gross", b"In-Hand", b"Tax (bracket)"]:
            assert s in resp.content

    def test_employee_detail_quick_lookup(self):
        resp = self._login().get("/employees/ACME-00001/")
        assert b"Quick lookup by ID" in resp.content

    def test_department_list_shows_max(self):
        resp = self._login().get("/departments/")
        assert b"Max" in resp.content

    def test_analytics_breakdowns(self):
        resp = self._login().get("/analytics/")
        for s in [b"By Country", b"By Department", b"By Job Title", b"Total payroll"]:
            assert s in resp.content

    def test_dashboard_pending_queue(self):
        resp = self._login().get("/")
        assert b"Pending Reimbursements" in resp.content or b"Reimbursement" in resp.content
