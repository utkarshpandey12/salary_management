from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.employees.models import Department, Employee, SalaryStructure, TaxBracket

User = get_user_model()


@pytest.mark.django_db
class TestAnalyticsBusinessRules:
    def setup_method(self):
        self.dept_eng = Department.objects.create(name="Engineering", code="ENG")
        self.dept_sales = Department.objects.create(name="Sales", code="SAL")
        self.hr = User.objects.create_user(username="hr", password="pass", role="HR")
        self.emp = User.objects.create_user(username="emp", password="pass", role="EMPLOYEE")
        # tax
        TaxBracket.objects.create(
            country="India",
            lower_limit=Decimal("0"),
            upper_limit=Decimal("300000"),
            rate=Decimal("0"),
        )
        TaxBracket.objects.create(
            country="India", lower_limit=Decimal("300000"), upper_limit=None, rate=Decimal("10")
        )
        TaxBracket.objects.create(
            country="USA", lower_limit=Decimal("0"), upper_limit=None, rate=Decimal("0")
        )
        # employees
        self.e1 = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="A",
            last_name="B",
            email="a@a.com",
            country="India",
            job_title="Engineer",
            department=self.dept_eng,
            date_of_joining="2020-01-01",
        )
        SalaryStructure.objects.create(employee=self.e1, basic_salary=Decimal("50000"))
        self.e2 = Employee.objects.create(
            employee_id="ACME-00002",
            first_name="C",
            last_name="D",
            email="c@a.com",
            country="India",
            job_title="Engineer",
            department=self.dept_eng,
            date_of_joining="2020-01-01",
        )
        SalaryStructure.objects.create(employee=self.e2, basic_salary=Decimal("80000"))
        self.e3 = Employee.objects.create(
            employee_id="ACME-00003",
            first_name="E",
            last_name="F",
            email="e@a.com",
            country="USA",
            job_title="Designer",
            department=self.dept_sales,
            date_of_joining="2020-01-01",
        )
        SalaryStructure.objects.create(employee=self.e3, basic_salary=Decimal("60000"))

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    def test_employee_cannot_access_analytics(self):
        c = self._client(self.emp)
        assert c.get("/api/employees/analytics/").status_code == 403

    def test_anon_cannot_access_analytics(self):
        c = APIClient()
        assert c.get("/api/employees/analytics/").status_code in (401, 403)

    def test_hr_gets_overall_stats(self):
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/")
        assert resp.status_code == 200
        assert resp.data["overall"]["count"] == 3
        assert resp.data["overall"]["avg_net"] is not None
        assert resp.data["overall"]["min_net"] is not None
        assert resp.data["overall"]["max_net"] is not None

    def test_analytics_total_payroll_sum(self):
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/")
        total = resp.data["overall"]["total_payroll"]
        # manual sum
        from django.db.models import Sum

        expected = Employee.objects.filter(salary__isnull=False).aggregate(
            total=Sum("salary__net_in_hand")
        )["total"]
        assert total == expected

    def test_analytics_filter_by_country(self):
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/?country=India")
        assert resp.data["overall"]["count"] == 2
        assert all(
            r["country"] == "India" for r in resp.data["by_country"] if r["country"] == "India"
        )

    def test_analytics_filter_by_job_title(self):
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/?job_title=Engineer")
        assert resp.data["overall"]["count"] == 2

    def test_analytics_filter_by_department_id(self):
        c = self._client(self.hr)
        resp = c.get(f"/api/employees/analytics/?department={self.dept_eng.id}")
        assert resp.data["overall"]["count"] == 2

    def test_analytics_filter_by_department_code(self):
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/?department=ENG")
        assert resp.data["overall"]["count"] == 2

    def test_analytics_specific_avg_country_title(self):
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/?country=India&job_title=Engineer")
        assert resp.data["overall"]["specific_avg_job_country"] is not None

    def test_analytics_specific_avg_missing_returns_none(self):
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/?country=Nowhere&job_title=Ghost")
        assert resp.data["overall"]["specific_avg_job_country"] is None
        assert resp.data["overall"]["count"] == 0

    def test_analytics_median_p25_p75_present(self):
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/")
        assert resp.data["overall"]["median_net"] is not None
        assert resp.data["overall"]["p25"] is not None
        assert resp.data["overall"]["p75"] is not None
        assert (
            resp.data["overall"]["p25"]
            <= resp.data["overall"]["median_net"]
            <= resp.data["overall"]["p75"]
        )

    def test_analytics_by_country_aggregation(self):
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/")
        by_country = {r["country"]: r for r in resp.data["by_country"]}
        assert "India" in by_country
        assert by_country["India"]["count"] == 2
        assert by_country["India"]["avg"] is not None

    def test_analytics_by_department_aggregation(self):
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/")
        by_dept = {r["department__code"]: r for r in resp.data["by_department"]}
        assert "ENG" in by_dept
        assert by_dept["ENG"]["count"] == 2

    def test_analytics_by_job_title_aggregation(self):
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/")
        by_title = {r["job_title"]: r for r in resp.data["by_job_title"]}
        assert "Engineer" in by_title
        assert by_title["Engineer"]["count"] == 2

    def test_analytics_empty_queryset(self):
        Employee.objects.all().delete()
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/")
        assert resp.data["overall"]["count"] == 0
        assert resp.data["overall"]["avg_net"] is None

    def test_analytics_avg_gross_present(self):
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/")
        assert resp.data["overall"]["avg_gross"] is not None

    @pytest.mark.parametrize("country", ["India", "USA", "Germany"])
    def test_analytics_country_param_case_insensitive(self, country):
        # create extra
        Employee.objects.create(
            employee_id=f"ACME-00{Employee.objects.count() + 1:03d}",
            first_name="X",
            last_name="Y",
            email=f"x{Employee.objects.count()}@a.com",
            country=country,
            job_title="Tester",
            department=self.dept_eng,
            date_of_joining="2020-01-01",
        )
        from decimal import Decimal

        e = Employee.objects.filter(country=country).last()
        SalaryStructure.objects.create(employee=e, basic_salary=Decimal("40000"))
        c = self._client(self.hr)
        resp = c.get(f"/api/employees/analytics/?country={country.lower()}")
        assert resp.data["overall"]["count"] >= 1

    def test_analytics_min_max_correctness(self):
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/")
        overall = resp.data["overall"]
        assert overall["min_net"] <= overall["avg_net"] <= overall["max_net"]

    def test_analytics_filters_combined(self):
        c = self._client(self.hr)
        resp = c.get(
            f"/api/employees/analytics/?country=India&department={self.dept_eng.id}&job_title=Engineer"
        )
        assert resp.data["overall"]["count"] == 2

    def test_analytics_department_filter_invalid_returns_zero(self):
        c = self._client(self.hr)
        resp = c.get("/api/employees/analytics/?department=99999")
        assert resp.data["overall"]["count"] == 0
