from decimal import Decimal

from django.db.models import Avg, Count, Max, Min
from django.db.models.functions import Coalesce
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsHR

from .models import Department, Employee, SalaryStructure, TaxBracket
from .serializers import (
    DepartmentSerializer,
    EmployeeCreateSerializer,
    EmployeeDetailSerializer,
    EmployeeListSerializer,
    SalaryStructureSerializer,
    TaxBracketSerializer,
)


# Use mixins as requested
class DepartmentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "code"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        # annotate employee count for analytics
        return qs.annotate(employee_count=Count("employees"))

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsHR()]
        return [IsAuthenticated()]


class EmployeeViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "employee_id",
        "full_name",
        "first_name",
        "last_name",
        "email",
        "job_title",
        "country",
    ]
    ordering_fields = ["employee_id", "full_name", "date_of_joining", "country", "job_title"]

    def get_queryset(self):
        qs = Employee.objects.select_related("department", "salary", "manager").all()
        # filters via query_params
        params = self.request.query_params
        department = params.get("department")
        country = params.get("country")
        job_title = params.get("job_title")
        status_f = params.get("status")
        search = params.get("search")
        # search already handled by SearchFilter but also support employee_id exact
        if params.get("employee_id"):
            qs = qs.filter(employee_id__iexact=params.get("employee_id"))
        if department:
            qs = (
                qs.filter(department_id=department)
                if department.isdigit()
                else qs.filter(department__code=department)
            )
        if country:
            qs = qs.filter(country__iexact=country)
        if job_title:
            qs = qs.filter(job_title__iexact=job_title)
        if status_f:
            qs = qs.filter(status=status_f)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return EmployeeListSerializer
        if self.action in ("create",):
            return EmployeeCreateSerializer
        if self.action in ("update", "partial_update"):
            # allow partial salary via same serializer
            return EmployeeCreateSerializer
        return EmployeeDetailSerializer

    def get_permissions(self):
        if self.action in ("create", "destroy"):
            return [IsAuthenticated(), IsHR()]
        if self.action in ("update", "partial_update"):
            # HR can update all; employee can update own limited fields — enforced in perform_update
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        if user.is_hr:
            serializer.save()
            return
        # employee self-update: only allow address, phone, city?
        own = False
        try:
            if hasattr(user, "employee_profile") and user.employee_profile:
                own = user.employee_profile.id == instance.id
        except Exception:
            pass
        if not own:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Only HR or own profile can be updated.")
        # whitelisted fields
        allowed = {"phone", "address", "city"}
        for field in list(serializer.validated_data.keys()):
            if field not in allowed:
                serializer.validated_data.pop(field, None)
        # also block salary nested if non-HR
        serializer.validated_data.pop("salary", None)
        serializer.save()

    @action(detail=True, methods=["get", "put", "patch"], url_path="salary")
    def salary_detail(self, request, pk=None):
        employee = self.get_object()
        # permission: HR or own
        if not request.user.is_hr:
            own = False
            try:
                own = request.user.employee_profile.id == employee.id
            except Exception:
                pass
            if not own and request.method in ("PUT", "PATCH"):
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied("Only HR can update salary.")
            if not own and request.method == "GET":
                # hide? but detail serializer already hides; we explicitly block
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied("Salary visible only to HR or owner.")

        try:
            salary = employee.salary
        except SalaryStructure.DoesNotExist:
            salary = None

        if request.method == "GET":
            if not salary:
                return Response(
                    {"detail": "No salary structure found"}, status=status.HTTP_404_NOT_FOUND
                )
            ser = SalaryStructureSerializer(salary)
            return Response(ser.data)

        # PUT/PATCH
        if not request.user.is_hr:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Only HR can edit salary")
        data = request.data
        if salary:
            ser = SalaryStructureSerializer(salary, data=data, partial=(request.method == "PATCH"))
        else:
            data = {**data, "employee": employee.id}
            ser = SalaryStructureSerializer(data=data)
        ser.is_valid(raise_exception=True)
        # ensure employee link
        if not salary:
            ser.save(employee=employee)
        else:
            ser.save()
        return Response(ser.data)


class TaxBracketViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = TaxBracket.objects.all().order_by("country", "lower_limit")
    serializer_class = TaxBracketSerializer
    permission_classes = [IsAuthenticated, IsHR]
    filter_backends = [filters.SearchFilter]
    search_fields = ["country"]


