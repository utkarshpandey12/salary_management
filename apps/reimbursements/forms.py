from django import forms
from django.utils import timezone

from apps.employees.models import Employee

from .models import Reimbursement


class ReimbursementForm(forms.ModelForm):
    class Meta:
        model = Reimbursement
        fields = ["title", "purpose", "amount", "expense_date", "receipt"]
        widgets = {
            "expense_date": forms.DateInput(
                attrs={"type": "date", "class": "w-full border rounded px-3 py-2"}
            ),
            "title": forms.TextInput(attrs={"class": "w-full border rounded px-3 py-2"}),
            "purpose": forms.Textarea(
                attrs={"rows": 3, "class": "w-full border rounded px-3 py-2"}
            ),
            "amount": forms.NumberInput(
                attrs={"step": "0.01", "class": "w-full border rounded px-3 py-2"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # if HR, allow employee selector
        if user and user.is_hr:
            self.fields["employee"] = forms.ModelChoiceField(
                queryset=Employee.objects.order_by("employee_id"),
                required=False,
                widget=forms.Select(attrs={"class": "w-full border rounded px-3 py-2"}),
            )
            # move employee to first
            self.fields = {"employee": self.fields["employee"], **self.fields}

    def clean_expense_date(self):
        value = self.cleaned_data.get("expense_date")
        if value and value > timezone.now().date():
            raise forms.ValidationError("Expense date cannot be in the future.")
        return value

    def save(self, commit=True, **kwargs):
        obj = super().save(commit=False)
        if self.user and self.user.is_hr and self.cleaned_data.get("employee"):
            obj.employee = self.cleaned_data["employee"]
        elif self.user and not self.user.is_hr:
            # employee link handled in view
            pass
        if commit:
            obj.save()
        return obj
