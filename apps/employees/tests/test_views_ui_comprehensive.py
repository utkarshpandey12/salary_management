from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.employees.models import Department, Employee, SalaryStructure

User = get_user_model()


@pytest.mark.django_db
class TestEmployeeUIBusinessRules:
    def setup_method(self):
        self.dept = Department.objects.create(name="Eng", code="ENG")
        self.hr = User.objects.create_user(username="hr", password="pass", role="HR")
        self.emp_user = User.objects.create_user(username="emp", password="pass", role="EMPLOYEE")
        self.other_user = User.objects.create_user(
            username="other", password="pass", role="EMPLOYEE"
        )
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
        self.other = Employee.objects.create(
            employee_id="ACME-00002",
            first_name="Jane",
            last_name="Smith",
            email="jane@a.com",
            country="USA",
            job_title="Designer",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        SalaryStructure.objects.create(employee=self.other, basic_salary=Decimal("60000"))

    def _login(self, user):
        c = Client()
        c.force_login(user)
        return c

    def test_hr_dashboard_shows_totals(self):
        c = self._login(self.hr)
        resp = c.get("/")
        assert resp.status_code == 200
        assert b"Total Employees" in resp.content or b"HR Dashboard" in resp.content

    def test_employee_dashboard_shows_my_details(self):
        c = self._login(self.emp_user)
        resp = c.get("/")
        assert resp.status_code == 200
        assert b"My Dashboard" in resp.content

    def test_employee_dashboard_without_profile_shows_message(self):
        c = self._login(self.other_user)
        resp = c.get("/")
        assert b"No employee profile" in resp.content or b"My Dashboard" in resp.content

    def test_employee_list_search(self):
        c = self._login(self.hr)
        resp = c.get("/employees/?q=ACME-00001")
        assert resp.status_code == 200
        assert b"ACME-00001" in resp.content

    def test_employee_list_filter_department(self):
        c = self._login(self.hr)
        resp = c.get(f"/employees/?department={self.dept.id}")
        assert resp.status_code == 200

    def test_employee_list_filter_country(self):
        c = self._login(self.hr)
        resp = c.get("/employees/?country=India")
        assert b"India" in resp.content

    def test_employee_list_filter_job_title(self):
        c = self._login(self.hr)
        resp = c.get("/employees/?job_title=Eng")
        assert resp.status_code == 200

    def test_employee_list_pagination(self):
        # create many
        for i in range(30):
            e = Employee.objects.create(
                employee_id=f"ACME-00{i + 100:03d}",
                first_name="A",
                last_name="B",
                email=f"a{i}@a.com",
                country="India",
                job_title="Eng",
                department=self.dept,
                date_of_joining="2020-01-01",
            )
            SalaryStructure.objects.create(employee=e, basic_salary=Decimal("40000"))
        c = self._login(self.hr)
        resp = c.get("/employees/?page=2")
        assert resp.status_code == 200

    def test_employee_list_htmx_partial(self):
        c = self._login(self.hr)
        resp = c.get("/employees/", HTTP_HX_REQUEST="true")
        # should return partial table, not full layout
        assert resp.status_code == 200
        assert b"<table" in resp.content

    def test_employee_detail_hr_can_view_salary(self):
        c = self._login(self.hr)
        resp = c.get(f"/employees/{self.other.employee_id}/")
        assert b"Salary Structure" in resp.content
        assert b"Basic Salary" in resp.content

    def test_employee_detail_employee_can_view_own_salary(self):
        c = self._login(self.emp_user)
        resp = c.get(f"/employees/{self.emp.employee_id}/")
        assert b"Salary Structure" in resp.content

    def test_employee_detail_employee_cannot_view_other_salary(self):
        c = self._login(self.emp_user)
        resp = c.get(f"/employees/{self.other.employee_id}/")
        # should not contain salary, no locked card
        assert b"Salary Structure" not in resp.content
        assert b"Salary hidden" not in resp.content

    def test_employee_detail_manager_link_clickable(self):
        # ensure manager link present
        mgr = self.other
        self.emp.manager = mgr
        self.emp.save()
        c = self._login(self.hr)
        resp = c.get(f"/employees/{self.emp.employee_id}/")
        assert mgr.employee_id.encode() in resp.content
        assert f"/employees/{mgr.employee_id}/".encode() in resp.content
        # employee viewing same should also see link
        c2 = self._login(self.emp_user)
        resp2 = c2.get(f"/employees/{self.emp.employee_id}/")
        assert mgr.employee_id.encode() in resp2.content

    def test_employee_create_hr_only(self):
        c = self._login(self.hr)
        resp = c.get("/employees/create/")
        assert resp.status_code == 200
        c2 = self._login(self.emp_user)
        resp2 = c2.get("/employees/create/")
        assert resp2.status_code in (302, 403)

    def test_employee_update_hr_can_edit(self):
        c = self._login(self.hr)
        resp = c.get(f"/employees/{self.emp.employee_id}/edit/")
        assert resp.status_code == 200

    def test_employee_update_employee_can_edit_own(self):
        c = self._login(self.emp_user)
        resp = c.get(f"/employees/{self.emp.employee_id}/edit/")
        assert resp.status_code == 200
        # limited fields
        assert b"phone" in resp.content.lower()

    def test_employee_update_employee_cannot_edit_other(self):
        c = self._login(self.emp_user)
        resp = c.get(f"/employees/{self.other.employee_id}/edit/")
        assert resp.status_code in (302, 403)

    def test_employee_update_employee_limited_fields(self):
        c = self._login(self.emp_user)
        resp = c.post(
            f"/employees/{self.emp.employee_id}/edit/",
            {"phone": "+91-999", "address": "New Addr", "city": "Mumbai"},
        )
        assert resp.status_code in (302, 200)
        self.emp.refresh_from_db()
        assert self.emp.phone == "+91-999"

    def test_employee_update_employee_cannot_change_job_title(self):
        c = self._login(self.emp_user)
        orig = self.emp.job_title
        c.post(
            f"/employees/{self.emp.employee_id}/edit/",
            {"phone": "123", "address": "a", "city": "c", "job_title": "CEO"},
        )
        self.emp.refresh_from_db()
        assert self.emp.job_title == orig

    def test_salary_edit_hr_only(self):
        c = self._login(self.hr)
        resp = c.get(f"/employees/{self.emp.employee_id}/salary/edit/")
        assert resp.status_code == 200
        c2 = self._login(self.emp_user)
        resp2 = c2.get(f"/employees/{self.emp.employee_id}/salary/edit/")
        assert resp2.status_code in (302, 403)

    def test_salary_edit_recomputes(self):
        c = self._login(self.hr)
        old = self.emp.salary.net_in_hand
        c.post(
            f"/employees/{self.emp.employee_id}/salary/edit/",
            {
                "basic_salary": "90000",
                "house_rent_allowance": "10000",
                "dearness_allowance": "0",
                "transport_allowance": "0",
                "telephone_allowance": "0",
                "special_allowance": "0",
                "pf_deduction": "0",
                "professional_tax": "0",
            },
        )
        self.emp.salary.refresh_from_db()
        assert self.emp.salary.net_in_hand != old

    def test_department_list_hr_shows_salary(self):
        c = self._login(self.hr)
        resp = c.get("/departments/")
        assert b"Avg net" in resp.content or b"Avg" in resp.content

    def test_department_list_employee_hides_salary(self):
        c = self._login(self.emp_user)
        resp = c.get("/departments/")
        assert b"Avg net" not in resp.content
        assert b"Members" in resp.content

    def test_department_detail_hr_shows_stats(self):
        c = self._login(self.hr)
        resp = c.get(f"/departments/{self.dept.id}/")
        assert b"Median" in resp.content
        assert b"Net" in resp.content

    def test_department_detail_employee_hides_stats(self):
        c = self._login(self.emp_user)
        resp = c.get(f"/departments/{self.dept.id}/")
        assert b"Median" not in resp.content
        assert b"confidential" in resp.content.lower()
        # Net column hidden
        assert resp.content.count(b"Net</th>") == 0

    def test_analytics_hr_accessible(self):
        c = self._login(self.hr)
        assert c.get("/analytics/").status_code == 200

    def test_analytics_employee_redirect(self):
        c = self._login(self.emp_user)
        resp = c.get("/analytics/")
        assert resp.status_code in (302, 403)

    def test_login_required_redirect(self):
        assert Client().get("/employees/").status_code in (302, 301)

    @pytest.mark.parametrize("status", ["ACTIVE", "INACTIVE", "ON_LEAVE"])
    def test_employee_status_display(self, status):
        self.emp.status = status
        self.emp.save()
        c = self._login(self.hr)
        resp = c.get(f"/employees/{self.emp.employee_id}/")
        assert status.encode() in resp.content
