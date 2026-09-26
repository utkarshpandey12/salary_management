from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from .forms import EmployeeForm, SalaryStructureForm
from .models import Department, Employee, SalaryStructure


class HRRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_hr

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect(f"/accounts/login/?next={self.request.path}")
        messages.error(self.request, "HR access required.")
        return redirect("dashboard")


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_hr:
            total = Employee.objects.count()
            avg = SalaryStructure.objects.aggregate(avg=Avg("net_in_hand"))["avg"]
            depts = Department.objects.annotate(
                count=Count("employees"), avg_sal=Avg("employees__salary__net_in_hand")
            ).order_by("-count")
            recent_reimb = None
            try:
                from apps.reimbursements.models import Reimbursement

                recent_reimb = (
                    Reimbursement.objects.filter(status="PENDING")
                    .select_related("employee")
                    .order_by("-created_at")[:5]
                )
            except Exception:
                pass
            ctx.update(
                {
                    "is_hr": True,
                    "total_employees": total,
                    "avg_salary": avg,
                    "departments": depts,
                    "pending_reimbursements": recent_reimb,
                }
            )
        else:
            # employee dashboard
            try:
                emp = user.employee_profile
                ctx.update(
                    {
                        "is_hr": False,
                        "my_employee": emp,
                        "my_salary": getattr(emp, "salary", None) if emp else None,
                    }
                )
            except Exception:
                ctx.update({"is_hr": False, "my_employee": None})
        return ctx


class EmployeeListView(LoginRequiredMixin, ListView):
    model = Employee
    template_name = "employees/employee_list.html"
    context_object_name = "employees"
    paginate_by = 25

    def get_queryset(self):
        qs = Employee.objects.select_related("department", "salary").all().order_by("employee_id")
        q = self.request.GET.get("q", "").strip()
        dept = self.request.GET.get("department", "")
        country = self.request.GET.get("country", "")
        title = self.request.GET.get("job_title", "")
        status_f = self.request.GET.get("status", "")
        if q:
            qs = qs.filter(
                Q(employee_id__icontains=q)
                | Q(full_name__icontains=q)
                | Q(email__icontains=q)
                | Q(job_title__icontains=q)
            )
        if dept:
            qs = (
                qs.filter(department_id=dept)
                if dept.isdigit()
                else qs.filter(department__code=dept)
            )
        if country:
            qs = qs.filter(country__iexact=country)
        if title:
            qs = qs.filter(job_title__icontains=title)
        if status_f:
            qs = qs.filter(status=status_f)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["departments"] = Department.objects.all().order_by("name")
        ctx["q"] = self.request.GET.get("q", "")
        ctx["selected_department"] = self.request.GET.get("department", "")
        ctx["selected_country"] = self.request.GET.get("country", "")
        ctx["selected_title"] = self.request.GET.get("job_title", "")
        # distinct for filters
        ctx["countries"] = (
            Employee.objects.values_list("country", flat=True).distinct().order_by("country")
        )
        ctx["job_titles"] = (
            Employee.objects.values_list("job_title", flat=True)
            .distinct()
            .order_by("job_title")[:30]
        )
        return ctx

    def get_template_names(self):
        if self.request.htmx:
            return ["employees/partials/employee_table.html"]
        return [self.template_name]


class EmployeeDetailView(LoginRequiredMixin, DetailView):
    model = Employee
    template_name = "employees/employee_detail.html"
    context_object_name = "employee"
    slug_field = "employee_id"
    slug_url_kwarg = "employee_id"

    def get_object(self):
        # allow lookup by pk or employee_id
        eid = self.kwargs.get("employee_id")
        # try employee_id first
        try:
            return Employee.objects.select_related("department", "salary", "manager").get(
                employee_id=eid
            )
        except Employee.DoesNotExist:
            # fallback to pk
            return get_object_or_404(
                Employee.objects.select_related("department", "salary", "manager"), pk=eid
            )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        emp = self.object
        user = self.request.user
        # salary visibility
        can_view_salary = user.is_hr
        if not can_view_salary:
            try:
                can_view_salary = (
                    hasattr(user, "employee_profile")
                    and user.employee_profile
                    and user.employee_profile.id == emp.id
                )
            except Exception:
                pass
        ctx["can_view_salary"] = can_view_salary
        ctx["can_edit"] = user.is_hr or (
            hasattr(user, "employee_profile")
            and user.employee_profile
            and user.employee_profile.id == emp.id
        )
        ctx["is_hr"] = user.is_hr
        # salary form for HR
        if can_view_salary and hasattr(emp, "salary"):
            ctx["salary"] = emp.salary
        # reimbursement count
        try:
            ctx["reimbursements"] = emp.reimbursements.order_by("-created_at")[:5]
        except Exception:
            ctx["reimbursements"] = []
        return ctx


