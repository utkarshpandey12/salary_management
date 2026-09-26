from django.urls import path

from .views_ui import (
    PayrollExportCreateView,
    PayrollExportDownloadView,
    PayrollExportListView,
    PayrollExportStatusView,
    PayrollView,
)

urlpatterns = [
    path("payroll/", PayrollView.as_view(), name="payroll"),
    path("payroll/exports/", PayrollExportListView.as_view(), name="payroll-exports"),
    path(
        "payroll/exports/create/", PayrollExportCreateView.as_view(), name="payroll-export-create"
    ),
    path(
        "payroll/exports/<int:pk>/", PayrollExportStatusView.as_view(), name="payroll-export-status"
    ),
    path(
        "payroll/exports/<int:pk>/download/",
        PayrollExportDownloadView.as_view(),
        name="payroll-export-download",
    ),
]
