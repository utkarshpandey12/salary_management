import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    def test_create_hr_user(self):
        u = User.objects.create_user(username="hr1", password="pass", role=User.Role.HR)
        assert u.role == "HR"
        assert u.is_hr is True
        assert u.is_employee_role is False
        assert str(u) == "hr1 (HR)"

    def test_create_employee_user(self):
        u = User.objects.create_user(username="emp1", password="pass", role=User.Role.EMPLOYEE)
        assert u.role == "EMPLOYEE"
        assert u.is_hr is False
        assert u.is_employee_role is True

    def test_default_role_is_employee(self):
        u = User.objects.create_user(username="def", password="pass")
        assert u.role == User.Role.EMPLOYEE

    def test_is_hr_property(self):
        hr = User.objects.create_user(username="h", password="pass", role="HR")
        emp = User.objects.create_user(username="e", password="pass", role="EMPLOYEE")
        assert hr.is_hr and not emp.is_hr

    def test_invalid_role_choice(self):
        from django.core.exceptions import ValidationError

        u = User(username="x", role="INVALID")
        try:
            u.full_clean()
            assert False, "should raise"
        except ValidationError:
            assert True

    @pytest.mark.parametrize("username", ["a", "ab", "user_with_long_name_123"])
    def test_username_variations(self, username):
        u = User.objects.create_user(username=username, password="pass")
        assert User.objects.filter(username=username).exists()

    def test_email_unique_not_required(self):
        User.objects.create_user(username="u1", password="pass", email="a@a.com")
        User.objects.create_user(username="u2", password="pass", email="a@a.com")
        # email not unique in User model (only Employee email unique), should allow duplicate
        assert User.objects.filter(email="a@a.com").count() == 2

    def test_password_hashing(self):
        u = User.objects.create_user(username="h", password="secret123")
        assert u.check_password("secret123")
        assert not u.check_password("wrong")

    def test_superuser_creation(self):
        su = User.objects.create_superuser(username="admin", password="pass", email="admin@a.com")
        assert su.is_staff
        assert su.is_superuser

    def test_str_includes_role(self):
        u = User.objects.create_user(username="bob", password="pass", role="HR")
        assert "HR" in str(u)

    @pytest.mark.parametrize("role,expected_is_hr", [("HR", True), ("EMPLOYEE", False)])
    def test_role_is_hr_parametrized(self, role, expected_is_hr):
        u = User.objects.create_user(username=f"u_{role}", password="pass", role=role)
        assert u.is_hr == expected_is_hr

    def test_user_role_choices(self):
        choices = [c[0] for c in User.Role.choices]
        assert "HR" in choices
        assert "EMPLOYEE" in choices
        assert len(choices) == 2
