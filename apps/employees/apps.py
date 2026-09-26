from django.apps import AppConfig


class EmployeesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.employees"
    verbose_name = "Employees"

    def ready(self):
        import apps.employees.signals  # noqa
