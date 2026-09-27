from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.employees.models import Department, Employee, SalaryStructure

User = get_user_model()


@pytest.mark.django_db
class TestManagerValidation:
    def setup_method(self):
        self.dept = Department.objects.create(name="Eng", code="ENG")
        self.hr = User.objects.create_user(username="hr", password="pass", role="HR")
        self.a = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="A",
            last_name="One",
            email="a@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        SalaryStructure.objects.create(employee=self.a, basic_salary=Decimal("50000"))
        self.b = Employee.objects.create(
            employee_id="ACME-00002",
            first_name="B",
            last_name="Two",
            email="b@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        SalaryStructure.objects.create(employee=self.b, basic_salary=Decimal("50000"))
        self.c = Employee.objects.create(
            employee_id="ACME-00003",
            first_name="C",
            last_name="Three",
            email="c@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        SalaryStructure.objects.create(employee=self.c, basic_salary=Decimal("50000"))

    def _client(self):
        c = APIClient()
        c.force_authenticate(user=self.hr)
        return c

    def test_cannot_be_own_manager_api(self):
        resp = self._client().patch(
            f"/api/employees/{self.a.id}/", {"manager": self.a.id}, format="json"
        )
        assert resp.status_code == 400
        assert "manager" in resp.data

    def test_model_rejects_self_manager(self):
        self.a.manager = self.a
        with pytest.raises(ValidationError):
            self.a.full_clean()

    def test_direct_cycle_rejected(self):
        # A -> B ok
        resp1 = self._client().patch(
            f"/api/employees/{self.a.id}/", {"manager": self.b.id}, format="json"
        )
        assert resp1.status_code == 200
        # B -> A must fail (cycle)
        resp2 = self._client().patch(
            f"/api/employees/{self.b.id}/", {"manager": self.a.id}, format="json"
        )
        assert resp2.status_code == 400
        assert "manager" in resp2.data

    def test_indirect_cycle_rejected(self):
        # A->B, B->C ok
        assert (
            self._client()
            .patch(f"/api/employees/{self.a.id}/", {"manager": self.b.id}, format="json")
            .status_code
            == 200
        )
        assert (
            self._client()
            .patch(f"/api/employees/{self.b.id}/", {"manager": self.c.id}, format="json")
            .status_code
            == 200
        )
        # C->A closes loop, must fail
        resp = self._client().patch(
            f"/api/employees/{self.c.id}/", {"manager": self.a.id}, format="json"
        )
        assert resp.status_code == 400

    def test_valid_manager_allowed(self):
        resp = self._client().patch(
            f"/api/employees/{self.a.id}/", {"manager": self.b.id}, format="json"
        )
        assert resp.status_code == 200
        self.a.refresh_from_db()
        assert self.a.manager_id == self.b.id
