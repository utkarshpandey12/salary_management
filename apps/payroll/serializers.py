from rest_framework import serializers

from .models import PayrollExport


class PayrollRowSerializer(serializers.Serializer):
    empID = serializers.CharField()
    full_name = serializers.CharField()
    salary_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reimbursement_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class PayrollExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollExport
        fields = [
            "id",
            "requested_by",
            "month",
            "format",
            "status",
            "celery_task_id",
            "file",
            "error",
            "created_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "requested_by",
            "status",
            "celery_task_id",
            "file",
            "error",
            "created_at",
            "completed_at",
        ]

    def validate_month(self, value):
        # ensure first day of month
        return value.replace(day=1)
