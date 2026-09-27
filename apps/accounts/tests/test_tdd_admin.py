import pytest
from django.contrib import admin


@pytest.mark.django_db
class TestAdminRegistrations:
    def test_user_registered(self):
        from apps.accounts.models import User

        assert admin.site.is_registered(User)

    def test_department_registered(self):
        from apps.employees.models import Department

        assert admin.site.is_registered(Department)

    def test_employee_registered(self):
        from apps.employees.models import Employee

        assert admin.site.is_registered(Employee)

    def test_salary_structure_registered(self):
        from apps.employees.models import SalaryStructure

        assert admin.site.is_registered(SalaryStructure)

    def test_tax_bracket_registered(self):
        from apps.employees.models import TaxBracket

        assert admin.site.is_registered(TaxBracket)

    def test_reimbursement_registered(self):
        from apps.reimbursements.models import Reimbursement

        assert admin.site.is_registered(Reimbursement)

    def test_payroll_export_registered(self):
        from apps.payroll.models import PayrollExport

        assert admin.site.is_registered(PayrollExport)
