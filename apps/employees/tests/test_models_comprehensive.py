import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.employees.models import Department, Employee

User = get_user_model()


@pytest.mark.django_db
class TestDepartmentModel:
    def test_create_department(self):
        d = Department.objects.create(name="Engineering", code="ENG", description="Builds")
        assert d.name == "Engineering"
        assert str(d) == "Engineering (ENG)"
        assert d.code == "ENG"

    def test_name_unique(self):
        Department.objects.create(name="Eng", code="ENG")
        with pytest.raises(IntegrityError):
            Department.objects.create(name="Eng", code="ENG2")

    def test_code_unique(self):
        Department.objects.create(name="Eng", code="ENG")
        with pytest.raises(IntegrityError):
            Department.objects.create(name="Other", code="ENG")

    def test_ordering_by_name(self):
        Department.objects.create(name="Zeta", code="ZET")
        Department.objects.create(name="Alpha", code="ALP")
        names = list(Department.objects.values_list("name", flat=True))
        assert names == sorted(names)

    def test_employee_count_annotation(self):
        dept = Department.objects.create(name="Eng", code="ENG")
        dept2 = Department.objects.create(name="Sales", code="SAL")
        from django.db.models import Count

        Employee.objects.create(
            employee_id="ACME-00001",
            first_name="A",
            last_name="B",
            email="a@a.com",
            country="India",
            job_title="Eng",
            department=dept,
            date_of_joining="2020-01-01",
        )
        Employee.objects.create(
            employee_id="ACME-00002",
            first_name="C",
            last_name="D",
            email="c@a.com",
            country="India",
            job_title="Eng",
            department=dept,
            date_of_joining="2020-01-01",
        )
        qs = Department.objects.annotate(count=Count("employees")).filter(id=dept.id).first()
        assert qs.count == 2
        qs2 = Department.objects.annotate(count=Count("employees")).filter(id=dept2.id).first()
        assert qs2.count == 0

    @pytest.mark.parametrize("name,code", [("HR", "HR"), ("Finance", "FIN"), ("Marketing", "MKT")])
    def test_various_departments(self, name, code):
        d = Department.objects.create(name=name, code=code)
        assert Department.objects.filter(code=code).exists()


