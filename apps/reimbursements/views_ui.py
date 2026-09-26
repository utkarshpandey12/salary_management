from django.views.generic import ListView, CreateView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse

from .models import Reimbursement
from .forms import ReimbursementForm
from apps.employees.models import Employee

class ReimbursementListView(LoginRequiredMixin, ListView):
    model = Reimbursement
    template_name = "reimbursements/reimbursement_list.html"
    context_object_name = "reimbursements"
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        qs = Reimbursement.objects.select_related("employee", "reviewed_by").order_by("-created_at")
        if not user.is_hr:
            try:
                emp = user.employee_profile
                qs = qs.filter(employee=emp)
            except Exception:
                qs = qs.none()
        else:
            # HR filters
            status_f = self.request.GET.get("status")
            q = self.request.GET.get("q")
            if status_f:
                qs = qs.filter(status=status_f)
            if q:
                qs = qs.filter(title__icontains=q)
        # self filter
        status_f = self.request.GET.get("status")
        if status_f and not user.is_hr:
            # employee can also filter own
            qs = qs.filter(status=status_f)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_hr"] = self.request.user.is_hr
        ctx["status"] = self.request.GET.get("status","")
        return ctx

    def get_template_names(self):
        if self.request.htmx:
            return ["reimbursements/partials/reimbursement_table.html"]
        return [self.template_name]


class ReimbursementCreateView(LoginRequiredMixin, CreateView):
    model = Reimbursement
    form_class = ReimbursementForm
    template_name = "reimbursements/reimbursement_form.html"
    success_url = reverse_lazy("reimbursement-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        obj = form.save(commit=False)
        if not user.is_hr:
            try:
                emp = user.employee_profile
            except Exception:
                messages.error(self.request, "No employee profile linked to your account.")
                return redirect("dashboard")
            obj.employee = emp
        else:
            # HR creating for employee must have employee field
            if not obj.employee_id:
                # try to set from form's employee if provided
                emp = form.cleaned_data.get("employee")
                if emp:
                    obj.employee = emp
                else:
                    messages.error(self.request, "Select an employee.")
                    return self.form_invalid(form)
        obj.status = Reimbursement.Status.PENDING
        obj.save()
        messages.success(self.request, "Reimbursement request submitted.")
        return redirect(self.success_url)


class ReimbursementDetailView(LoginRequiredMixin, DetailView):
    model = Reimbursement
    template_name = "reimbursements/reimbursement_detail.html"
    context_object_name = "reimbursement"

    def get_queryset(self):
        qs = Reimbursement.objects.select_related("employee", "reviewed_by")
        user = self.request.user
        if not user.is_hr:
            try:
                emp = user.employee_profile
                qs = qs.filter(employee=emp)
            except Exception:
                qs = qs.none()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_hr"] = self.request.user.is_hr
        return ctx


class ReimbursementActionView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_hr

    def post(self, request, pk):
        obj = get_object_or_404(Reimbursement, pk=pk)
        action = request.POST.get("action") or request.GET.get("action")
        # also support JSON via htmx
        if obj.status != Reimbursement.Status.PENDING:
            messages.warning(request, f"Already {obj.status}")
            if request.htmx:
                return render(request, "reimbursements/partials/reimbursement_row.html", {"r": obj, "is_hr": True})
            return redirect("reimbursement-detail", pk=obj.pk)
        if action == "approve":
            obj.status = Reimbursement.Status.APPROVED
        elif action == "reject":
            obj.status = Reimbursement.Status.REJECTED
        else:
            messages.error(request, "Invalid action")
            return redirect("reimbursement-detail", pk=obj.pk)
        obj.reviewed_by = request.user
        obj.reviewed_at = timezone.now()
        obj.save(update_fields=["status","reviewed_by","reviewed_at","updated_at"])
        messages.success(request, f"Reimbursement {obj.status.lower()}.")
        if request.htmx:
            return render(request, "reimbursements/partials/reimbursement_row.html", {"r": obj, "is_hr": True})
        return redirect("reimbursement-detail", pk=obj.pk)
