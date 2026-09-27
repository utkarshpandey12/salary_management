"""Payroll UI routes — PLACEHOLDERS that unblock base nav reverses.

Real PayrollView/exports land in the payroll-ui TDD step, which replaces
these stubs (its RED tests fail on placeholder content).
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.urls import path
from django.views import View


class PayrollPlaceholderView(LoginRequiredMixin, View):
    def get(self, request, pk=None):  # noqa: ARG002
        return HttpResponse("Payroll — full view lands in the payroll-ui step.")

    def post(self, request, pk=None):  # noqa: ARG002
        return HttpResponse("Payroll — full view lands in the payroll-ui step.")


urlpatterns = [
    path("payroll/", PayrollPlaceholderView.as_view(), name="payroll"),
    path("payroll/exports/", PayrollPlaceholderView.as_view(), name="payroll-exports"),
    path(
        "payroll/exports/create/",
        PayrollPlaceholderView.as_view(),
        name="payroll-export-create",
    ),
    path(
        "payroll/exports/<int:pk>/",
        PayrollPlaceholderView.as_view(),
        name="payroll-export-status",
    ),
    path(
        "payroll/exports/<int:pk>/download/",
        PayrollPlaceholderView.as_view(),
        name="payroll-export-download",
    ),
]
