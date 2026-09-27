from rest_framework.routers import DefaultRouter

from .views_api import ReimbursementViewSet

router = DefaultRouter()
router.register(r"", ReimbursementViewSet, basename="api-reimbursements")

urlpatterns = router.urls
