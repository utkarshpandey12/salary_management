from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.employees.models import Department, Employee, SalaryStructure
from apps.reimbursements.models import Reimbursement

User = get_user_model()


@pytest.mark.django_db
class TestReimbursementModel:
    def setup_method(self):
        self.dept = Department.objects.create(name="Eng", code="ENG")
        self.emp = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="John",
            last_name="Doe",
            email="john@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        SalaryStructure.objects.create(employee=self.emp, basic_salary=Decimal("50000"))

    def test_create_pending_default(self):
        r = Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            purpose="Visit",
            amount=Decimal("1000"),
            expense_date="2026-09-10",
        )
        assert r.status == "PENDING"
        assert r.is_pending is True
        assert str(r).startswith("Trip")

    def test_amount_must_be_positive(self):
        r = Reimbursement(
            employee=self.emp, title="Trip", amount=Decimal("0"), expense_date="2026-09-10"
        )
        try:
            r.full_clean()
            assert False
        except ValidationError as e:
            assert "amount" in e.message_dict

    def test_amount_negative_fails(self):
        r = Reimbursement(
            employee=self.emp, title="Trip", amount=Decimal("-100"), expense_date="2026-09-10"
        )
        try:
            r.full_clean()
            assert False
        except ValidationError:
            assert True

    def test_title_required(self):
        r = Reimbursement(
            employee=self.emp, title="", amount=Decimal("100"), expense_date="2026-09-10"
        )
        # title blank allowed? CharField not blank? Should test blank vs empty
        # Our model allows blank? title not blank=True, so full_clean should fail
        try:
            r.full_clean()
            assert False
        except ValidationError:
            assert True

    def test_purpose_optional(self):
        r = Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            amount=Decimal("100"),
            expense_date="2026-09-10",
            purpose="",
        )
        assert r.purpose == ""

    def test_receipt_upload_to(self):
        pdf = SimpleUploadedFile("bill.pdf", b"pdf content", content_type="application/pdf")
        r = Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            amount=Decimal("500"),
            expense_date="2026-09-10",
            receipt=pdf,
        )
        assert "reimbursements/ACME-00001" in r.receipt.name

    def test_status_choices(self):
        for status in ["PENDING", "APPROVED", "REJECTED"]:
            r = Reimbursement.objects.create(
                employee=self.emp,
                title=f"Trip{status}",
                amount=Decimal("100"),
                expense_date="2026-09-10",
                status=status,
            )
            assert r.status == status

    def test_reviewed_by_optional(self):
        hr = User.objects.create_user(username="hr", password="pass", role="HR")
        r = Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            amount=Decimal("100"),
            expense_date="2026-09-10",
            reviewed_by=hr,
        )
        assert r.reviewed_by == hr

    def test_ordering_by_created_at_desc(self):
        r1 = Reimbursement.objects.create(
            employee=self.emp, title="A", amount=Decimal("100"), expense_date="2026-09-10"
        )
        r2 = Reimbursement.objects.create(
            employee=self.emp, title="B", amount=Decimal("200"), expense_date="2026-09-10"
        )
        assert list(Reimbursement.objects.values_list("title", flat=True)) == ["B", "A"]

    @pytest.mark.parametrize(
        "amount", [Decimal("0.01"), Decimal("1"), Decimal("1000"), Decimal("99999.99")]
    )
    def test_various_amounts(self, amount):
        r = Reimbursement.objects.create(
            employee=self.emp, title="Trip", amount=amount, expense_date="2026-09-10"
        )
        assert r.amount == amount

    def test_expense_date_required(self):
        r = Reimbursement(employee=self.emp, title="Trip", amount=Decimal("100"))
        try:
            r.full_clean()
            assert False
        except ValidationError:
            assert True

    def test_is_pending_property(self):
        r = Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            amount=Decimal("100"),
            expense_date="2026-09-10",
            status="PENDING",
        )
        assert r.is_pending is True
        r.status = "APPROVED"
        assert r.is_pending is False

    def test_cascade_on_employee_delete(self):
        r = Reimbursement.objects.create(
            employee=self.emp, title="Trip", amount=Decimal("100"), expense_date="2026-09-10"
        )
        self.emp.delete()
        assert not Reimbursement.objects.filter(id=r.id).exists()

    def test_reviewed_by_set_null_on_user_delete(self):
        hr = User.objects.create_user(username="hr", password="pass", role="HR")
        r = Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            amount=Decimal("100"),
            expense_date="2026-09-10",
            reviewed_by=hr,
            status="APPROVED",
        )
        hr.delete()
        r.refresh_from_db()
        assert r.reviewed_by is None

    def test_indexes_filter(self):
        # relies on indexes existing, just ensure query works
        Reimbursement.objects.create(
            employee=self.emp,
            title="Trip",
            amount=Decimal("100"),
            expense_date="2026-09-10",
            status="PENDING",
        )
        assert Reimbursement.objects.filter(status="PENDING").exists()
        assert Reimbursement.objects.filter(employee=self.emp).exists()
