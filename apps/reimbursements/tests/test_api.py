import pytest
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Department, Employee, SalaryStructure
from apps.reimbursements.models import Reimbursement

User = get_user_model()

@pytest.mark.django_db
class TestReimbursementAPI(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Eng", code="ENG")
        self.hr = User.objects.create_user(username="hr", password="pass", role=User.Role.HR)
        self.emp_user = User.objects.create_user(username="emp", password="pass", role=User.Role.EMPLOYEE)
        self.emp = Employee.objects.create(employee_id="ACME-00001", first_name="John", last_name="Doe", email="john@acme.test", country="India", job_title="Engineer", department=self.dept, date_of_joining="2020-01-01", user=self.emp_user)
        SalaryStructure.objects.create(employee=self.emp, basic_salary=Decimal("50000"))
        self.other_emp = Employee.objects.create(employee_id="ACME-00002", first_name="Jane", last_name="Smith", email="jane@acme.test", country="India", job_title="Engineer", department=self.dept, date_of_joining="2020-01-01")
        SalaryStructure.objects.create(employee=self.other_emp, basic_salary=Decimal("50000"))

    def test_employee_create_reimbursement(self):
        c = APIClient()
        c.force_authenticate(user=self.emp_user)
        resp = c.post("/api/reimbursements/", {"title": "Travel", "purpose": "Visit", "amount": "1000.00", "expense_date": "2026-09-10"}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Reimbursement.objects.count(), 1)
        r = Reimbursement.objects.first()
        self.assertEqual(r.employee, self.emp)
        self.assertEqual(r.status, "PENDING")

    def test_employee_cannot_see_others_reimbursement(self):
        Reimbursement.objects.create(employee=self.other_emp, title="Other", purpose="x", amount=Decimal("500"), expense_date="2026-09-10")
        c = APIClient()
        c.force_authenticate(user=self.emp_user)
        resp = c.get("/api/reimbursements/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 0)  # only own

    def test_hr_sees_all_and_can_approve(self):
        r = Reimbursement.objects.create(employee=self.emp, title="Trip", purpose="x", amount=Decimal("800"), expense_date="2026-09-10")
        c = APIClient()
        c.force_authenticate(user=self.hr)
        resp = c.get("/api/reimbursements/")
        self.assertEqual(resp.data["count"], 1)
        # approve
        resp2 = c.post(f"/api/reimbursements/{r.id}/approve/", format="json")
        self.assertEqual(resp2.status_code, 200)
        r.refresh_from_db()
        self.assertEqual(r.status, "APPROVED")
        self.assertEqual(r.reviewed_by, self.hr)

    def test_hr_can_reject(self):
        r = Reimbursement.objects.create(employee=self.emp, title="Trip", purpose="x", amount=Decimal("800"), expense_date="2026-09-10")
        c = APIClient()
        c.force_authenticate(user=self.hr)
        resp = c.post(f"/api/reimbursements/{r.id}/reject/", format="json")
        self.assertEqual(resp.status_code, 200)
        r.refresh_from_db()
        self.assertEqual(r.status, "REJECTED")

    def test_employee_cannot_approve(self):
        r = Reimbursement.objects.create(employee=self.emp, title="Trip", purpose="x", amount=Decimal("800"), expense_date="2026-09-10")
        c = APIClient()
        c.force_authenticate(user=self.emp_user)
        resp = c.post(f"/api/reimbursements/{r.id}/approve/", format="json")
        self.assertEqual(resp.status_code, 403)

    def test_double_approve_fails(self):
        r = Reimbursement.objects.create(employee=self.emp, title="Trip", purpose="x", amount=Decimal("800"), expense_date="2026-09-10", status="APPROVED", reviewed_by=self.hr)
        c = APIClient()
        c.force_authenticate(user=self.hr)
        resp = c.post(f"/api/reimbursements/{r.id}/approve/", format="json")
        self.assertEqual(resp.status_code, 400)

    def test_hr_create_for_employee(self):
        c = APIClient()
        c.force_authenticate(user=self.hr)
        resp = c.post("/api/reimbursements/", {"employee": self.other_emp.id, "title": "HR Created", "purpose": "test", "amount": "2000.00", "expense_date": "2026-09-11"}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Reimbursement.objects.get(id=resp.data["id"]).employee, self.other_emp)
