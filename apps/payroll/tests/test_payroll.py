import pytest
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.employees.models import Department, Employee, SalaryStructure
from apps.reimbursements.models import Reimbursement
from apps.payroll.models import PayrollExport
from apps.payroll.tasks import get_payroll_rows

User = get_user_model()

@pytest.mark.django_db
class TestPayroll(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Eng", code="ENG")
        self.hr = User.objects.create_user(username="hr", password="pass", role=User.Role.HR)
        self.emp_user = User.objects.create_user(username="emp", password="pass", role=User.Role.EMPLOYEE)
        self.emp = Employee.objects.create(employee_id="ACME-00001", first_name="John", last_name="Doe", email="john@acme.test", country="India", job_title="Engineer", department=self.dept, date_of_joining="2020-01-01", user=self.emp_user, status="ACTIVE")
        self.emp2 = Employee.objects.create(employee_id="ACME-00002", first_name="Jane", last_name="Smith", email="jane@acme.test", country="India", job_title="Engineer", department=self.dept, date_of_joining="2020-01-01", status="ACTIVE")
        SalaryStructure.objects.create(employee=self.emp, basic_salary=Decimal("50000"), house_rent_allowance=Decimal("10000"), pf_deduction=Decimal("2000"))
        SalaryStructure.objects.create(employee=self.emp2, basic_salary=Decimal("60000"), house_rent_allowance=Decimal("10000"), pf_deduction=Decimal("2000"))
        # reimbursement for current month
        Reimbursement.objects.create(employee=self.emp, title="Trip", purpose="x", amount=Decimal("1500"), expense_date="2026-09-10", status="APPROVED")
        Reimbursement.objects.create(employee=self.emp, title="Pending", purpose="x", amount=Decimal("9999"), expense_date="2026-09-10", status="PENDING")

    def test_get_payroll_rows(self):
        from datetime import date
        rows = get_payroll_rows(date(2026, 9, 1))
        self.assertEqual(len(rows), 2)
        # find emp
        r1 = [r for r in rows if r["empID"] == "ACME-00001"][0]
        # reimbursement should be 1500 only (approved)
        self.assertEqual(r1["reimbursement_amount"], Decimal("1500.00"))
        # total = salary + reimb
        self.assertEqual(r1["total_amount"], r1["salary_amount"] + Decimal("1500.00"))
        # emp2 should have 0 reimb
        r2 = [r for r in rows if r["empID"] == "ACME-00002"][0]
        self.assertEqual(r2["reimbursement_amount"], Decimal("0.00"))

    def test_payroll_api_requires_hr(self):
        c = APIClient()
        c.force_authenticate(user=self.emp_user)
        resp = c.get("/api/payroll/data/?month=2026-09")
        self.assertEqual(resp.status_code, 403)
        c.force_authenticate(user=self.hr)
        resp2 = c.get("/api/payroll/data/?month=2026-09")
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data["count"], 2)

    def test_payroll_export_celery_excel_and_pdf(self):
        # relies on eager mode
        c = APIClient()
        c.force_authenticate(user=self.hr)
        # excel
        resp = c.post("/api/payroll/exports/", {"month": "2026-09-01", "format": "EXCEL"}, format="json")
        self.assertEqual(resp.status_code, 201)
        exp = PayrollExport.objects.get(id=resp.data["id"])
        # eager: should be completed quickly
        exp.refresh_from_db()
        self.assertEqual(exp.status, "COMPLETED")
        self.assertTrue(exp.file.name.endswith(".xlsx"))
        # pdf
        resp2 = c.post("/api/payroll/exports/", {"month": "2026-09-01", "format": "PDF"}, format="json")
        self.assertEqual(resp2.status_code, 201)
        exp2 = PayrollExport.objects.get(id=resp2.data["id"])
        exp2.refresh_from_db()
        self.assertEqual(exp2.status, "COMPLETED")
        self.assertTrue(exp2.file.name.endswith(".pdf"))

    def test_payroll_recomputes_after_salary_edit(self):
        from datetime import date
        rows_before = get_payroll_rows(date(2026, 9, 1))
        r_before = [r for r in rows_before if r["empID"] == "ACME-00001"][0]["total_amount"]
        # increase salary
        sal = self.emp.salary
        sal.basic_salary = Decimal("80000")
        sal.save()
        rows_after = get_payroll_rows(date(2026, 9, 1))
        r_after = [r for r in rows_after if r["empID"] == "ACME-00001"][0]["total_amount"]
        self.assertGreater(r_after, r_before)

    def test_inactive_not_in_payroll(self):
        self.emp2.status = "INACTIVE"
        self.emp2.save()
        from datetime import date
        rows = get_payroll_rows(date(2026, 9, 1))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["empID"], "ACME-00001")
