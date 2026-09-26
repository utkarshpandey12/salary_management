from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_api import DepartmentViewSet, EmployeeViewSet, TaxBracketViewSet, AnalyticsViewSet

router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="api-departments")
router.register(r"", EmployeeViewSet, basename="api-employees")
router.register(r"tax-brackets/tax", TaxBracketViewSet, basename="api-tax")  # will mount under employees/

# analytics separate path
from django.urls import re_path

urlpatterns = [
    path("analytics/", AnalyticsViewSet.as_view({"get": "list"}), name="api-analytics"),
    path("", include(router.urls)),
]
