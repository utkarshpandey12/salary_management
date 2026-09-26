from django.urls import include, path

urlpatterns = [
    path("auth/", include("apps.accounts.urls_api")),
    path("employees/", include("apps.employees.urls_api")),
    path("reimbursements/", include("apps.reimbursements.urls_api")),
    path("payroll/", include("apps.payroll.urls_api")),
]
