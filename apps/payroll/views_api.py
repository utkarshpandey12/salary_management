from datetime import date
from calendar import monthrange
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Q
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from apps.accounts.permissions import IsHR
from apps.employees.models import Employee
from apps.reimbursements.models import Reimbursement
from .models import PayrollExport
from .serializers import PayrollExportSerializer
from .tasks import get_payroll_rows, generate_payroll_export

class PayrollDataView(APIView):
    permission_classes = [IsAuthenticated, IsHR]

    def get(self, request):
        # query param month=YYYY-MM or YYYY-MM-DD
        month_str = request.query_params.get("month")
        if month_str:
            try:
                if len(month_str) == 7:  # YYYY-MM
                    year, month = map(int, month_str.split("-"))
                    month_date = date(year, month, 1)
                else:
                    month_date = date.fromisoformat(month_str).replace(day=1)
            except Exception:
                return Response({"detail": "Invalid month format. Use YYYY-MM"}, status=400)
        else:
            today = timezone.now().date()
            month_date = date(today.year, today.month, 1)

        rows = get_payroll_rows(month_date)
        # pagination for API — simple slice
        page = int(request.query_params.get("page", "1"))
        page_size = int(request.query_params.get("page_size", "50"))
        page_size = min(page_size, 200)
        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size
        paged = rows[start:end]

        # totals
        total_salary = sum((r["salary_amount"] for r in rows), Decimal("0"))
        total_reimb = sum((r["reimbursement_amount"] for r in rows), Decimal("0"))
        total_all = sum((r["total_amount"] for r in rows), Decimal("0"))

        return Response({
            "month": month_date.isoformat(),
            "count": total,
            "page": page,
            "page_size": page_size,
            "totals": {
                "salary_amount": total_salary,
                "reimbursement_amount": total_reimb,
                "total_amount": total_all,
            },
            "results": paged,
        })


class PayrollExportViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = PayrollExport.objects.select_related("requested_by").order_by("-created_at")
    serializer_class = PayrollExportSerializer
    permission_classes = [IsAuthenticated, IsHR]

    def get_queryset(self):
        qs = super().get_queryset()
        # HR sees all; in case employee somehow hits, filter own (but permission blocks)
        return qs

    def perform_create(self, serializer):
        month = serializer.validated_data["month"]
        fmt = serializer.validated_data["format"]
        export = serializer.save(requested_by=self.request.user, month=month.replace(day=1), format=fmt)
        # trigger celery task
        # Use eager fallback if broker not available: the task will run synchronously due to CELERY_TASK_ALWAYS_EAGER
        try:
            generate_payroll_export.delay(export.id)
        except Exception:
            # fallback to inline if celery broker unavailable
            generate_payroll_export(export.id)