@pytest.mark.django_db
class TestEmployeeModel:
    def setup_method(self):
        self.dept = Department.objects.create(name="Eng", code="ENG")

    def test_full_name_auto(self):
        e = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="John",
            last_name="Doe",
            email="john@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        assert e.full_name == "John Doe"
        e.first_name = "Jane"
        e.save()
        assert e.full_name == "Jane Doe"

    def test_employee_id_unique(self):
        Employee.objects.create(
            employee_id="ACME-00001",
            first_name="A",
            last_name="B",
            email="a@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        with pytest.raises(IntegrityError):
            Employee.objects.create(
                employee_id="ACME-00001",
                first_name="C",
                last_name="D",
                email="c@a.com",
                country="India",
                job_title="Eng",
                department=self.dept,
                date_of_joining="2020-01-01",
            )

    def test_email_unique(self):
        Employee.objects.create(
            employee_id="ACME-00001",
            first_name="A",
            last_name="B",
            email="dup@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        with pytest.raises(IntegrityError):
            Employee.objects.create(
                employee_id="ACME-00002",
                first_name="C",
                last_name="D",
                email="dup@a.com",
                country="India",
                job_title="Eng",
                department=self.dept,
                date_of_joining="2020-01-01",
            )

    def test_employee_id_format_validation(self):
        e = Employee(
            employee_id="BAD-001",
            first_name="A",
            last_name="B",
            email="bad@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        try:
            e.full_clean()
            assert False
        except ValidationError as ve:
            assert "employee_id" in ve.message_dict

    def test_valid_employee_id(self):
        e = Employee(
            employee_id="ACME-12345",
            first_name="A",
            last_name="B",
            email="valid@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
            department_id=self.dept.id,
        )
        e.full_clean()  # should not raise

    def test_manager_self_fk(self):
        mgr = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="Mgr",
            last_name="One",
            email="mgr@a.com",
            country="India",
            job_title="Manager",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        emp = Employee.objects.create(
            employee_id="ACME-00002",
            first_name="John",
            last_name="Doe",
            email="john@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
            manager=mgr,
        )
        assert emp.manager == mgr
        assert mgr.reports.count() == 1

    def test_manager_cascade_set_null(self):
        mgr = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="Mgr",
            last_name="One",
            email="mgr@a.com",
            country="India",
            job_title="Manager",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        emp = Employee.objects.create(
            employee_id="ACME-00002",
            first_name="John",
            last_name="Doe",
            email="john@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
            manager=mgr,
        )
        mgr.delete()
        emp.refresh_from_db()
        assert emp.manager is None

    def test_user_one_to_one(self):
        u = User.objects.create_user(username="emp", password="pass")
        e = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="John",
            last_name="Doe",
            email="john@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
            user=u,
        )
        assert e.user == u
        assert u.employee_profile == e

    def test_user_set_null_on_delete(self):
        u = User.objects.create_user(username="emp", password="pass")
        e = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="John",
            last_name="Doe",
            email="john@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
            user=u,
        )
        u.delete()
        e.refresh_from_db()
        assert e.user is None

    def test_status_choices(self):
        for status in ["ACTIVE", "INACTIVE", "ON_LEAVE"]:
            e = Employee.objects.create(
                employee_id=f"ACME-00{Employee.objects.count() + 1:03d}",
                first_name="A",
                last_name="B",
                email=f"a{Employee.objects.count()}@a.com",
                country="India",
                job_title="Eng",
                department=self.dept,
                date_of_joining="2020-01-01",
                status=status,
            )
            assert e.status == status

    def test_employment_type_choices(self):
        for typ in ["FULL_TIME", "CONTRACT", "PART_TIME", "INTERN"]:
            e = Employee.objects.create(
                employee_id=f"ACME-00{Employee.objects.count() + 1:03d}",
                first_name="A",
                last_name="B",
                email=f"a{Employee.objects.count()}@a.com",
                country="India",
                job_title="Eng",
                department=self.dept,
                date_of_joining="2020-01-01",
                employment_type=typ,
            )
            assert e.employment_type == typ

    def test_country_filter(self):
        Employee.objects.create(
            employee_id="ACME-00001",
            first_name="A",
            last_name="B",
            email="a@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        Employee.objects.create(
            employee_id="ACME-00002",
            first_name="C",
            last_name="D",
            email="c@a.com",
            country="USA",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        assert Employee.objects.filter(country="India").count() == 1
        assert Employee.objects.filter(country="USA").count() == 1

    @pytest.mark.parametrize("country", ["India", "USA", "Germany", "UK", "Canada"])
    def test_country_variations(self, country):
        Employee.objects.create(
            employee_id=f"ACME-00{Employee.objects.count() + 1:03d}",
            first_name="A",
            last_name="B",
            email=f"{country}_{Employee.objects.count()}@a.com",
            country=country,
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        assert Employee.objects.filter(country=country).exists()

    def test_str_includes_employee_id(self):
        e = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="John",
            last_name="Doe",
            email="john@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        assert "ACME-00001" in str(e)
        assert "John Doe" in str(e)

    def test_ordering_by_employee_id(self):
        Employee.objects.create(
            employee_id="ACME-00002",
            first_name="B",
            last_name="B",
            email="b@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        Employee.objects.create(
            employee_id="ACME-00001",
            first_name="A",
            last_name="A",
            email="a@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        ids = list(Employee.objects.values_list("employee_id", flat=True))
        assert ids == sorted(ids)

    def test_department_protect(self):
        e = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="A",
            last_name="B",
            email="a@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
        )
        try:
            self.dept.delete()
            assert False
        except Exception:
            assert True
        assert Employee.objects.filter(id=e.id).exists()

    def test_phone_optional(self):
        e = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="A",
            last_name="B",
            email="a@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
            phone="",
        )
        assert e.phone == ""

    def test_address_optional(self):
        e = Employee.objects.create(
            employee_id="ACME-00001",
            first_name="A",
            last_name="B",
            email="a@a.com",
            country="India",
            job_title="Eng",
            department=self.dept,
            date_of_joining="2020-01-01",
            address="",
        )
        assert e.address == ""
