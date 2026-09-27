import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.employees.models import Employee, SalaryStructure

User = get_user_model()


@pytest.mark.django_db
class TestSeedCommand:
    def test_seed_creates_employees_and_salaries(self):
        call_command("seed_employees", count=5)
        assert Employee.objects.count() == 5
        assert SalaryStructure.objects.count() == 5

    def test_seed_assigns_managers(self):
        call_command("seed_employees", count=5)
        assert Employee.objects.filter(manager__isnull=False).count() == 5

    def test_seed_creates_demo_users(self):
        call_command("seed_employees", count=5)
        assert User.objects.filter(username="hr_admin").exists()
        assert User.objects.filter(username="employee_demo").exists()

    def test_seed_idempotent_without_clear(self):
        call_command("seed_employees", count=5)
        call_command("seed_employees", count=5)
        assert Employee.objects.count() == 5

    def test_seed_clear_resets(self):
        call_command("seed_employees", count=5)
        call_command("seed_employees", count=3, clear=True)
        assert Employee.objects.count() == 3
