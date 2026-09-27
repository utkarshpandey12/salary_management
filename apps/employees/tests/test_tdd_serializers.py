from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestSerializers:
    def setup_method(self):
        from apps.employees.models import Department

        self.dept = Department.objects.create(name="Eng", code="ENG")

    def test_department_serializer_fields(self):
        from apps.employees.serializers import DepartmentSerializer

        s = DepartmentSerializer(self.dept)
        assert s.data["name"] == "Eng"
        assert s.data["code"] == "ENG"

    def test_salary_serializer_rejects_negative(self):
        from apps.employees.models import Employee
        from apps.employees.serializers import SalaryStructureSerializer

        emp = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="A",
            last_name="B",
            email="a@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        s = SalaryStructureSerializer(data={"employee": emp.id, "basic_salary": "-100.00"})
        assert not s.is_valid()
        assert "basic_salary" in s.errors

    def test_employee_create_with_nested_salary(self):
        from apps.employees.models import Employee
        from apps.employees.serializers import EmployeeCreateSerializer

        s = EmployeeCreateSerializer(
            data={
                "employee_id": "ACME-00002",
                "first_name": "New",
                "last_name": "Guy",
                "email": "new@a.com",
                "country": "India",
                "job_title": "Eng",
                "department": self.dept.id,
                "date_of_joining": "2020-01-01",
                "salary": {"basic_salary": "60000.00"},
            }
        )
        assert s.is_valid(), s.errors
        emp = s.save()
        assert Employee.objects.filter(employee_id="ACME-00002").exists()
        assert emp.salary.basic_salary == Decimal("60000.00")

    def test_tax_bracket_serializer(self):
        from apps.employees.models import TaxBracket
        from apps.employees.serializers import TaxBracketSerializer

        b = TaxBracket.objects.create(
            country="T", lower_limit=Decimal("0"), upper_limit=None, rate=Decimal("5")
        )
        assert TaxBracketSerializer(b).data["country"] == "T"

    def test_reimbursement_serializer_fields(self):
        from apps.employees.models import Employee, SalaryStructure
        from apps.reimbursements.models import Reimbursement
        from apps.reimbursements.serializers import ReimbursementSerializer

        emp = Employee.objects.create(
            employee_id="ACME-00003",
            first_name="R",
            last_name="E",
            email="r@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        SalaryStructure.objects.create(employee=emp, basic_salary=Decimal("50000"))
        r = Reimbursement.objects.create(
            employee=emp, title="Trip", amount=Decimal("100"), expense_date="2026-09-10"
        )
        data = ReimbursementSerializer(r).data
        assert data["employee_id_display"] == "ACME-00003"
        assert data["status"] == "PENDING"
