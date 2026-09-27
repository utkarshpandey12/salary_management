from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.employees.models import Department, Employee, SalaryStructure
from apps.payroll.models import PayrollExport

User = get_user_model()


@pytest.mark.django_db
class TestPayrollUI:
    def setup_method(self):
        self.dept = Department.objects.create(name="Eng", code="ENG")
        self.hr = User.objects.create_user(username="hr", password="pass", role="HR")
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
            status="ACTIVE",
        )
        SalaryStructure.objects.create(employee=self.emp, basic_salary=Decimal("50000"))

    def _login(self, user):
        c = Client()
        c.force_login(user)
        return c

    def test_payroll_page_renders_table(self):
        resp = self._login(self.hr).get("/payroll/?month=2026-09")
        assert resp.status_code == 200
        assert b"ACME-00001" in resp.content
        assert b"Salary" in resp.content

    def test_payroll_employee_forbidden(self):
        resp = self._login(self.emp_user).get("/payroll/")
        assert resp.status_code in (302, 403)

    def test_payroll_anon_redirects(self):
        resp = Client().get("/payroll/")
        assert resp.status_code in (302, 301)

    def test_export_excel_creates_record(self):
        c = self._login(self.hr)
        resp = c.post("/payroll/exports/create/", {"month": "2026-09-01", "format": "EXCEL"})
        assert resp.status_code in (302, 200)
        exp = PayrollExport.objects.filter(format="EXCEL").first()
        assert exp is not None
        assert exp.status in ("COMPLETED", "PROCESSING", "PENDING")

    def test_export_list_page(self):
        PayrollExport.objects.create(requested_by=self.hr, month="2026-09-01", format="EXCEL")
        resp = self._login(self.hr).get("/payroll/exports/")
        assert resp.status_code == 200
