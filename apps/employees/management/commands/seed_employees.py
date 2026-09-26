import random
import time
from decimal import Decimal
from pathlib import Path
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from django.conf import settings

from apps.employees.models import Department, Employee, SalaryStructure, TaxBracket

# Constants for realistic seeding
COUNTRIES = ["USA", "India", "Germany", "UK", "Canada", "Australia", "Singapore", "UAE", "Brazil", "Japan"]
JOB_TITLES = [
    "Software Engineer", "Senior Software Engineer", "Engineering Manager", "Product Manager",
    "Designer", "Data Analyst", "Data Scientist", "DevOps Engineer", "QA Engineer",
    "Sales Executive", "Sales Manager", "HR Specialist", "Finance Analyst", "Marketing Manager",
    "Support Engineer", "Operations Manager", "Legal Counsel", "Researcher"
]
DEPARTMENTS = [
    ("Engineering", "ENG", "Builds the product"),
    ("Product", "PROD", "Product vision and roadmaps"),
    ("Design", "DES", "User experience and design"),
    ("Sales", "SAL", "Revenue and client relations"),
    ("Marketing", "MKT", "Growth and branding"),
    ("Finance", "FIN", "Budgeting and payroll"),
    ("HR", "HR", "People operations"),
    ("Support", "SUP", "Customer support"),
    ("Operations", "OPS", "Day to day operations"),
    ("Legal", "LEG", "Compliance and legal"),
    ("Data", "DAT", "Data and analytics"),
]

# Salary bands by title (monthly basic ranges)
TITLE_SALARY_BAND = {
    "Software Engineer": (60000, 110000),
    "Senior Software Engineer": (95000, 160000),
    "Engineering Manager": (140000, 220000),
    "Product Manager": (90000, 170000),
    "Designer": (50000, 100000),
    "Data Analyst": (55000, 105000),
    "Data Scientist": (80000, 150000),
    "DevOps Engineer": (70000, 130000),
    "QA Engineer": (45000, 90000),
    "Sales Executive": (40000, 85000),
    "Sales Manager": (80000, 140000),
    "HR Specialist": (45000, 90000),
    "Finance Analyst": (60000, 115000),
    "Marketing Manager": (70000, 125000),
    "Support Engineer": (35000, 75000),
    "Operations Manager": (75000, 135000),
    "Legal Counsel": (90000, 160000),
    "Researcher": (65000, 120000),
}
DEFAULT_BAND = (40000, 90000)
COUNTRY_MULTIPLIER = {
    "USA": 1.2,
    "India": 0.45,
    "Germany": 1.05,
    "UK": 1.1,
    "Canada": 1.0,
    "Australia": 1.05,
    "Singapore": 1.1,
    "UAE": 1.0,
    "Brazil": 0.6,
    "Japan": 1.0,
}

