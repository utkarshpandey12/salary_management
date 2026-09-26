from django.utils import timezone
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from apps.accounts.permissions import IsHR
from .models import Reimbursement
from .serializers import ReimbursementSerializer

class ReimbursementViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = ReimbursementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Reimbursement.objects.select_related("employee", "reviewed_by").all()
        # employee sees only own; HR sees all
        if not user.is_hr:
            try:
                emp = user.employee_profile
                qs = qs.filter(employee=emp)
            except Exception:
                qs = qs.none()
        # filters
        status_f = self.request.query_params.get("status")
        employee = self.request.query_params.get("employee")
        if status_f:
            qs = qs.filter(status=status_f)
        if employee and user.is_hr:
            qs = qs.filter(employee_id=employee) if employee.isdigit() else qs.filter(employee__employee_id=employee)
        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        user = self.request.user
        # employee must have profile
        try:
            emp = user.employee_profile
        except Exception:
            if user.is_hr:
                # HR can specify employee field; otherwise error
                if "employee" not in serializer.validated_data:
                    raise PermissionDenied("HR must specify employee for reimbursement")
                serializer.save()
                return
            raise PermissionDenied("Employee profile not found")
        # force employee to own
        serializer.save(employee=emp, status=Reimbursement.Status.PENDING)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsHR], url_path="approve")
    def approve(self, request, pk=None):
        obj = self.get_object()
        if obj.status != Reimbursement.Status.PENDING:
            return Response({"detail": f"Already {obj.status}"}, status=status.HTTP_400_BAD_REQUEST)
        obj.status = Reimbursement.Status.APPROVED
        obj.reviewed_by = request.user
        obj.reviewed_at = timezone.now()
        obj.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
        return Response(ReimbursementSerializer(obj).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsHR], url_path="reject")
    def reject(self, request, pk=None):
        obj = self.get_object()
        if obj.status != Reimbursement.Status.PENDING:
            return Response({"detail": f"Already {obj.status}"}, status=status.HTTP_400_BAD_REQUEST)
        obj.status = Reimbursement.Status.REJECTED
        obj.reviewed_by = request.user
        obj.reviewed_at = timezone.now()
        obj.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
        return Response(ReimbursementSerializer(obj).data)
