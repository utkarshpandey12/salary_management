from django import forms
from .models import Employee, SalaryStructure

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["employee_id","first_name","last_name","email","phone","address","city","country","job_title","department","employment_type","status","date_of_joining","manager"]
        widgets = {
            "date_of_joining": forms.DateInput(attrs={"type":"date", "class":"w-full border rounded px-3 py-2"}),
            "employee_id": forms.TextInput(attrs={"class":"w-full border rounded px-3 py-2", "placeholder":"ACME-00001"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name not in ("date_of_joining",):
                field.widget.attrs.setdefault("class","w-full border rounded px-3 py-2")
        # manager queryset
        self.fields["manager"].queryset = Employee.objects.select_related("department").order_by("full_name")[:500]
        self.fields["department"].queryset = self.fields["department"].queryset.order_by("name")

class SalaryStructureForm(forms.ModelForm):
    class Meta:
        model = SalaryStructure
        fields = ["basic_salary","house_rent_allowance","dearness_allowance","transport_allowance","telephone_allowance","special_allowance","pf_deduction","professional_tax"]
        widgets = {
            "basic_salary": forms.NumberInput(attrs={"step":"0.01","class":"w-full border rounded px-3 py-2"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class","w-full border rounded px-3 py-2")
            field.widget.attrs.setdefault("step","0.01")