class Command(BaseCommand):
    help = "Seed 10,000 employees with salary structures (optimized bulk_create). Uses first_names.txt / last_names.txt if present."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=10000, help="Number of employees to seed")
        parser.add_argument("--clear", action="store_true", help="Clear existing employees before seeding")
        parser.add_argument("--batch-size", type=int, default=1000, help="bulk_create batch size")

    def handle(self, *args, **options):
        count = options["count"]
        clear = options["clear"]
        batch_size = options["batch_size"]
        t0 = time.time()

        User = get_user_model()

        if clear:
            self.stdout.write(self.style.WARNING("Clearing existing employees, salary structures, departments and tax brackets..."))
            SalaryStructure.objects.all().delete()
            Employee.objects.all().delete()
            Department.objects.all().delete()
            TaxBracket.objects.all().delete()
            # keep HR users? We will recreate demo users
            User.objects.filter(username__in=["hr_admin", "employee_demo"]).delete()

        # Ensure tax brackets exist
        if TaxBracket.objects.count() == 0:
            self._create_tax_brackets()
            self.stdout.write(self.style.SUCCESS(f"Created {TaxBracket.objects.count()} tax brackets"))

        # Ensure departments exist
        depts = self._ensure_departments()
        dept_list = list(depts.values())

        # Ensure demo users
        self._ensure_demo_users()

        existing = Employee.objects.count()
        if existing >= count and not clear:
            self.stdout.write(self.style.WARNING(f"Already have {existing} employees (>= {count}). Use --clear to reset. Skipping."))
            return

        needed = count - existing
        self.stdout.write(f"Seeding {needed} employees (target {count}, existing {existing}) ...")

        first_names, last_names = self._load_names()
        self.stdout.write(f"Loaded {len(first_names)} first names, {len(last_names)} last names")

        # Generate employees in memory then bulk_create
        # Pre-fetch random helpers
        random.seed(42)  # deterministic for tests/demo

        employees_to_create = []
        # For performance: we will not create User per employee (too heavy: 10k users). We link ~5% to User for demo login coverage.
        # But we need User for role testing optionally. We create Employee without user for most.
        start_id = existing + 1

        # For manager linking, keep list of created employee objects references after bulk? We'll do two passes:
        # First pass bulk_create without managers, then randomly assign managers among same department.

        for i in range(needed):
            idx = start_id + i
            emp_id = f"ACME-{idx:05d}"
            first = random.choice(first_names)
            last = random.choice(last_names)
            country = random.choice(COUNTRIES)
            title = random.choice(JOB_TITLES)
            dept = random.choice(dept_list)
            email = f"{first.lower()}.{last.lower()}.{idx}@acme.test".replace(" ", "")
            # ensures unique email even with duplicate names
            phone = f"+{random.randint(1,99)}-{random.randint(1000000000,9999999999)}"
            address = f"{random.randint(10,999)} {random.choice(['Main St','Park Ave','MG Road','High St','Elgin','Shibuya'])}"
            city = random.choice(["New York","Mumbai","Berlin","London","Toronto","Sydney","Singapore","Dubai","Sao Paulo","Tokyo"])
            doj = date(2015,1,1) + timedelta(days=random.randint(0, 4000))
            employees_to_create.append(Employee(
                employee_id=emp_id,
                first_name=first,
                last_name=last,
                full_name=f"{first} {last}",
                email=email,
                phone=phone,
                address=address,
                city=city,
                country=country,
                job_title=title,
                department_id=dept["id"],
                employment_type=random.choice(["FULL_TIME","CONTRACT","FULL_TIME","FULL_TIME"]),
                status="ACTIVE" if random.random() > 0.04 else random.choice(["ON_LEAVE","INACTIVE"]),
                date_of_joining=doj,
            ))

        # Bulk create employees
        with transaction.atomic():
            Employee.objects.bulk_create(employees_to_create, batch_size=batch_size)

        self.stdout.write(self.style.SUCCESS(f"Bulk created {len(employees_to_create)} employees"))

        # Create salary structures bulk
        # Need to re-fetch IDs for created employees (we already have objects but bulk_create may not populate IDs on SQLite for all? In Django 5 it does with batch? We'll query)
        created_emps = list(Employee.objects.filter(employee_id__gte=f"ACME-{start_id:05d}").order_by("employee_id").select_related("department"))
        # Use batch for salaries
        salaries = []
        for emp in created_emps:
            band = TITLE_SALARY_BAND.get(emp.job_title, DEFAULT_BAND)
            mult = COUNTRY_MULTIPLIER.get(emp.country, 1.0)
            low, high = int(band[0]*mult), int(band[1]*mult)
            basic = Decimal(random.randint(low, high))
            # allowances as percentages of basic
            hra = (basic * Decimal(random.uniform(0.15, 0.35))).quantize(Decimal("0.01"))
            da = (basic * Decimal(random.uniform(0.05, 0.15))).quantize(Decimal("0.01"))
            ta = Decimal(random.randint(800, 4000))
            telephone = Decimal(random.randint(300, 1500))
            special = (basic * Decimal(random.uniform(0.05, 0.20))).quantize(Decimal("0.01"))
            pf = (basic * Decimal("0.08")).quantize(Decimal("0.01"))
            prof_tax = Decimal("200.00") if emp.country == "India" else Decimal(random.randint(0, 300))

            # Create without save compute will happen via model save recompute. But bulk_create bypasses save().
            # So compute manually
            gross = basic + hra + da + ta + telephone + special
            annual_gross = gross * Decimal("12")
            annual_tax = TaxBracket.compute_tax(emp.country, annual_gross)
            monthly_tax = (annual_tax / Decimal("12")).quantize(Decimal("0.01"))
            net = gross - pf - prof_tax - monthly_tax
            if net < Decimal("0"):
                net = Decimal("0.00")
            salaries.append(SalaryStructure(
                employee=emp,
                basic_salary=basic.quantize(Decimal("0.01")),
                house_rent_allowance=hra,
                dearness_allowance=da,
                transport_allowance=ta,
                telephone_allowance=telephone,
                special_allowance=special,
                pf_deduction=pf,
                professional_tax=prof_tax,
                gross_salary=gross.quantize(Decimal("0.01")),
                total_compensation=gross.quantize(Decimal("0.01")),
                tax_deduction=monthly_tax,
                net_in_hand=net.quantize(Decimal("0.01")),
            ))

        with transaction.atomic():
            SalaryStructure.objects.bulk_create(salaries, batch_size=batch_size)

        self.stdout.write(self.style.SUCCESS(f"Bulk created {len(salaries)} salary structures"))

        # Assign managers randomly within same department (5% managers) — optimized pure-python, no per-row DB hits
        try:
            from collections import defaultdict
            all_emps = list(Employee.objects.values("id", "department_id"))
            dept_groups = defaultdict(list)
            for e in all_emps:
                dept_groups[e["department_id"]].append(e["id"])
            manager_by_dept = {}
            manager_pool = []
            for dept_id, ids in dept_groups.items():
                n_mgr = max(2, len(ids) // 20)  # ~5%
                mgrs = ids[:n_mgr]
                manager_by_dept[dept_id] = mgrs
                manager_pool.extend(mgrs)
            manager_pool_set = set(manager_pool)
            # Build updates in-memory
            to_update = []
            # Use values iterator to avoid loading full objects for assignment
            for row in Employee.objects.exclude(id__in=manager_pool_set).values("id", "department_id"):
                if random.random() < 0.8:
                    dept = row["department_id"]
                    same = manager_by_dept.get(dept, [])
                    chosen = random.choice(same) if same else random.choice(manager_pool)
                    # bulk_update needs model instances with pk
                    to_update.append(Employee(id=row["id"], manager_id=chosen))
                    if len(to_update) >= 1000:
                        Employee.objects.bulk_update(to_update, ["manager_id"], batch_size=1000)
                        to_update = []
            if to_update:
                Employee.objects.bulk_update(to_update, ["manager_id"], batch_size=1000)
            self.stdout.write(self.style.SUCCESS(f"Assigned managers to {Employee.objects.filter(manager__isnull=False).count()} employees"))
        except Exception as e:
            import traceback
            self.stdout.write(self.style.WARNING(f"Manager assignment skipped: {e}\n{traceback.format_exc()}"))

        # Ensure demo users are linked to employee profiles (post-seed)
        try:
            emp_user = User.objects.get(username="employee_demo")
            # refresh profile check: query Employee by user
            if not Employee.objects.filter(user=emp_user).exists():
                free_emp = Employee.objects.filter(user__isnull=True).first()
                if free_emp:
                    free_emp.user = emp_user
                    free_emp.save(update_fields=["user", "updated_at"])
                    self.stdout.write(self.style.SUCCESS(f"Linked employee_demo to {free_emp.employee_id}"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Could not link employee_demo: {e}"))

        elapsed = time.time() - t0
        self.stdout.write(self.style.SUCCESS(f"Seeding complete: {Employee.objects.count()} employees, {SalaryStructure.objects.count()} salaries in {elapsed:.2f}s"))

        # Show demo logins
        self.stdout.write(self.style.SUCCESS("Demo logins: hr_admin / hr12345 (HR), employee_demo / emp12345 (Employee)"))

    def _load_names(self):
        base = Path(settings.BASE_DIR)
        # try common locations
        candidates_first = [base / "first_names.txt", base / "data" / "first_names.txt", Path("first_names.txt")]
        candidates_last = [base / "last_names.txt", base / "data" / "last_names.txt", Path("last_names.txt")]
        first_names = None
        last_names = None
        for p in candidates_first:
            if p.exists():
                first_names = [l.strip() for l in p.read_text().splitlines() if l.strip()]
                break
        for p in candidates_last:
            if p.exists():
                last_names = [l.strip() for l in p.read_text().splitlines() if l.strip()]
                break
        if not first_names:
            first_names = ["James","Mary","John","Patricia","Robert","Jennifer","Michael","Linda","William","Elizabeth",
                           "David","Barbara","Richard","Susan","Joseph","Jessica","Thomas","Sarah","Charles","Karen",
                           "Christopher","Nancy","Daniel","Lisa","Matthew","Betty","Anthony","Margaret","Mark","Sandra",
                           "Donald","Ashley","Steven","Kimberly","Paul","Emily","Andrew","Donna","Joshua","Michelle",
                           "Kenneth","Dorothy","Kevin","Carol","Brian","Amanda","George","Melissa","Edward","Deborah",
                           "Ronald","Stephanie","Timothy","Rebecca","Jason","Sharon","Jeffrey","Laura","Ryan","Cynthia",
                           "Jacob","Kathryn","Gary","Amy","Nicholas","Shirley","Eric","Angela","Jonathan","Helen",
                           "Stephen","Anna","Larry","Brenda","Justin","Pamela","Scott","Nicole","Brandon","Emma",
                           "Benjamin","Samantha","Samuel","Katherine","Gregory","Christine","Alexander","Debra","Frank","Rachel",
                           "Patrick","Catherine","Raymond","Carolyn","Jack","Janet","Dennis","Ruth","Jerry","Virginia",
                           "Tyler","Maria","Aaron","Heather","Jose","Diane","Adam","Alice","Nathan","Julie",
                           "Henry","Olivia","Douglas","Joyce","Peter","Victoria","Kyle","Ruth","Ethan","Christina",
                           "Walter","Joan","Gabriel","Evelyn","Randy","Lauren","Harold","Kelly","Carl","Judith",
                           "Arthur","Hannah","Roger","Martha","Gerald","Cheryl","Keith","Megan","Jeremy","Andrea",
                           "Terry","Holly","Christian","Ann","Sean","Doris","Lawrence","Julia","Austin","Kathleen",
                           "Joe","Theresa","Albert","Sara","Jesse","Rose","Willie","Abigail","Billy","Sofia",
                           "Bryan","Isabella","Bruce","Grace","Jordan","Jasmine","Ralph","Alexis","Roy","Aubrey","Aaron","Layla",
                           "Aarav","Vivaan","Aditya","Vikram","Arjun","Sai","Reyansh","Ayaan","Krishna","Ishaan",
                           "Hans","Klaus","Wolfgang","Jurgen","Gunter","Helmut","Dieter","Manfred","Karl","Heinz",
                           "Hiroshi","Kenji","Takeshi","Yuki","Haruto","Sota","Riku","Kaito","Daiki","Ren"]
        if not last_names:
            last_names = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez",
                          "Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore","Jackson","Martin",
                          "Lee","Perez","Thompson","White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson",
                          "Walker","Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill","Flores",
                          "Green","Adams","Nelson","Baker","Hall","Rivera","Campbell","Mitchell","Carter","Roberts",
                          "Gomez","Phillips","Evans","Turner","Diaz","Parker","Cruz","Edwards","Collins","Reyes",
                          "Stewart","Morris","Morales","Murphy","Cook","Rogers","Gutierrez","Ortiz","Morgan","Cooper",
                          "Peterson","Bailey","Reed","Kelly","Howard","Ramos","Kim","Cox","Ward","Richardson",
                          "Watson","Brooks","Chavez","Wood","James","Bennett","Gray","Mendoza","Ruiz","Hughes",
                          "Price","Alvarez","Castillo","Sanders","Patel","Myers","Long","Ross","Foster","Jimenez",
                          "Powell","Jenkins","Perry","Russell","Sullivan","Bell","Coleman","Butler","Henderson","Barnes",
                          "Gonzales","Fisher","Vasquez","Jenkins","Stone","Hawkins","Dunn","Black","Gutierrez","Takahashi",
                          "Sato","Suzuki","Watanabe","Ito","Yamamoto","Nakamura","Kobayashi","Kato","Yoshida","Yamada",
                          "Sasaki","Yamaguchi","Matsumoto","Inoue","Kimura","Hayashi","Shimizu","Yamazaki","Mori","Abe",
                          "Schmidt","Muller","Schneider","Fischer","Weber","Meyer","Wagner","Becker","Schulz","Hoffmann",
                          "Sharma","Verma","Gupta","Singh","Kumar","Patel","Shah","Jain","Yadav","Mishra",
                          "Silva","Santos","Oliveira","Souza","Rodrigues","Ferreira","Almeida","Costa","Pereira","Nascimento"]
        return first_names, last_names

    def _ensure_departments(self):
        for name, code, desc in DEPARTMENTS:
            Department.objects.get_or_create(name=name, defaults={"code": code, "description": desc})
        return Department.objects.all()

    def _create_tax_brackets(self):
        # Simple progressive: 0-300k 0%, 300k-600k 5%, 600k-900k 10%, 900k-1200k 15%, 1200k+ 20% and 30% variant per country
        # We'll create per-country variants with slight tweaks
        base_brackets = [
            (0, 300000, 0),
            (300000, 600000, 5),
            (600000, 900000, 10),
            (900000, 1200000, 15),
            (1200000, None, 20),
        ]
        country_overrides = {
            "USA": [(0, 500000, 0),(500000, 1000000, 10),(1000000, None, 22)],
            "Germany": [(0, 400000, 0),(400000, 800000, 8),(800000, None, 18)],
        }
        for country in COUNTRIES + ["GLOBAL"]:
            brackets = country_overrides.get(country, base_brackets)
            for low, high, rate in brackets:
                TaxBracket.objects.get_or_create(
                    country=country, lower_limit=Decimal(low),
                    defaults={"upper_limit": Decimal(high) if high else None, "rate": Decimal(rate), "description": f"{country} slab"}
                )
        # GLOBAL fallback
        if not TaxBracket.objects.filter(country="GLOBAL").exists():
            for low, high, rate in base_brackets:
                TaxBracket.objects.create(country="GLOBAL", lower_limit=Decimal(low), upper_limit=Decimal(high) if high else None, rate=Decimal(rate))

    def _ensure_demo_users(self):
        User = get_user_model()
        # HR
        if not User.objects.filter(username="hr_admin").exists():
            u = User.objects.create_user(username="hr_admin", email="hr@acme.test", password="hr12345", role=User.Role.HR, is_staff=True)
            self.stdout.write(self.style.SUCCESS("Created HR user: hr_admin / hr12345"))
        # Also ensure hr_admin is HR
        # Employee demo — pick first employee after seeding or create placeholder
        if not User.objects.filter(username="employee_demo").exists():
            u = User.objects.create_user(username="employee_demo", email="employee@acme.test", password="emp12345", role=User.Role.EMPLOYEE)
            self.stdout.write(self.style.SUCCESS("Created Employee user: employee_demo / emp12345"))
        # We'll link employee_demo to a random employee after employees created — do in post-seed linking
        # If employees already exist, link now
        try:
            emp_user = User.objects.get(username="employee_demo")
            if not hasattr(emp_user, "employee_profile") or emp_user.employee_profile is None:
                # link to first employee without user
                free_emp = Employee.objects.filter(user__isnull=True).first()
                if free_emp:
                    free_emp.user = emp_user
                    free_emp.save(update_fields=["user"])
        except Exception:
            pass
