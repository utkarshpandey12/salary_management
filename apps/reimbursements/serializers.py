from rest_framework import serializers

from .models import Reimbursement


class ReimbursementSerializer(serializers.ModelSerializer):
    employee_id_display = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.username", read_only=True, allow_null=True
    )

    class Meta:
        model = Reimbursement
        fields = [
            "id",
            "employee",
            "employee_id_display",
            "employee_name",
            "title",
            "purpose",
            "amount",
            "expense_date",
            "receipt",
            "status",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
            "employee_id_display",
            "employee_name",
        ]
        extra_kwargs = {"employee": {"required": False, "allow_null": True}}

    def validate(self, attrs):
        # limit file size/type in API? also handled in model
        return attrs
