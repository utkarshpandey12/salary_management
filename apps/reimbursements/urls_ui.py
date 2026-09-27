"""Reimbursement UI routes — PLACEHOLDERS that unblock base nav reverses.

Real list/create/detail/action views land in the reimbursement-ui TDD step,
which replaces these stubs (its RED tests fail on placeholder content).
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.urls import path
from django.views import View


class ReimbursementPlaceholderView(LoginRequiredMixin, View):
    def get(self, request, pk=None):  # noqa: ARG002
        return HttpResponse("Reimbursements — full view lands in the reimbursement-ui step.")

    def post(self, request, pk=None):  # noqa: ARG002
        return HttpResponse("Reimbursements — full view lands in the reimbursement-ui step.")


urlpatterns = [
    path(
        "reimbursements/",
        ReimbursementPlaceholderView.as_view(),
        name="reimbursement-list",
    ),
    path(
        "reimbursements/create/",
        ReimbursementPlaceholderView.as_view(),
        name="reimbursement-create",
    ),
    path(
        "reimbursements/<int:pk>/",
        ReimbursementPlaceholderView.as_view(),
        name="reimbursement-detail",
    ),
    path(
        "reimbursements/<int:pk>/action/",
        ReimbursementPlaceholderView.as_view(),
        name="reimbursement-action",
    ),
]
