from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import ListView, TemplateView, View

from .models import PayrollExport
from .tasks import generate_payroll_export, get_payroll_rows


class HRRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_hr

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect(f"/accounts/login/?next={self.request.path}")
        messages.error(self.request, "HR access required.")
        return redirect("dashboard")


class PayrollView(HRRequiredMixin, TemplateView):
    template_name = "payroll/payroll.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        month_str = self.request.GET.get("month")
        if month_str:
            try:
                if len(month_str) == 7:
                    y, m = map(int, month_str.split("-"))
                    month_date = date(y, m, 1)
                else:
                    month_date = date.fromisoformat(month_str).replace(day=1)
            except:
                month_date = date(timezone.now().year, timezone.now().month, 1)
        else:
            today = timezone.now().date()
            month_date = date(today.year, today.month, 1)

        rows = get_payroll_rows(month_date)
        # paginate
        paginator = Paginator(rows, 50)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        total_salary = sum((r["salary_amount"] for r in rows), Decimal("0"))
        total_reimb = sum((r["reimbursement_amount"] for r in rows), Decimal("0"))
        total_all = sum((r["total_amount"] for r in rows), Decimal("0"))

        # recent exports
        exports = (
            PayrollExport.objects.filter(requested_by=self.request.user).order_by("-created_at")[:5]
            if self.request.user.is_authenticated
            else []
        )

        ctx.update(
            {
                "month": month_date,
                "month_str": month_date.strftime("%Y-%m"),
                "page_obj": page_obj,
                "rows": page_obj.object_list,
                "total_salary": total_salary,
                "total_reimb": total_reimb,
                "total_all": total_all,
                "count": len(rows),
                "exports": exports,
            }
        )
        return ctx

    def get_template_names(self):
        if self.request.htmx and self.request.GET.get("partial") == "table":
            return ["payroll/partials/payroll_table.html"]
        return [self.template_name]


class PayrollExportCreateView(HRRequiredMixin, View):
    def post(self, request):
        fmt = request.POST.get("format", "EXCEL").upper()
        month_str = request.POST.get("month")
        if fmt not in ("EXCEL", "PDF"):
            messages.error(request, "Invalid format")
            return redirect("payroll")
        try:
            if month_str and len(month_str) == 7:
                y, m = map(int, month_str.split("-"))
                month_date = date(y, m, 1)
            elif month_str:
                month_date = date.fromisoformat(month_str).replace(day=1)
            else:
                today = timezone.now().date()
                month_date = date(today.year, today.month, 1)
        except:
            messages.error(request, "Invalid month")
            return redirect("payroll")

        export = PayrollExport.objects.create(
            requested_by=request.user, month=month_date, format=fmt
        )
        # trigger task
        try:
            generate_payroll_export.delay(export.id)
            messages.info(request, f"Export queued (#{export.id}). Will be ready shortly.")
        except Exception:
            # fallback sync
            generate_payroll_export(export.id)
            messages.success(request, f"Export ready (#{export.id})")

        if request.htmx:
            # return polling snippet
            return render(request, "payroll/partials/export_status.html", {"export": export})
        return redirect("payroll")


class PayrollExportListView(HRRequiredMixin, ListView):
    model = PayrollExport
    template_name = "payroll/export_list.html"
    context_object_name = "exports"
    paginate_by = 20

    def get_queryset(self):
        return PayrollExport.objects.filter(requested_by=self.request.user).order_by("-created_at")


class PayrollExportStatusView(HRRequiredMixin, View):
    def get(self, request, pk):
        export = get_object_or_404(PayrollExport, pk=pk, requested_by=request.user)
        if request.htmx:
            return render(request, "payroll/partials/export_status.html", {"export": export})
        return render(request, "payroll/export_status.html", {"export": export})


class PayrollExportDownloadView(HRRequiredMixin, View):
    def get(self, request, pk):
        export = get_object_or_404(PayrollExport, pk=pk)
        if export.status != PayrollExport.Status.COMPLETED or not export.file:
            raise Http404("Export not ready")
        return FileResponse(
            export.file.open("rb"), as_attachment=True, filename=export.file.name.split("/")[-1]
        )
