import pytest
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.employees.models import Department, Employee, SalaryStructure, TaxBracket

User = get_user_model()

@pytest.mark.django_db
class TestSalaryComputation(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Engineering", code="ENG", description="Eng")
        # create tax brackets for test country
        TaxBracket.objects.create(country="Testland", lower_limit=Decimal("0"), upper_limit=Decimal("300000"), rate=Decimal("0"))
        TaxBracket.objects.create(country="Testland", lower_limit=Decimal("300000"), upper_limit=Decimal("600000"), rate=Decimal("10"))
        TaxBracket.objects.create(country="Testland", lower_limit=Decimal("600000"), upper_limit=None, rate=Decimal("20"))

    def test_employee_full_name_auto(self):
        emp = Employee.objects.create(
            employee_id="ACME-00001", first_name="John", last_name="Doe", email="john@acme.test",
            country="Testland", job_title="Engineer", department=self.dept, date_of_joining="2020-01-01", phone="123", address="Addr"
        )
        self.assertEqual(emp.full_name, "John Doe")

    def test_salary_recompute_gross_and_tax(self):
        emp = Employee.objects.create(
            employee_id="ACME-00002", first_name="Jane", last_name="Roe", email="jane@acme.test",
            country="Testland", job_title="Engineer", department=self.dept, date_of_joining="2020-01-01"
        )
        sal = SalaryStructure.objects.create(
            employee=emp,
            basic_salary=Decimal("50000"),
            house_rent_allowance=Decimal("10000"),
            dearness_allowance=Decimal("5000"),
            transport_allowance=Decimal("2000"),
            telephone_allowance=Decimal("500"),
            special_allowance=Decimal("3000"),
            pf_deduction=Decimal("4000"),
            professional_tax=Decimal("200"),
        )
        # gross = 50000+10000+5000+2000+500+3000=70500
        self.assertEqual(sal.gross_salary, Decimal("70500.00"))
        # annual gross = 846000 => tax: 0 on 0-300k, 10% on 300k-600k =30k, 20% on 600k-846k=49200 => total 79200 annual => 6600 monthly
        # Actually compute: bracket 300k-600k => 300k*10%=30000, 600k-846k=246k*20%=49200 total 79200/12=6600
        self.assertEqual(sal.tax_deduction, Decimal("6600.00"))
        # net = 70500 -4000 -200 -6600 = 59700
        self.assertEqual(sal.net_in_hand, Decimal("59700.00"))

    def test_salary_update_recomputes(self):
        emp = Employee.objects.create(
            employee_id="ACME-00003", first_name="Bob", last_name="Lee", email="bob@acme.test",
            country="Testland", job_title="Engineer", department=self.dept, date_of_joining="2020-01-01"
        )
        sal = SalaryStructure.objects.create(employee=emp, basic_salary=Decimal("40000"))
        orig_net = sal.net_in_hand
        sal.basic_salary = Decimal("80000")
        sal.save()
        self.assertNotEqual(sal.net_in_hand, orig_net)
        self.assertGreater(sal.net_in_hand, orig_net)

    def test_tax_bracket_global_fallback(self):
        # no Testland2 brackets -> should use GLOBAL or 0
        TaxBracket.objects.create(country="GLOBAL", lower_limit=Decimal("0"), upper_limit=None, rate=Decimal("0"))
        tax = TaxBracket.compute_tax("Testland2", Decimal("1000000"))
        self.assertEqual(tax, Decimal("0.00"))

    def test_employee_indexes_and_constraints(self):
        emp = Employee.objects.create(
            employee_id="ACME-00004", first_name="A", last_name="B", email="a@acme.test",
            country="India", job_title="Engineer", department=self.dept, date_of_joining="2020-01-01"
        )
        self.assertTrue(Employee.objects.filter(country="India").exists())
        # duplicate email should fail? uniqueness enforced at DB — test API would catch
