from django.contrib import admin

from .models import Reimbursement


@admin.register(Reimbursement)
class ReimbursementAdmin(admin.ModelAdmin):
    list_display = ("title", "employee", "amount", "expense_date", "status", "reviewed_by")
    list_filter = ("status", "expense_date")
    search_fields = ("title", "employee__employee_id", "employee__full_name")
    readonly_fields = ("created_at", "updated_at")
