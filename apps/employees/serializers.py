from rest_framework import serializers

from .models import Department, Employee, SalaryStructure, TaxBracket


class DepartmentSerializer(serializers.ModelSerializer):
    employee_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = ["id", "name", "code", "description", "created_at", "employee_count"]
        read_only_fields = ["id", "created_at"]


class TaxBracketSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxBracket
        fields = ["id", "country", "lower_limit", "upper_limit", "rate", "description"]


class SalaryStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryStructure
        fields = [
            "id",
            "employee",
            "basic_salary",
            "house_rent_allowance",
            "dearness_allowance",
            "transport_allowance",
            "telephone_allowance",
            "special_allowance",
            "pf_deduction",
            "professional_tax",
            "gross_salary",
            "tax_deduction",
            "net_in_hand",
            "total_compensation",
            "effective_from",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "gross_salary",
            "tax_deduction",
            "net_in_hand",
            "total_compensation",
            "effective_from",
            "updated_at",
        ]

    def validate(self, attrs):
        # ensure gross components are sensible
        for f in [
            "basic_salary",
            "house_rent_allowance",
            "dearness_allowance",
            "transport_allowance",
            "telephone_allowance",
            "special_allowance",
        ]:
            if f in attrs and attrs[f] < 0:
                raise serializers.ValidationError({f: "Must be non-negative"})
        return attrs


class EmployeeListSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    department_code = serializers.CharField(source="department.code", read_only=True)
    net_in_hand = serializers.DecimalField(
        source="salary.net_in_hand",
        max_digits=12,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_id",
            "full_name",
            "first_name",
            "last_name",
            "email",
            "phone",
            "country",
            "job_title",
            "department",
            "department_name",
            "department_code",
            "employment_type",
            "status",
            "date_of_joining",
            "net_in_hand",
        ]
        read_only_fields = ["id", "full_name", "net_in_hand"]


class EmployeeDetailSerializer(serializers.ModelSerializer):
    department_detail = DepartmentSerializer(source="department", read_only=True)
    salary = SalaryStructureSerializer(read_only=True)
    manager_name = serializers.CharField(
        source="manager.full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_id",
            "user",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "address",
            "city",
            "country",
            "job_title",
            "department",
            "department_detail",
            "employment_type",
            "status",
            "date_of_joining",
            "manager",
            "manager_name",
            "created_at",
            "updated_at",
            "salary",
        ]
        read_only_fields = ["id", "full_name", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        # Hide salary for non-HR viewing others
        if request and not request.user.is_hr:
            # employee can see own salary, not others
            own = False
            try:
                if hasattr(request.user, "employee_profile") and request.user.employee_profile:
                    own = request.user.employee_profile.id == instance.id
            except Exception:
                pass
            if not own:
                data.pop("salary", None)
        return data


class EmployeeCreateSerializer(serializers.ModelSerializer):
    # nested salary creation
    salary = SalaryStructureSerializer(required=False)

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "address",
            "city",
            "country",
            "job_title",
            "department",
            "employment_type",
            "status",
            "date_of_joining",
            "manager",
            "salary",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        salary_data = validated_data.pop("salary", None)
        employee = Employee.objects.create(**validated_data)
        if salary_data:
            # remove employee if passed
            salary_data.pop("employee", None)
            SalaryStructure.objects.create(employee=employee, **salary_data)
        else:
            # create default salary
            from decimal import Decimal

            SalaryStructure.objects.create(employee=employee, basic_salary=Decimal("50000.00"))
        return employee

    def update(self, instance, validated_data):
        salary_data = validated_data.pop("salary", None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if salary_data:
            sal = getattr(instance, "salary", None)
            if sal:
                for attr, val in salary_data.items():
                    setattr(sal, attr, val)
                sal.save()
            else:
                SalaryStructure.objects.create(employee=instance, **salary_data)
        return instance
