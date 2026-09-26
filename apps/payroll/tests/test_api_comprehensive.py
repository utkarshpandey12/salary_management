from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.employees.models import Department, Employee, SalaryStructure
from apps.payroll.models import PayrollExport
from apps.reimbursements.models import Reimbursement

User = get_user_model()


@pytest.mark.django_db
class TestPayrollDataAPI:
    def setup_method(self):
        self.dept = Department.objects.create(name="Eng", code="ENG")
        self.hr = User.objects.create_user(username="hr", password="pass", role="HR")
        self.emp_user = User.objects.create_user(username="emp", password="pass", role="EMPLOYEE")
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
            status="ACTIVE",
        )
        self.emp2 = Employee.objects.create(
            employee_id="ACME-00002",
            first_name="Jane",
            last_name="Smith",
            email="jane@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
            status="ACTIVE",
        )
        SalaryStructure.objects.create(employee=self.emp, basic_salary=Decimal("50000"))
        SalaryStructure.objects.create(employee=self.emp2, basic_salary=Decimal("60000"))
        Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            amount=Decimal("1000"),
            expense_date="2026-09-10",
            status="APPROVED",
        )
        Reimbursement.objects.create(
            employee=self.emp,
            title="Pending",
            amount=Decimal("5000"),
            expense_date="2026-09-10",
            status="PENDING",
        )

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    def test_hr_can_access(self):
        assert self._client(self.hr).get("/api/payroll/data/?month=2026-09").status_code == 200

    def test_employee_forbidden(self):
        assert (
            self._client(self.emp_user).get("/api/payroll/data/?month=2026-09").status_code == 403
        )

    def test_anon_forbidden(self):
        assert APIClient().get("/api/payroll/data/?month=2026-09").status_code in (401, 403)

    def test_default_month_is_current(self):
        resp = self._client(self.hr).get("/api/payroll/data/")
        assert resp.status_code == 200
        assert "month" in resp.data

    @pytest.mark.parametrize("month_str", ["2026-09", "2026-09-01", "2026-01", "2026-12"])
    def test_various_month_formats(self, month_str):
        resp = self._client(self.hr).get(f"/api/payroll/data/?month={month_str}")
        assert resp.status_code == 200

    def test_invalid_month_returns_400(self):
        resp = self._client(self.hr).get("/api/payroll/data/?month=invalid")
        assert resp.status_code == 400

    def test_invalid_month_format2(self):
        resp = self._client(self.hr).get("/api/payroll/data/?month=2026-13")
        assert resp.status_code == 400

    def test_pagination(self):
        resp = self._client(self.hr).get("/api/payroll/data/?month=2026-09&page=1&page_size=1")
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1
        assert resp.data["count"] == 2

    def test_pagination_page2(self):
        resp = self._client(self.hr).get("/api/payroll/data/?month=2026-09&page=2&page_size=1")
        assert len(resp.data["results"]) == 1

    def test_totals_correct(self):
        resp = self._client(self.hr).get("/api/payroll/data/?month=2026-09")
        # only approved reimbursement counted
        assert resp.data["totals"]["reimbursement_amount"] == Decimal("1000")
        # salary totals
        from django.db.models import Sum

        expected_salary = Employee.objects.filter(status="ACTIVE").aggregate(
            total=Sum("salary__net_in_hand")
        )["total"]
        # API totals salary_amount is sum of net_in_hand, need to compare
        # Our API returns totals salary_amount as sum of net_in_hand
        # Check that total = salary + reimb
        assert (
            resp.data["totals"]["total_amount"]
            == resp.data["totals"]["salary_amount"] + resp.data["totals"]["reimbursement_amount"]
        )

    def test_inactive_excluded(self):
        self.emp2.status = "INACTIVE"
        self.emp2.save()
        resp = self._client(self.hr).get("/api/payroll/data/?month=2026-09")
        assert resp.data["count"] == 1

    def test_reimbursement_wrong_month_not_counted(self):
        Reimbursement.objects.create(
            employee=self.emp,
            title="Oct",
            amount=Decimal("2000"),
            expense_date="2026-10-10",
            status="APPROVED",
        )
        resp = self._client(self.hr).get("/api/payroll/data/?month=2026-09")
        # should still be 1000
        assert resp.data["totals"]["reimbursement_amount"] == Decimal("1000")

    def test_pending_not_counted(self):
        # already have pending 5000 not counted
        resp = self._client(self.hr).get("/api/payroll/data/?month=2026-09")
        assert resp.data["totals"]["reimbursement_amount"] == Decimal("1000")

    def test_multiple_reimbursements_same_employee(self):
        Reimbursement.objects.create(
            employee=self.emp,
            title="Trip2",
            amount=Decimal("2000"),
            expense_date="2026-09-15",
            status="APPROVED",
        )
        resp = self._client(self.hr).get("/api/payroll/data/?month=2026-09")
        assert resp.data["totals"]["reimbursement_amount"] == Decimal("3000")

    def test_page_size_capped(self):
        resp = self._client(self.hr).get("/api/payroll/data/?month=2026-09&page_size=500")
        # capped to 200
        assert len(resp.data["results"]) <= 200

    def test_results_contain_required_fields(self):
        resp = self._client(self.hr).get("/api/payroll/data/?month=2026-09")
        for r in resp.data["results"]:
            assert "empID" in r
            assert "salary_amount" in r
            assert "reimbursement_amount" in r
            assert "total_amount" in r