class EmployeeCreateView(HRRequiredMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "employees/employee_form.html"
    success_url = reverse_lazy("employee-list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_create"] = True
        return ctx

    def form_valid(self, form):
        # save employee
        resp = super().form_valid(form)
        # create salary with defaults if not exists
        if not hasattr(self.object, "salary"):
            from decimal import Decimal

            SalaryStructure.objects.create(employee=self.object, basic_salary=Decimal("70000.00"))
        messages.success(self.request, f"Employee {self.object.employee_id} created.")
        return resp


class EmployeeUpdateView(LoginRequiredMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "employees/employee_form.html"
    slug_field = "employee_id"
    slug_url_kwarg = "employee_id"

    def get_object(self):
        eid = self.kwargs.get("employee_id")
        try:
            return Employee.objects.get(employee_id=eid)
        except Employee.DoesNotExist:
            return get_object_or_404(Employee, pk=eid)

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        user = request.user
        if user.is_hr:
            return super().dispatch(request, *args, **kwargs)
        # employee can only edit own limited fields
        try:
            own = (
                hasattr(user, "employee_profile")
                and user.employee_profile
                and user.employee_profile.id == obj.id
            )
        except Exception:
            own = False
        if not own:
            messages.error(request, "You can only edit your own profile.")
            return redirect("employee-detail", employee_id=obj.employee_id)
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, *args, **kwargs):
        form = super().get_form(*args, **kwargs)
        user = self.request.user
        if not user.is_hr:
            # limit fields to phone, address, city
            allowed = {"phone", "address", "city"}
            for field in list(form.fields.keys()):
                if field not in allowed:
                    form.fields.pop(field)
        return form

    def get_success_url(self):
        return reverse_lazy("employee-detail", kwargs={"employee_id": self.object.employee_id})

    def form_valid(self, form):
        messages.success(self.request, "Profile updated.")
        return super().form_valid(form)


class SalaryUpdateView(HRRequiredMixin, UpdateView):
    model = SalaryStructure
    form_class = SalaryStructureForm
    template_name = "employees/salary_form.html"

    def get_object(self):
        eid = self.kwargs.get("employee_id")
        emp = (
            get_object_or_404(Employee, employee_id=eid)
            if not eid.isdigit() or eid.startswith("ACME")
            else get_object_or_404(Employee, pk=eid)
        )
        # Actually try both
        try:
            emp = Employee.objects.get(employee_id=eid)
        except Employee.DoesNotExist:
            try:
                emp = Employee.objects.get(pk=eid)
            except:
                # fallback: try as passed directly
                emp = get_object_or_404(Employee, employee_id=self.kwargs.get("employee_id"))
        salary, _ = SalaryStructure.objects.get_or_create(
            employee=emp, defaults={"basic_salary": Decimal("50000")}
        )
        return salary

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["employee"] = self.object.employee
        return ctx

    def get_success_url(self):
        return reverse_lazy(
            "employee-detail", kwargs={"employee_id": self.object.employee.employee_id}
        )

    def form_valid(self, form):
        # recompute will happen in save
        messages.success(self.request, "Salary updated.")
        return super().form_valid(form)


class DepartmentListView(LoginRequiredMixin, ListView):
    model = Department
    template_name = "employees/department_list.html"
    context_object_name = "departments"

    def get_queryset(self):
        return Department.objects.annotate(
            count=Count("employees"),
            avg_sal=Avg("employees__salary__net_in_hand"),
            max_sal=Max("employees__salary__net_in_hand"),
            min_sal=Min("employees__salary__net_in_hand"),
        ).order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_hr"] = self.request.user.is_hr
        return ctx


class DepartmentDetailView(LoginRequiredMixin, DetailView):
    model = Department
    template_name = "employees/department_detail.html"
    context_object_name = "department"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dept = self.object
        emps = (
            Employee.objects.filter(department=dept)
            .select_related("salary", "manager")
            .order_by("employee_id")
        )
        # HTMX pagination? Use simple paginator
        from django.core.paginator import Paginator

        paginator = Paginator(emps, 25)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        ctx["page_obj"] = page_obj
        ctx["employees"] = page_obj.object_list
        ctx["is_hr"] = self.request.user.is_hr
        # stats
        ctx["stats"] = Employee.objects.filter(department=dept, salary__isnull=False).aggregate(
            count=Count("id"),
            avg=Avg("salary__net_in_hand"),
            min=Min("salary__net_in_hand"),
            max=Max("salary__net_in_hand"),
        )
        # median calc
        salaries = list(
            Employee.objects.filter(department=dept, salary__isnull=False)
            .order_by("salary__net_in_hand")
            .values_list("salary__net_in_hand", flat=True)
        )
        median = None
        if salaries:
            n = len(salaries)
            mid = n // 2
            median = (
                salaries[mid] if n % 2 == 1 else (salaries[mid - 1] + salaries[mid]) / Decimal("2")
            )
        ctx["median"] = median
        return ctx


class AnalyticsView(HRRequiredMixin, TemplateView):
    template_name = "employees/analytics.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # filters
        country = self.request.GET.get("country", "")
        job_title = self.request.GET.get("job_title", "")
        department = self.request.GET.get("department", "")
        qs = Employee.objects.select_related("salary", "department").filter(salary__isnull=False)
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

        agg = qs.aggregate(
            count=Count("id"),
            avg=Avg("salary__net_in_hand"),
            min=Min("salary__net_in_hand"),
            max=Max("salary__net_in_hand"),
            avg_gross=Avg("salary__gross_salary"),
        )
        total = qs.aggregate(total=Sum("salary__net_in_hand"))["total"] or Decimal("0")
        salaries = list(
            qs.order_by("salary__net_in_hand").values_list("salary__net_in_hand", flat=True)
        )
        median = p25 = p75 = None
        if salaries:
            n = len(salaries)
            mid = n // 2
            median = (
                salaries[mid] if n % 2 == 1 else (salaries[mid - 1] + salaries[mid]) / Decimal("2")
            )
            import math

            def pct(arr, p):
                if not arr:
                    return None
                k = (len(arr) - 1) * p / 100
                f = math.floor(k)
                c = math.ceil(k)
                if f == c:
                    return arr[int(k)]
                return arr[int(f)] * Decimal(str(c - k)) + arr[int(c)] * Decimal(str(k - f))

            p25 = pct(salaries, 25)
            p75 = pct(salaries, 75)

        by_country = list(
            Employee.objects.filter(salary__isnull=False)
            .values("country")
            .annotate(
                count=Count("id"),
                avg=Avg("salary__net_in_hand"),
                min=Min("salary__net_in_hand"),
                max=Max("salary__net_in_hand"),
            )
            .order_by("-avg")
        )
        by_dept = list(
            Employee.objects.filter(salary__isnull=False)
            .values("department__name", "department__code")
            .annotate(
                count=Count("id"),
                avg=Avg("salary__net_in_hand"),
                min=Min("salary__net_in_hand"),
                max=Max("salary__net_in_hand"),
            )
            .order_by("-avg")
        )
        by_title = list(
            Employee.objects.filter(salary__isnull=False)
            .values("job_title")
            .annotate(
                count=Count("id"),
                avg=Avg("salary__net_in_hand"),
                min=Min("salary__net_in_hand"),
                max=Max("salary__net_in_hand"),
            )
            .order_by("-avg")[:20]
        )

        specific = None
        if country and job_title:
            specific = Employee.objects.filter(
                country__iexact=country, job_title__iexact=job_title, salary__isnull=False
            ).aggregate(avg=Avg("salary__net_in_hand"))["avg"]

        ctx.update(
            {
                "country": country,
                "job_title": job_title,
                "department": department,
                "agg": agg,
                "total": total,
                "median": median,
                "p25": p25,
                "p75": p75,
                "by_country": by_country,
                "by_dept": by_dept,
                "by_title": by_title,
                "specific_avg": specific,
                "departments": Department.objects.all().order_by("name"),
                "countries": Employee.objects.values_list("country", flat=True)
                .distinct()
                .order_by("country"),
                "job_titles": Employee.objects.values_list("job_title", flat=True)
                .distinct()
                .order_by("job_title")[:50],
            }
        )
        return ctx
