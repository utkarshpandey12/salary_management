import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.permissions import IsHR, IsHROrReadOnly, IsOwnerOrHR
from apps.employees.models import Department, Employee

User = get_user_model()


@pytest.mark.django_db
class TestIsHRPermission:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.hr = User.objects.create_user(username="hr", password="pass", role="HR")
        self.emp = User.objects.create_user(username="emp", password="pass", role="EMPLOYEE")

    def _req(self, user):
        r = self.factory.get("/")
        r.user = user
        return r

    def test_hr_has_permission(self):
        assert IsHR().has_permission(self._req(self.hr), None) is True

    def test_employee_denied(self):
        assert IsHR().has_permission(self._req(self.emp), None) is False

    def test_anon_denied(self):
        from django.contrib.auth.models import AnonymousUser

        r = self.factory.get("/")
        r.user = AnonymousUser()
        assert IsHR().has_permission(r, None) is False

    def test_unauthenticated_user(self):
        from django.contrib.auth.models import AnonymousUser

        r = self.factory.get("/")
        r.user = AnonymousUser()
        assert IsHR().has_permission(r, None) is False


@pytest.mark.django_db
class TestIsHROrReadOnly:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.hr = User.objects.create_user(username="hr", password="pass", role="HR")
        self.emp = User.objects.create_user(username="emp", password="pass", role="EMPLOYEE")

    def test_read_allowed_for_employee(self):
        r = self.factory.get("/")
        r.user = self.emp
        r.method = "GET"
        assert IsHROrReadOnly().has_permission(r, None) is True

    def test_write_denied_for_employee(self):
        r = self.factory.post("/")
        r.user = self.emp
        r.method = "POST"
        assert IsHROrReadOnly().has_permission(r, None) is False

    def test_write_allowed_for_hr(self):
        r = self.factory.post("/")
        r.user = self.hr
        r.method = "POST"
        assert IsHROrReadOnly().has_permission(r, None) is True

    def test_head_allowed(self):
        r = self.factory.head("/")
        r.user = self.emp
        r.method = "HEAD"
        assert IsHROrReadOnly().has_permission(r, None) is True

    def test_options_allowed(self):
        r = self.factory.options("/")
        r.user = self.emp
        r.method = "OPTIONS"
        assert IsHROrReadOnly().has_permission(r, None) is True


@pytest.mark.django_db
class TestIsOwnerOrHR:
    def setup_method(self):
        self.hr = User.objects.create_user(username="hr", password="pass", role="HR")
        self.emp_user = User.objects.create_user(username="emp", password="pass", role="EMPLOYEE")
        self.other_user = User.objects.create_user(
            username="other", password="pass", role="EMPLOYEE"
        )
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
            user=self.emp_user,
        )

    def test_hr_can_access_any(self):
        perm = IsOwnerOrHR()
        factory = APIRequestFactory()
        r = factory.get("/")
        r.user = self.hr
        assert perm.has_object_permission(r, None, self.emp) is True

    def test_owner_can_access_own_employee(self):
        perm = IsOwnerOrHR()
        factory = APIRequestFactory()
        r = factory.get("/")
        r.user = self.emp_user
        assert perm.has_object_permission(r, None, self.emp) is True

    def test_other_employee_denied(self):
        perm = IsOwnerOrHR()
        factory = APIRequestFactory()
        r = factory.get("/")
        r.user = self.other_user
        assert perm.has_object_permission(r, None, self.emp) is False

    def test_user_object_self(self):
        perm = IsOwnerOrHR()
        factory = APIRequestFactory()
        r = factory.get("/")
        r.user = self.emp_user
        assert perm.has_object_permission(r, None, self.emp_user) is True

    def test_user_object_other(self):
        perm = IsOwnerOrHR()
        factory = APIRequestFactory()
        r = factory.get("/")
        r.user = self.other_user
        assert perm.has_object_permission(r, None, self.emp_user) is False

    @pytest.mark.parametrize("role", ["HR", "EMPLOYEE"])
    def test_hr_always_passes(self, role):
        u = User.objects.create_user(username=f"u_{role}_2", password="pass", role=role)
        factory = APIRequestFactory()
        r = factory.get("/")
        r.user = u
        # only HR should pass for random object not owned
        expected = role == "HR"
        assert (
            IsOwnerOrHR().has_object_permission(r, None, self.emp) == expected or u == self.emp_user
        )


@pytest.mark.django_db
class TestAPIAuthEnforcement:
    def test_unauthenticated_api_401(self):
        c = APIClient()
        resp = c.get("/api/employees/")
        assert resp.status_code in (401, 403)

    def test_authenticated_can_access_me(self):
        hr = User.objects.create_user(username="hr", password="pass", role="HR")
        c = APIClient()
        c.force_authenticate(user=hr)
        resp = c.get("/api/auth/me/")
        assert resp.status_code == 200
        assert resp.data["role"] == "HR"
        assert resp.data["is_hr"] is True

    def test_employee_me(self):
        emp = User.objects.create_user(username="emp", password="pass", role="EMPLOYEE")
        c = APIClient()
        c.force_authenticate(user=emp)
        resp = c.get("/api/auth/me/")
        assert resp.status_code == 200
        assert resp.data["is_hr"] is False

    def test_anon_me_forbidden(self):
        c = APIClient()
        resp = c.get("/api/auth/me/")
        assert resp.status_code in (401, 403)