@pytest.mark.django_db
class TestPayrollExportAPI:
    def setup_method(self):
        self.hr = User.objects.create_user(username="hr", password="pass", role="HR")
        self.emp = User.objects.create_user(username="emp", password="pass", role="EMPLOYEE")

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    def test_hr_can_create_excel(self):
        resp = self._client(self.hr).post(
            "/api/payroll/exports/", {"month": "2026-09-01", "format": "EXCEL"}, format="json"
        )
        assert resp.status_code == 201
        exp = PayrollExport.objects.get(id=resp.data["id"])
        exp.refresh_from_db()
        assert exp.status == "COMPLETED"
        assert exp.file.name.endswith(".xlsx")

    def test_hr_can_create_pdf(self):
        resp = self._client(self.hr).post(
            "/api/payroll/exports/", {"month": "2026-09-01", "format": "PDF"}, format="json"
        )
        assert resp.status_code == 201
        assert PayrollExport.objects.get(id=resp.data["id"]).file.name.endswith(".pdf")

    def test_employee_cannot_create(self):
        resp = self._client(self.emp).post(
            "/api/payroll/exports/", {"month": "2026-09-01", "format": "EXCEL"}, format="json"
        )
        assert resp.status_code == 403

    def test_anon_cannot_create(self):
        assert APIClient().post(
            "/api/payroll/exports/", {"month": "2026-09-01", "format": "EXCEL"}, format="json"
        ).status_code in (401, 403)

    def test_invalid_format(self):
        resp = self._client(self.hr).post(
            "/api/payroll/exports/", {"month": "2026-09-01", "format": "DOCX"}, format="json"
        )
        assert resp.status_code == 400

    def test_month_normalized_to_first_day(self):
        resp = self._client(self.hr).post(
            "/api/payroll/exports/", {"month": "2026-09-15", "format": "EXCEL"}, format="json"
        )
        assert resp.status_code == 201
        exp = PayrollExport.objects.get(id=resp.data["id"])
        assert exp.month.day == 1

    def test_list_hr_sees_own(self):
        self._client(self.hr).post(
            "/api/payroll/exports/", {"month": "2026-09-01", "format": "EXCEL"}, format="json"
        )
        resp = self._client(self.hr).get("/api/payroll/exports/")
        assert resp.status_code == 200
        assert resp.data["count"] == 1

    def test_employee_cannot_list(self):
        assert self._client(self.emp).get("/api/payroll/exports/").status_code == 403

    def test_retrieve(self):
        resp = self._client(self.hr).post(
            "/api/payroll/exports/", {"month": "2026-09-01", "format": "EXCEL"}, format="json"
        )
        exp_id = resp.data["id"]
        resp2 = self._client(self.hr).get(f"/api/payroll/exports/{exp_id}/")
        assert resp2.status_code == 200

    @pytest.mark.parametrize("fmt", ["EXCEL", "PDF"])
    def test_both_formats(self, fmt):
        resp = self._client(self.hr).post(
            "/api/payroll/exports/", {"month": "2026-09-01", "format": fmt}, format="json"
        )
        assert resp.status_code == 201

    def test_missing_month(self):
        resp = self._client(self.hr).post(
            "/api/payroll/exports/", {"format": "EXCEL"}, format="json"
        )
        assert resp.status_code == 400
