from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_api import PayrollDataView, PayrollExportViewSet

router = DefaultRouter()
router.register(r"exports", PayrollExportViewSet, basename="api-payroll-exports")

urlpatterns = [
    path("data/", PayrollDataView.as_view(), name="api-payroll-data"),
    path("", include(router.urls)),
]
