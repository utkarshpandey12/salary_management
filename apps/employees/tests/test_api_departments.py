from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.employees.models import Department, Employee, SalaryStructure

User = get_user_model()


@pytest.mark.django_db
class TestDepartmentAPI:
    def setup_method(self):
        self.dept = Department.objects.create(name="Engineering", code="ENG")
        self.dept2 = Department.objects.create(name="Sales", code="SAL")
        self.hr = User.objects.create_user(username="hr", password="pass", role="HR")
        self.emp = User.objects.create_user(username="emp", password="pass", role="EMPLOYEE")
        self.e1 = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="John",
            last_name="Doe",
            email="john@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        SalaryStructure.objects.create(employee=self.e1, basic_salary=Decimal("50000"))

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    def test_list_departments_authenticated(self):
        assert self._client(self.hr).get("/api/employees/departments/").status_code == 200
        assert self._client(self.emp).get("/api/employees/departments/").status_code == 200

    def test_anon_denied(self):
        assert APIClient().get("/api/employees/departments/").status_code in (401, 403)

    def test_create_hr_success(self):
        resp = self._client(self.hr).post(
            "/api/employees/departments/",
            {"name": "NewDept", "code": "NEW", "description": "desc"},
            format="json",
        )
        assert resp.status_code == 201
        assert Department.objects.filter(code="NEW").exists()

    def test_create_employee_forbidden(self):
        resp = self._client(self.emp).post(
            "/api/employees/departments/", {"name": "X", "code": "X"}, format="json"
        )
        assert resp.status_code == 403

    def test_retrieve_department(self):
        resp = self._client(self.hr).get(f"/api/employees/departments/{self.dept.id}/")
        assert resp.status_code == 200
        assert resp.data["name"] == "Engineering"

    def test_employee_count_annotation(self):
        resp = self._client(self.hr).get("/api/employees/departments/")
        data = {r["code"]: r for r in resp.data["results"]}
        assert data["ENG"]["employee_count"] == 1
        assert data["SAL"]["employee_count"] == 0

    def test_search_by_name(self):
        resp = self._client(self.hr).get("/api/employees/departments/?search=Engineering")
        assert resp.data["count"] == 1

    def test_update_hr_success(self):
        resp = self._client(self.hr).patch(
            f"/api/employees/departments/{self.dept.id}/", {"description": "updated"}, format="json"
        )
        assert resp.status_code == 200
        self.dept.refresh_from_db()
        assert self.dept.description == "updated"

    def test_update_employee_forbidden(self):
        resp = self._client(self.emp).patch(
            f"/api/employees/departments/{self.dept.id}/", {"description": "x"}, format="json"
        )
        assert resp.status_code == 403

    def test_list_ordering_by_name(self):
        Department.objects.create(name="ADept", code="A")
        resp = self._client(self.hr).get("/api/employees/departments/?ordering=name")
        names = [r["name"] for r in resp.data["results"]]
        assert names == sorted(names)

    def test_duplicate_name_fails(self):
        resp = self._client(self.hr).post(
            "/api/employees/departments/", {"name": "Engineering", "code": "ENG2"}, format="json"
        )
        assert resp.status_code == 400

    def test_duplicate_code_fails(self):
        resp = self._client(self.hr).post(
            "/api/employees/departments/", {"name": "New", "code": "ENG"}, format="json"
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("code", ["ENG", "SAL", "MKT"])
    def test_various_codes(self, code):
        if code not in ["ENG", "SAL"]:
            Department.objects.create(name=f"Dept{code}", code=code)
        resp = self._client(self.hr).get("/api/employees/departments/")
        assert any(r["code"] == code for r in resp.data["results"])

    def test_retrieve_not_found(self):
        resp = self._client(self.hr).get("/api/employees/departments/99999/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestTaxBracketAPI:
    def setup_method(self):
        self.hr = User.objects.create_user(username="hr", password="pass", role="HR")
        self.emp = User.objects.create_user(username="emp", password="pass", role="EMPLOYEE")

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    def test_hr_can_list(self):
        assert self._client(self.hr).get("/api/employees/tax-brackets/tax/").status_code == 200

    def test_employee_forbidden(self):
        assert self._client(self.emp).get("/api/employees/tax-brackets/tax/").status_code == 403

    def test_anon_forbidden(self):
        assert APIClient().get("/api/employees/tax-brackets/tax/").status_code in (401, 403)

    def test_hr_can_create(self):
        resp = self._client(self.hr).post(
            "/api/employees/tax-brackets/tax/",
            {"country": "Test", "lower_limit": "0", "upper_limit": "100000", "rate": "5"},
            format="json",
        )
        assert resp.status_code == 201

    def test_employee_cannot_create(self):
        resp = self._client(self.emp).post(
            "/api/employees/tax-brackets/tax/",
            {"country": "Test", "lower_limit": "0", "rate": "5"},
            format="json",
        )
        assert resp.status_code == 403

    def test_search_filter(self):
        from decimal import Decimal

        from apps.employees.models import TaxBracket

        TaxBracket.objects.create(
            country="SearchCountry", lower_limit=Decimal("0"), upper_limit=None, rate=Decimal("10")
        )
        resp = self._client(self.hr).get("/api/employees/tax-brackets/tax/?search=SearchCountry")
        assert resp.data["count"] >= 1
