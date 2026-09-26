from django.urls import path
from .views_ui import ReimbursementListView, ReimbursementCreateView, ReimbursementDetailView, ReimbursementActionView

urlpatterns = [
    path("reimbursements/", ReimbursementListView.as_view(), name="reimbursement-list"),
    path("reimbursements/create/", ReimbursementCreateView.as_view(), name="reimbursement-create"),
    path("reimbursements/<int:pk>/", ReimbursementDetailView.as_view(), name="reimbursement-detail"),
    path("reimbursements/<int:pk>/action/", ReimbursementActionView.as_view(), name="reimbursement-action"),
]
