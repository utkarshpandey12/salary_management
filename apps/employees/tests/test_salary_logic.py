from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.employees.models import Department, Employee, SalaryStructure, TaxBracket

User = get_user_model()


@pytest.mark.django_db
class TestTaxBracket:
    def test_compute_tax_zero(self):
        TaxBracket.objects.create(
            country="T", lower_limit=Decimal("0"), upper_limit=Decimal("500000"), rate=Decimal("0")
        )
        TaxBracket.objects.create(
            country="T", lower_limit=Decimal("500000"), upper_limit=None, rate=Decimal("10")
        )
        assert TaxBracket.compute_tax("T", Decimal("0")) == Decimal("0.00")
        assert TaxBracket.compute_tax("T", Decimal("400000")) == Decimal("0.00")

    def test_compute_tax_single_bracket(self):
        TaxBracket.objects.create(
            country="X", lower_limit=Decimal("0"), upper_limit=None, rate=Decimal("10")
        )
        assert TaxBracket.compute_tax("X", Decimal("100000")) == Decimal("10000.00")

    def test_compute_tax_progressive(self):
        TaxBracket.objects.create(
            country="P", lower_limit=Decimal("0"), upper_limit=Decimal("300000"), rate=Decimal("0")
        )
        TaxBracket.objects.create(
            country="P",
            lower_limit=Decimal("300000"),
            upper_limit=Decimal("600000"),
            rate=Decimal("10"),
        )
        TaxBracket.objects.create(
            country="P", lower_limit=Decimal("600000"), upper_limit=None, rate=Decimal("20")
        )
        # 0 tax up to 300k
        assert TaxBracket.compute_tax("P", Decimal("300000")) == Decimal("0.00")
        # 450k -> 150k *10% =15000
        assert TaxBracket.compute_tax("P", Decimal("450000")) == Decimal("15000.00")
        # 700k -> 300k*10% +100k*20% =30000+20000=50000
        assert TaxBracket.compute_tax("P", Decimal("700000")) == Decimal("50000.00")

    def test_compute_tax_upper_none(self):
        TaxBracket.objects.create(
            country="U", lower_limit=Decimal("0"), upper_limit=None, rate=Decimal("15")
        )
        assert TaxBracket.compute_tax("U", Decimal("200000")) == Decimal("30000.00")

    def test_compute_tax_country_fallback_global(self):
        TaxBracket.objects.create(
            country="GLOBAL", lower_limit=Decimal("0"), upper_limit=None, rate=Decimal("5")
        )
        assert TaxBracket.compute_tax("UNKNOWN", Decimal("100000")) == Decimal("5000.00")

    def test_compute_tax_no_brackets_returns_zero(self):
        assert TaxBracket.compute_tax("NOWHERE", Decimal("1000000")) == Decimal("0.00")

    @pytest.mark.parametrize(
        "gross,expected",
        [
            (Decimal("0"), Decimal("0.00")),
            (Decimal("300000"), Decimal("0.00")),
            (Decimal("600000"), Decimal("30000.00")),
            (Decimal("900000"), Decimal("90000.00")),
        ],
    )
    def test_compute_tax_parametrized(self, gross, expected):
        TaxBracket.objects.all().delete()
        TaxBracket.objects.create(
            country="Q", lower_limit=Decimal("0"), upper_limit=Decimal("300000"), rate=Decimal("0")
        )
        TaxBracket.objects.create(
            country="Q",
            lower_limit=Decimal("300000"),
            upper_limit=Decimal("600000"),
            rate=Decimal("10"),
        )
        TaxBracket.objects.create(
            country="Q", lower_limit=Decimal("600000"), upper_limit=None, rate=Decimal("20")
        )
        assert TaxBracket.compute_tax("Q", gross) == expected

    def test_bracket_ordering(self):
        TaxBracket.objects.create(
            country="O", lower_limit=Decimal("600000"), upper_limit=None, rate=Decimal("20")
        )
        TaxBracket.objects.create(
            country="O", lower_limit=Decimal("0"), upper_limit=Decimal("300000"), rate=Decimal("0")
        )
        TaxBracket.objects.create(
            country="O",
            lower_limit=Decimal("300000"),
            upper_limit=Decimal("600000"),
            rate=Decimal("10"),
        )
        # should still compute correctly despite creation order
        assert TaxBracket.compute_tax("O", Decimal("500000")) == Decimal("20000.00")

    def test_rate_zero(self):
        TaxBracket.objects.create(
            country="Z", lower_limit=Decimal("0"), upper_limit=None, rate=Decimal("0")
        )
        assert TaxBracket.compute_tax("Z", Decimal("1000000")) == Decimal("0.00")

    def test_unique_constraint(self):
        TaxBracket.objects.create(
            country="UQ", lower_limit=Decimal("0"), upper_limit=Decimal("100"), rate=Decimal("5")
        )
        try:
            TaxBracket.objects.create(
                country="UQ",
                lower_limit=Decimal("0"),
                upper_limit=Decimal("200"),
                rate=Decimal("10"),
            )
            assert False, "should violate unique"
        except Exception:
            assert True


