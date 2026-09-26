from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.employees.models import Department, Employee, SalaryStructure
from apps.reimbursements.models import Reimbursement

User = get_user_model()


@pytest.mark.django_db
class TestReimbursementUIBusinessRules:
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
        )
        SalaryStructure.objects.create(employee=self.emp, basic_salary=Decimal("50000"))
        self.other_emp = Employee.objects.create(
            employee_id="ACME-00002",
            first_name="Jane",
            last_name="Smith",
            email="jane@a.com",
            country="USA",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        SalaryStructure.objects.create(employee=self.other_emp, basic_salary=Decimal("50000"))

    def _login(self, user):
        c = Client()
        c.force_login(user)
        return c

    def test_list_hr_sees_all(self):
        Reimbursement.objects.create(
            employee=self.emp, title="Trip", amount=Decimal("100"), expense_date="2026-09-10"
        )
        Reimbursement.objects.create(
            employee=self.other_emp, title="Other", amount=Decimal("200"), expense_date="2026-09-10"
        )
        c = self._login(self.hr)
        resp = c.get("/reimbursements/")
        assert resp.status_code == 200
        assert b"Trip" in resp.content
        assert b"Other" in resp.content

    def test_list_employee_sees_only_own(self):
        Reimbursement.objects.create(
            employee=self.emp, title="Mine", amount=Decimal("100"), expense_date="2026-09-10"
        )
        Reimbursement.objects.create(
            employee=self.other_emp, title="Other", amount=Decimal("200"), expense_date="2026-09-10"
        )
        c = self._login(self.emp_user)
        resp = c.get("/reimbursements/")
        assert b"Mine" in resp.content
        assert b"Other" not in resp.content

    def test_list_filter_status_pending(self):
        Reimbursement.objects.create(
            employee=self.emp,
            title="PendingTrip",
            amount=Decimal("100"),
            expense_date="2026-09-10",
            status="PENDING",
        )
        Reimbursement.objects.create(
            employee=self.emp,
            title="ApprovedTrip",
            amount=Decimal("100"),
            expense_date="2026-09-10",
            status="APPROVED",
        )
        c = self._login(self.emp_user)
        resp = c.get("/reimbursements/?status=PENDING")
        assert b"PendingTrip" in resp.content
        # ApprovedTrip should be filtered out; check table body not containing that title (dropdown still contains word Approved)
        assert b"ApprovedTrip" not in resp.content

    def test_list_htmx_partial(self):
        c = self._login(self.hr)
        resp = c.get("/reimbursements/", HTTP_HX_REQUEST="true")
        assert resp.status_code == 200
        assert b"<table" in resp.content

    def test_create_employee_success(self):
        c = self._login(self.emp_user)
        resp = c.get("/reimbursements/create/")
        assert resp.status_code == 200
        resp2 = c.post(
            "/reimbursements/create/",
            {"title": "Trip", "purpose": "Visit", "amount": "1000", "expense_date": "2026-09-10"},
        )
        assert resp2.status_code in (302, 200)
        assert Reimbursement.objects.filter(title="Trip", employee=self.emp).exists()

    def test_create_employee_with_receipt(self):
        c = self._login(self.emp_user)
        pdf = SimpleUploadedFile("bill.pdf", b"pdf", content_type="application/pdf")
        resp = c.post(
            "/reimbursements/create/",
            {
                "title": "Trip",
                "purpose": "Visit",
                "amount": "500",
                "expense_date": "2026-09-10",
                "receipt": pdf,
            },
        )
        assert resp.status_code in (302, 200)
        r = Reimbursement.objects.get(title="Trip")
        assert r.receipt.name.endswith(".pdf")

    def test_create_hr_for_employee(self):
        c = self._login(self.hr)
        resp = c.post(
            "/reimbursements/create/",
            {
                "title": "HR Trip",
                "purpose": "Visit",
                "amount": "800",
                "expense_date": "2026-09-10",
                "employee": self.other_emp.id,
            },
        )
        assert resp.status_code in (302, 200)
        assert Reimbursement.objects.filter(title="HR Trip", employee=self.other_emp).exists()

    def test_create_requires_title(self):
        c = self._login(self.emp_user)
        resp = c.post(
            "/reimbursements/create/", {"title": "", "amount": "100", "expense_date": "2026-09-10"}
        )
        assert resp.status_code == 200  # form error
        assert b"required" in resp.content.lower() or b"error" in resp.content.lower()

    def test_detail_employee_can_view_own(self):
        r = Reimbursement.objects.create(
            employee=self.emp, title="Trip", amount=Decimal("100"), expense_date="2026-09-10"
        )
        c = self._login(self.emp_user)
        resp = c.get(f"/reimbursements/{r.id}/")
        assert resp.status_code == 200
        assert b"Trip" in resp.content

    def test_detail_employee_cannot_view_other(self):
        r = Reimbursement.objects.create(
            employee=self.other_emp, title="Other", amount=Decimal("100"), expense_date="2026-09-10"
        )
        c = self._login(self.emp_user)
        resp = c.get(f"/reimbursements/{r.id}/")
        assert resp.status_code == 404

    def test_detail_hr_can_view_any(self):
        r = Reimbursement.objects.create(
            employee=self.other_emp, title="Other", amount=Decimal("100"), expense_date="2026-09-10"
        )
        c = self._login(self.hr)
        resp = c.get(f"/reimbursements/{r.id}/")
        assert resp.status_code == 200

    def test_detail_shows_receipt_link(self):
        pdf = SimpleUploadedFile("bill.pdf", b"pdf", content_type="application/pdf")
        r = Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            amount=Decimal("100"),
            expense_date="2026-09-10",
            receipt=pdf,
        )
        c = self._login(self.hr)
        resp = c.get(f"/reimbursements/{r.id}/")
        assert b"Receipt" in resp.content or b"bill.pdf" in resp.content

    def test_approve_hr_success(self):
        r = Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            amount=Decimal("100"),
            expense_date="2026-09-10",
            status="PENDING",
        )
        c = self._login(self.hr)
        resp = c.post(f"/reimbursements/{r.id}/action/", {"action": "approve"})
        assert resp.status_code in (302, 200)
        r.refresh_from_db()
        assert r.status == "APPROVED"
        assert r.reviewed_by == self.hr

    def test_reject_hr_success(self):
        r = Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            amount=Decimal("100"),
            expense_date="2026-09-10",
            status="PENDING",
        )
        c = self._login(self.hr)
        resp = c.post(f"/reimbursements/{r.id}/action/", {"action": "reject"})
        assert resp.status_code in (302, 200)
        r.refresh_from_db()
        assert r.status == "REJECTED"

    def test_approve_already_approved_fails_gracefully(self):
        r = Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            amount=Decimal("100"),
            expense_date="2026-09-10",
            status="APPROVED",
        )
        c = self._login(self.hr)
        resp = c.post(f"/reimbursements/{r.id}/action/", {"action": "approve"})
        assert resp.status_code in (302, 200)

    def test_employee_cannot_approve(self):
        r = Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            amount=Decimal("100"),
            expense_date="2026-09-10",
            status="PENDING",
        )
        c = self._login(self.emp_user)
        resp = c.post(f"/reimbursements/{r.id}/action/", {"action": "approve"})
        assert resp.status_code in (302, 403)

    def test_approve_htmx_swap(self):
        r = Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            amount=Decimal("100"),
            expense_date="2026-09-10",
            status="PENDING",
        )
        c = self._login(self.hr)
        resp = c.post(
            f"/reimbursements/{r.id}/action/", {"action": "approve"}, HTTP_HX_REQUEST="true"
        )
        assert resp.status_code == 200
        assert b"APPROVED" in resp.content or b"Approved" in resp.content

    def test_invalid_action(self):
        r = Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            amount=Decimal("100"),
            expense_date="2026-09-10",
            status="PENDING",
        )
        c = self._login(self.hr)
        resp = c.post(f"/reimbursements/{r.id}/action/", {"action": "invalid"})
        assert resp.status_code in (302, 200)

    def test_employee_create_shows_form_errors(self):
        c = self._login(self.emp_user)
        resp = c.post(
            "/reimbursements/create/",
            {"title": "Trip", "amount": "-100", "expense_date": "2026-09-10"},
        )
        assert resp.status_code == 200  # stays on form with errors

    @pytest.mark.parametrize("amount", ["0", "-10", "0.00"])
    def test_create_invalid_amounts(self, amount):
        c = self._login(self.emp_user)
        resp = c.post(
            "/reimbursements/create/",
            {"title": "Trip", "amount": amount, "expense_date": "2026-09-10"},
        )
        assert resp.status_code == 200  # form error, not created
