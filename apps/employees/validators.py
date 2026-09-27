"""Employee validators — extracted in TDD refactor phase for sonar-clean reuse."""

from django.core.exceptions import ValidationError as DjangoValidationError

MAX_CHAIN_DEPTH = 50


def validate_manager_assignment(employee, manager):
    """Raise DjangoValidationError if manager is self or creates a cycle.

    employee: Employee instance or None (create ignores self-check, cycle impossible for new pk).
    manager: Employee instance or None.
    Uses only manager_id chain with .only() for lean queries.
    """
    if manager is None:
        return manager
    if employee is not None and employee.pk and manager.pk == employee.pk:
        raise DjangoValidationError({"manager": "Employee cannot be their own manager."})
    if employee is not None and employee.pk:
        from .models import Employee

        seen = {employee.pk}
        current = manager
        for _ in range(MAX_CHAIN_DEPTH):
            if current.pk in seen:
                raise DjangoValidationError({"manager": "Manager assignment would create a cycle."})
            seen.add(current.pk)
            if not current.manager_id:
                break
            try:
                current = Employee.objects.only("manager_id").get(pk=current.manager_id)
            except Employee.DoesNotExist:
                break
    return manager