# Analytics — as separate viewset with list + retrieve style, but using GenericViewSet mixins
class AnalyticsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, IsHR]

    def list(self, request):
        """
        Query params: country, job_title, department (id or code), group_by=country|department|job_title
        Returns aggregated salary stats.
        """
        qs = Employee.objects.select_related("salary", "department").filter(salary__isnull=False)
        country = request.query_params.get("country")
        job_title = request.query_params.get("job_title")
        department = request.query_params.get("department")
        if country:
            qs = qs.filter(country__iexact=country)
        if job_title:
            qs = qs.filter(job_title__iexact=job_title)
        if department:
            qs = (
                qs.filter(department_id=department)
                if department.isdigit()
                else qs.filter(department__code=department)
            )

        # Overall stats
        agg = qs.aggregate(
            count=Count("id"),
            avg_salary=Avg("salary__net_in_hand"),
            min_salary=Min("salary__net_in_hand"),
            max_salary=Max("salary__net_in_hand"),
            avg_gross=Avg("salary__gross_salary"),
            total_payroll=Coalesce(Avg("salary__net_in_hand"), Decimal("0"))
            * Count("id"),  # placeholder
        )
        # more accurate total
        from django.db.models import Sum

        total = qs.aggregate(total=Sum("salary__net_in_hand"))["total"] or Decimal("0")
        agg["total_payroll"] = total

        # Median: need ordered values – fetch only net salaries, not whole objects, for performance
        # For 10k scale, fetching one column is fine; do in DB via window? We'll do Python median on sorted list for accuracy and speed.
        salaries = list(
            qs.order_by("salary__net_in_hand").values_list("salary__net_in_hand", flat=True)
        )
        median = None
        p25 = p75 = None
        if salaries:
            n = len(salaries)
            mid = n // 2
            if n % 2 == 1:
                median = salaries[mid]
            else:
                median = (salaries[mid - 1] + salaries[mid]) / Decimal("2")
            # percentiles
            import math

            def percentile(arr, p):
                if not arr:
                    return None
                k = (len(arr) - 1) * p / 100
                f = math.floor(k)
                c = math.ceil(k)
                if f == c:
                    return arr[int(k)]
                d0 = arr[int(f)] * Decimal(str(c - k))
                d1 = arr[int(c)] * Decimal(str(k - f))
                return d0 + d1

            p25 = percentile(salaries, 25)
            p75 = percentile(salaries, 75)

        # breakdowns
        by_country = list(
            qs.values("country")
            .annotate(
                count=Count("id"),
                avg=Avg("salary__net_in_hand"),
                min=Min("salary__net_in_hand"),
                max=Max("salary__net_in_hand"),
            )
            .order_by("-avg")[:20]
        )
        by_department = list(
            qs.values("department__name", "department__code")
            .annotate(
                count=Count("id"),
                avg=Avg("salary__net_in_hand"),
                min=Min("salary__net_in_hand"),
                max=Max("salary__net_in_hand"),
            )
            .order_by("-avg")
        )
        by_title = list(
            qs.values("job_title")
            .annotate(
                count=Count("id"),
                avg=Avg("salary__net_in_hand"),
                min=Min("salary__net_in_hand"),
                max=Max("salary__net_in_hand"),
            )
            .order_by("-avg")[:20]
        )

        # also handle specific question: avg for given job title in country
        specific_avg = None
        if country and job_title:
            specific_avg = qs.filter(
                country__iexact=country, job_title__iexact=job_title
            ).aggregate(avg=Avg("salary__net_in_hand"))["avg"]

        return Response(
            {
                "filters": {"country": country, "job_title": job_title, "department": department},
                "overall": {
                    "count": agg["count"],
                    "avg_net": agg["avg_salary"],
                    "min_net": agg["min_salary"],
                    "max_net": agg["max_salary"],
                    "avg_gross": agg["avg_gross"],
                    "median_net": median,
                    "p25": p25,
                    "p75": p75,
                    "total_payroll": total,
                    "specific_avg_job_country": specific_avg,
                },
                "by_country": by_country,
                "by_department": by_department,
                "by_job_title": by_title,
            }
        )