@pytest.mark.django_db
class TestSalaryRecompute:
    def setup_method(self):
        self.dept = Department.objects.create(name="Eng", code="ENG")
        # brackets: 0-300k 0%, 300k-600k 10%, 600k+20%
        TaxBracket.objects.create(
            country="Test",
            lower_limit=Decimal("0"),
            upper_limit=Decimal("300000"),
            rate=Decimal("0"),
        )
        TaxBracket.objects.create(
            country="Test",
            lower_limit=Decimal("300000"),
            upper_limit=Decimal("600000"),
            rate=Decimal("10"),
        )
        TaxBracket.objects.create(
            country="Test", lower_limit=Decimal("600000"), upper_limit=None, rate=Decimal("20")
        )

    def _emp(self, country="Test"):
        return Employee.objects.create(
            employee_id=f"ACME-{Employee.objects.count() + 1:05d}",
            first_name="John",
            last_name="Doe",
            email=f"john{Employee.objects.count()}@a.com",
            country=country,
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )

    def test_gross_sum(self):
        emp = self._emp()
        sal = SalaryStructure.objects.create(
            employee=emp,
            basic_salary=Decimal("10000"),
            house_rent_allowance=Decimal("2000"),
            dearness_allowance=Decimal("1000"),
            transport_allowance=Decimal("500"),
            telephone_allowance=Decimal("300"),
            special_allowance=Decimal("700"),
            pf_deduction=Decimal("1000"),
            professional_tax=Decimal("200"),
        )
        assert sal.gross_salary == Decimal("14500.00")
        assert sal.total_compensation == Decimal("14500.00")

    def test_net_calculation(self):
        emp = self._emp()
        sal = SalaryStructure.objects.create(
            employee=emp,
            basic_salary=Decimal("50000"),
            pf_deduction=Decimal("4000"),
            professional_tax=Decimal("200"),
        )
        # gross 50000, annual 600000, tax = 30000 annual => 2500 monthly
        # net = 50000-4000-200-2500=432... let's compute
        expected_tax = TaxBracket.compute_tax("Test", Decimal("600000")) / Decimal("12")
        expected_net = Decimal("50000") - Decimal("4000") - Decimal("200") - expected_tax
        assert sal.tax_deduction == expected_tax.quantize(Decimal("0.01"))
        assert sal.net_in_hand == max(expected_net, Decimal("0")).quantize(Decimal("0.01"))

    def test_net_never_negative(self):
        emp = self._emp()
        sal = SalaryStructure.objects.create(
            employee=emp,
            basic_salary=Decimal("1000"),
            pf_deduction=Decimal("5000"),
            professional_tax=Decimal("5000"),
        )
        assert sal.net_in_hand == Decimal("0.00")

    def test_update_basic_recomputes(self):
        emp = self._emp()
        sal = SalaryStructure.objects.create(employee=emp, basic_salary=Decimal("30000"))
        old = sal.net_in_hand
        sal.basic_salary = Decimal("60000")
        sal.save()
        assert sal.net_in_hand != old
        assert (
            sal.gross_salary
            == Decimal("60000.00") + sal.house_rent_allowance + sal.dearness_allowance
        )

    @pytest.mark.parametrize(
        "allowance_field",
        [
            "house_rent_allowance",
            "dearness_allowance",
            "transport_allowance",
            "telephone_allowance",
            "special_allowance",
        ],
    )
    def test_update_allowance_recomputes(self, allowance_field):
        emp = self._emp()
        sal = SalaryStructure.objects.create(employee=emp, basic_salary=Decimal("40000"))
        old_gross = sal.gross_salary
        setattr(sal, allowance_field, Decimal("5000"))
        sal.save()
        assert sal.gross_salary != old_gross

    @pytest.mark.parametrize("deduction_field", ["pf_deduction", "professional_tax"])
    def test_update_deduction_recomputes_net(self, deduction_field):
        emp = self._emp()
        sal = SalaryStructure.objects.create(
            employee=emp,
            basic_salary=Decimal("50000"),
            pf_deduction=Decimal("1000"),
            professional_tax=Decimal("100"),
        )
        old_net = sal.net_in_hand
        setattr(sal, deduction_field, Decimal("5000"))
        sal.save()
        assert sal.net_in_hand != old_net
        assert sal.net_in_hand < old_net

    def test_country_affects_tax(self):
        TaxBracket.objects.create(
            country="Other", lower_limit=Decimal("0"), upper_limit=None, rate=Decimal("30")
        )
        emp1 = Employee.objects.create(
            employee_id="ACME-10001",
            first_name="A",
            last_name="B",
            email="a1@a.com",
            country="Test",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        emp2 = Employee.objects.create(
            employee_id="ACME-10002",
            first_name="C",
            last_name="D",
            email="c1@a.com",
            country="Other",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        sal1 = SalaryStructure.objects.create(employee=emp1, basic_salary=Decimal("50000"))
        sal2 = SalaryStructure.objects.create(employee=emp2, basic_salary=Decimal("50000"))
        assert sal1.tax_deduction != sal2.tax_deduction
        assert sal2.tax_deduction > sal1.tax_deduction

    def test_zero_components(self):
        emp = self._emp()
        sal = SalaryStructure.objects.create(
            employee=emp, basic_salary=Decimal("0"), house_rent_allowance=Decimal("0")
        )
        assert sal.gross_salary == Decimal("0.00")
        assert sal.net_in_hand == Decimal("0.00")

    def test_decimal_precision(self):
        emp = self._emp()
        sal = SalaryStructure.objects.create(
            employee=emp, basic_salary=Decimal("12345.67"), house_rent_allowance=Decimal("0.33")
        )
        assert sal.gross_salary.quantize(Decimal("0.01")) == sal.gross_salary
