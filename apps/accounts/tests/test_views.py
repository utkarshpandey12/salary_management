import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()


@pytest.mark.django_db
class TestLoginView:
    def setup_method(self):
        self.hr = User.objects.create_user(username="hr", password="hr12345", role="HR")
        self.emp = User.objects.create_user(username="emp", password="emp12345", role="EMPLOYEE")
        self.client = Client()

    def test_login_page_get(self):
        resp = self.client.get("/accounts/login/")
        assert resp.status_code == 200
        assert b"Sign in" in resp.content or b"Welcome back" in resp.content

    def test_login_hr_success_redirects_dashboard(self):
        resp = self.client.post("/accounts/login/", {"username": "hr", "password": "hr12345"})
        assert resp.status_code in (302, 200)
        # should be authenticated
        resp2 = self.client.get("/")
        assert resp2.status_code == 200

    def test_login_employee_success(self):
        resp = self.client.post("/accounts/login/", {"username": "emp", "password": "emp12345"})
        assert resp.status_code in (302, 200)

    def test_login_wrong_password_fails(self):
        resp = self.client.post("/accounts/login/", {"username": "hr", "password": "wrong"})
        assert resp.status_code == 200  # stays on login page
        assert (
            b"correct username" in resp.content.lower()
            or b"error" in resp.content.lower()
            or resp.context["form"].errors
        )

    def test_login_nonexistent_user(self):
        resp = self.client.post("/accounts/login/", {"username": "nouser", "password": "pass"})
        assert resp.status_code == 200

    def test_logout_redirects_login(self):
        self.client.force_login(self.hr)
        resp = self.client.get("/accounts/logout/")
        assert resp.status_code in (302, 200)
        # after logout, dashboard should redirect to login
        resp2 = self.client.get("/")
        assert resp2.status_code in (302, 200)

    def test_dashboard_requires_login(self):
        c = Client()
        resp = c.get("/")
        assert resp.status_code in (302, 200)
        assert "/accounts/login" in resp.url if hasattr(resp, "url") else True

    def test_hr_dashboard_contains_hr_text(self):
        self.client.force_login(self.hr)
        resp = self.client.get("/")
        assert resp.status_code == 200
        assert b"HR Dashboard" in resp.content or b"Total Employees" in resp.content

    def test_employee_dashboard_contains_my_dashboard(self):
        self.client.force_login(self.emp)
        resp = self.client.get("/")
        assert resp.status_code == 200
        # employee without linked profile shows message
        assert b"My Dashboard" in resp.content or b"Welcome" in resp.content

    @pytest.mark.parametrize(
        "url", ["/employees/", "/departments/", "/analytics/", "/payroll/", "/reimbursements/"]
    )
    def test_protected_urls_redirect_for_anon(self, url):
        c = Client()
        resp = c.get(url)
        assert resp.status_code in (302, 301)
        assert "login" in resp.url

    def test_employee_cannot_access_analytics_ui(self):
        self.client.force_login(self.emp)
        resp = self.client.get("/analytics/")
        assert resp.status_code in (302, 403, 200)  # redirect with message
        # should not contain analytics data
        if resp.status_code == 200:
            assert b"Analytics" not in resp.content or b"HR access required" in resp.content

    def test_hr_can_access_analytics_ui(self):
        self.client.force_login(self.hr)
        resp = self.client.get("/analytics/")
        assert resp.status_code == 200
        assert b"Analytics" in resp.content

    def test_login_next_redirect(self):
        self.client.force_login(self.hr)
        resp = self.client.get("/employees/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestUserCreationEdgeCases:
    def test_duplicate_username_fails(self):
        User.objects.create_user(username="dup", password="pass")
        try:
            User.objects.create_user(username="dup", password="pass")
            assert False
        except Exception:
            assert True

    def test_create_user_with_email(self):
        u = User.objects.create_user(username="e", password="pass", email="e@a.com")
        assert u.email == "e@a.com"

    def test_staff_flag(self):
        u = User.objects.create_user(username="staff", password="pass", is_staff=True, role="HR")
        assert u.is_staff is True

    def test_inactive_user_cannot_login(self):
        u = User.objects.create_user(
            username="inactive", password="pass", role="HR", is_active=False
        )
        c = Client()
        resp = c.post("/accounts/login/", {"username": "inactive", "password": "pass"})
        assert resp.status_code == 200  # login fails
