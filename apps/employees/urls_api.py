from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views_api import (
    AnalyticsViewSet,
    DepartmentViewSet,
    EmployeeViewSet,
    TaxBracketViewSet,
)

router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="api-departments")
router.register(r"", EmployeeViewSet, basename="api-employees")
router.register(
    r"tax-brackets/tax", TaxBracketViewSet, basename="api-tax"
)  # will mount under employees/

# analytics separate path

urlpatterns = [
    path("analytics/", AnalyticsViewSet.as_view({"get": "list"}), name="api-analytics"),
    path("", include(router.urls)),
]
