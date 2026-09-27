from django.contrib import admin

from .models import PayrollExport


@admin.register(PayrollExport)
class PayrollExportAdmin(admin.ModelAdmin):
    list_display = ("month", "format", "requested_by", "status", "created_at")
    list_filter = ("status", "format", "month")
