from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers as drf_serializers


def validate_not_future(value, field_name="expense_date"):
    if value and value > timezone.now().date():
        msg = "Expense date cannot be in the future."
        # raise both Django + DRF compatible (same message)
        raise DjangoValidationError({field_name: msg} if field_name else msg)
    return value


def validate_not_future_drf(value):
    if value and value > timezone.now().date():
        raise drf_serializers.ValidationError("Expense date cannot be in the future.")
    return value
