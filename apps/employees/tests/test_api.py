from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.employees.models import Department, Employee, SalaryStructure

User = get_user_model()


@pytest.mark.django_db
class TestEmployeeAPI(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Engineering", code="ENG")
        self.dept2 = Department.objects.create(name="Sales", code="SAL")
        self.hr = User.objects.create_user(username="hr", password="pass", role=User.Role.HR)
        self.emp_user = User.objects.create_user(
            username="emp", password="pass", role=User.Role.EMPLOYEE
        )
        self.emp = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="John",
            last_name="Doe",
            email="john@acme.test",
            country="India",
            job_title="Engineer",
            department=self.dept,
            date_of_joining="2020-01-01",
            user=self.emp_user,
        )
        SalaryStructure.objects.create(employee=self.emp, basic_salary=Decimal("50000"))
        self.other = Employee.objects.create(
            employee_id="ACME-00002",
            first_name="Jane",
            last_name="Smith",
            email="jane@acme.test",
            country="USA",
            job_title="Engineer",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        SalaryStructure.objects.create(employee=self.other, basic_salary=Decimal("60000"))

    def test_hr_can_list_employees(self):
        c = APIClient()
        c.force_authenticate(user=self.hr)
        resp = c.get("/api/employees/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 2)

    def test_employee_can_list_but_salary_hidden_for_others(self):
        c = APIClient()
        c.force_authenticate(user=self.emp_user)
        resp = c.get(f"/api/employees/{self.other.id}/")
        self.assertEqual(resp.status_code, 200)
        # salary should be absent for other employee
        self.assertNotIn("salary", resp.data)
        # own salary visible
        resp2 = c.get(f"/api/employees/{self.emp.id}/")
        self.assertEqual(resp2.status_code, 200)
        self.assertIn("salary", resp2.data)

    def test_hr_can_create_employee(self):
        c = APIClient()
        c.force_authenticate(user=self.hr)
        payload = {
            "employee_id": "ACME-99999",
            "first_name": "New",
            "last_name": "Guy",
            "email": "new@acme.test",
            "country": "India",
            "job_title": "Designer",
            "department": self.dept.id,
            "date_of_joining": "2022-01-01",
        }
        resp = c.post("/api/employees/", payload, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Employee.objects.filter(employee_id="ACME-99999").exists())

    def test_employee_cannot_create(self):
        c = APIClient()
        c.force_authenticate(user=self.emp_user)
        payload = {
            "employee_id": "ACME-99998",
            "first_name": "Fail",
            "last_name": "Guy",
            "email": "fail@acme.test",
            "country": "India",
            "job_title": "Designer",
            "department": self.dept.id,
            "date_of_joining": "2022-01-01",
        }
        resp = c.post("/api/employees/", payload, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_employee_can_update_own_limited_fields(self):
        c = APIClient()
        c.force_authenticate(user=self.emp_user)
        # try to update own phone (allowed)
        resp = c.patch(f"/api/employees/{self.emp.id}/", {"phone": "+91-9999999999"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.phone, "+91-9999999999")
        # try to update job_title (not allowed) -> should be ignored or not changed
        resp2 = c.patch(f"/api/employees/{self.emp.id}/", {"job_title": "CEO"}, format="json")
        self.assertEqual(resp2.status_code, 200)
        self.emp.refresh_from_db()
        self.assertNotEqual(self.emp.job_title, "CEO")

    def test_hr_can_update_salary_and_recompute(self):
        c = APIClient()
        c.force_authenticate(user=self.hr)
        sal = self.emp.salary
        old_net = sal.net_in_hand
        resp = c.patch(
            f"/api/employees/{self.emp.id}/salary/", {"basic_salary": "90000.00"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        sal.refresh_from_db()
        self.assertNotEqual(sal.net_in_hand, old_net)
        self.assertEqual(sal.basic_salary, Decimal("90000.00"))

    def test_employee_cannot_update_other_salary(self):
        c = APIClient()
        c.force_authenticate(user=self.emp_user)
        resp = c.patch(
            f"/api/employees/{self.other.id}/salary/", {"basic_salary": "90000.00"}, format="json"
        )
        self.assertIn(resp.status_code, (403, 404))

    def test_search_by_employee_id(self):
        c = APIClient()
        c.force_authenticate(user=self.hr)
        resp = c.get("/api/employees/?employee_id=ACME-00001")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["employee_id"], "ACME-00001")

    def test_analytics_requires_hr(self):
        c = APIClient()
        c.force_authenticate(user=self.emp_user)
        resp = c.get("/api/employees/analytics/")
        self.assertEqual(resp.status_code, 403)
        c.force_authenticate(user=self.hr)
        resp2 = c.get("/api/employees/analytics/")
        self.assertEqual(resp2.status_code, 200)
        self.assertIn("overall", resp2.data)
        self.assertIn("by_country", resp2.data)

    def test_analytics_avg_by_country_title(self):
        c = APIClient()
        c.force_authenticate(user=self.hr)
        resp = c.get("/api/employees/analytics/?country=India&job_title=Engineer")
        self.assertEqual(resp.status_code, 200)
        # should return specific_avg
        self.assertIsNotNone(resp.data["overall"]["specific_avg_job_country"])

    def test_department_filter(self):
        # create employee in Sales
        e2 = Employee.objects.create(
            employee_id="ACME-00003",
            first_name="Bob",
            last_name="Sales",
            email="bob@acme.test",
            country="India",
            job_title="Sales Executive",
            department=self.dept2,
            date_of_joining="2021-01-01",
        )
        SalaryStructure.objects.create(employee=e2, basic_salary=Decimal("50000"))
        c = APIClient()
        c.force_authenticate(user=self.hr)
        resp = c.get(f"/api/employees/?department={self.dept2.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
