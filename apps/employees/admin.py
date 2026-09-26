from django.contrib import admin

from .models import Department, Employee, SalaryStructure, TaxBracket


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "created_at")
    search_fields = ("name", "code")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "full_name", "job_title", "department", "country", "status")
    list_filter = ("department", "country", "job_title", "status", "employment_type")
    search_fields = ("employee_id", "full_name", "email", "job_title")
    raw_id_fields = ("manager", "user")


@admin.register(SalaryStructure)
class SalaryStructureAdmin(admin.ModelAdmin):
    list_display = ("employee", "gross_salary", "tax_deduction", "net_in_hand")
    search_fields = ("employee__employee_id", "employee__full_name")
    readonly_fields = ("gross_salary", "tax_deduction", "net_in_hand", "total_compensation")


@admin.register(TaxBracket)
class TaxBracketAdmin(admin.ModelAdmin):
    list_display = ("country", "lower_limit", "upper_limit", "rate")
    list_filter = ("country",)
