from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    code = models.CharField(max_length=20, unique=True, help_text="Short code e.g. ENG")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Department"
        verbose_name_plural = "Departments"

    def __str__(self):
        return f"{self.name} ({self.code})"


class TaxBracket(models.Model):
    country = models.CharField(max_length=100, db_index=True)
    lower_limit = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    upper_limit = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, help_text="Null = no upper bound"
    )
    rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage e.g. 10.00 for 10%",
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["country", "lower_limit"]
        constraints = [
            models.UniqueConstraint(
                fields=["country", "lower_limit"], name="uniq_tax_bracket_country_lower"
            ),
        ]
        indexes = [
            models.Index(fields=["country", "lower_limit"]),
        ]

    def __str__(self):
        upper = f"-{self.upper_limit}" if self.upper_limit else "+"
        return f"{self.country} {self.lower_limit}{upper} @ {self.rate}%"

    @staticmethod
    def compute_tax(country: str, gross: Decimal) -> Decimal:
        """Progressive tax: sum over brackets for given country; fallback to default world brackets if none."""
        brackets = list(TaxBracket.objects.filter(country=country).order_by("lower_limit"))
        if not brackets:
            brackets = list(TaxBracket.objects.filter(country="GLOBAL").order_by("lower_limit"))
        if not brackets:
            # default simple slabs if DB empty (shouldn't happen after seed)
            # 0-600k:0%, 600k-1.2M:5%, 1.2M-1.8M:10%, 1.8M+:20% (assuming annualised gross monthly*12? but we treat gross as annual)
            # For simplicity treat monthly gross as taxable base directly
            return Decimal("0.00")
        tax = Decimal("0.00")
        remaining = gross
        for b in brackets:
            if gross <= b.lower_limit:
                break
            upper = b.upper_limit if b.upper_limit is not None else gross
            taxable_in_bracket = min(gross, upper) - b.lower_limit
            if taxable_in_bracket > 0:
                tax += taxable_in_bracket * b.rate / Decimal("100")
        return tax.quantize(Decimal("0.01"))


class Employee(models.Model):
    class EmploymentType(models.TextChoices):
        FULL_TIME = "FULL_TIME", "Full-time"
        CONTRACT = "CONTRACT", "Contract"
        PART_TIME = "PART_TIME", "Part-time"
        INTERN = "INTERN", "Intern"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        ON_LEAVE = "ON_LEAVE", "On Leave"

    # Identity
    employee_id = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        validators=[RegexValidator(r"^ACME-\d{5,}$", message="Must be ACME-xxxxx")],
        help_text="Searchable ID e.g. ACME-00001",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_profile",
    )
    first_name = models.CharField(max_length=100, db_index=True)
    last_name = models.CharField(max_length=100, db_index=True)
    full_name = models.CharField(max_length=210, db_index=True, editable=False)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, db_index=True)
    job_title = models.CharField(max_length=100, db_index=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    employment_type = models.CharField(
        max_length=20, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    date_of_joining = models.DateField()
    manager = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reports"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["employee_id"]
        indexes = [
            models.Index(fields=["country", "job_title"]),
            models.Index(fields=["department", "country"]),
            models.Index(fields=["full_name"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.CheckConstraint(condition=~Q(email=""), name="employee_email_not_empty"),
        ]

    # TDD: manager self/cycle validation lands in the manager-improvement step.

    def save(self, *args, **kwargs):
        self.full_name = f"{self.first_name} {self.last_name}".strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee_id} — {self.full_name} ({self.job_title}, {self.country})"


class SalaryStructure(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name="salary")
    # Components (monthly)
    basic_salary = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    house_rent_allowance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="House Allowance (HRA)",
    )
    dearness_allowance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Dearness Allowance (DA)",
    )
    transport_allowance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Transport Allowance (TA)",
    )
    telephone_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    special_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    pf_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="PF Deduction"
    )
    professional_tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    # Computed (stored for fast payroll queries)
    gross_salary = models.DecimalField(
        max_digits=12, decimal_places=2, editable=False, default=Decimal("0.00")
    )
    tax_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, editable=False, default=Decimal("0.00")
    )
    net_in_hand = models.DecimalField(
        max_digits=12, decimal_places=2, editable=False, default=Decimal("0.00")
    )
    total_compensation = models.DecimalField(
        max_digits=12, decimal_places=2, editable=False, default=Decimal("0.00")
    )
    effective_from = models.DateField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Salary Structure"

    def compute_gross(self) -> Decimal:
        return (
            self.basic_salary
            + self.house_rent_allowance
            + self.dearness_allowance
            + self.transport_allowance
            + self.telephone_allowance
            + self.special_allowance
        )

    def recompute(self):
        gross = self.compute_gross()
        # annualise for tax? Our brackets are annual-like; but we treat monthly gross annualised *12 for realistic tax
        # However payroll expects monthly deduction; so we compute monthly tax as annual_tax/12
        annual_gross = gross * Decimal("12")
        # need employee country; if not yet saved, fallback
        country = getattr(getattr(self, "employee", None), "country", "GLOBAL")
        annual_tax = TaxBracket.compute_tax(country, annual_gross)
        monthly_tax = (annual_tax / Decimal("12")).quantize(Decimal("0.01"))
        self.gross_salary = gross.quantize(Decimal("0.01"))
        self.total_compensation = gross.quantize(Decimal("0.01"))
        self.tax_deduction = monthly_tax
        net = gross - self.pf_deduction - self.professional_tax - monthly_tax
        self.net_in_hand = max(net, Decimal("0.00")).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        self.recompute()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Salary for {self.employee_id} — Gross {self.gross_salary} Net {self.net_in_hand}"


# TDD: SalaryHistory audit model + save hook land in the salary-history improvement step.
