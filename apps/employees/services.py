"""Salary domain services — extracted in TDD refactor phase for testability and sonar-clean code."""

TRACKED_SALARY_FIELDS = [
    "basic_salary",
    "house_rent_allowance",
    "dearness_allowance",
    "transport_allowance",
    "telephone_allowance",
    "special_allowance",
    "pf_deduction",
    "professional_tax",
]


def salary_changed(old, new, fields=None) -> bool:
    fields = fields or TRACKED_SALARY_FIELDS
    return any(getattr(old, f) != getattr(new, f) for f in fields)


def log_salary_change(old, new):
    """Create SalaryHistory entry; lazy import avoids circular imports."""
    from .models import SalaryHistory

    return SalaryHistory.objects.create(
        employee=new.employee,
        old_basic=old.basic_salary,
        new_basic=new.basic_salary,
        old_gross=old.gross_salary,
        new_gross=new.gross_salary,
        old_net=old.net_in_hand,
        new_net=new.net_in_hand,
    )
