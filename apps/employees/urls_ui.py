from django.urls import path
from .views_ui import (
    DashboardView,
    EmployeeListView,
    EmployeeDetailView,
    EmployeeCreateView,
    EmployeeUpdateView,
    SalaryUpdateView,
    DepartmentListView,
    DepartmentDetailView,
    AnalyticsView,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("employees/", EmployeeListView.as_view(), name="employee-list"),
    path("employees/create/", EmployeeCreateView.as_view(), name="employee-create"),
    path("employees/<str:employee_id>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path("employees/<str:employee_id>/edit/", EmployeeUpdateView.as_view(), name="employee-edit"),
    path("employees/<str:employee_id>/salary/edit/", SalaryUpdateView.as_view(), name="salary-edit"),
    path("departments/", DepartmentListView.as_view(), name="department-list"),
    path("departments/<int:pk>/", DepartmentDetailView.as_view(), name="department-detail"),
    path("analytics/", AnalyticsView.as_view(), name="analytics"),
]
