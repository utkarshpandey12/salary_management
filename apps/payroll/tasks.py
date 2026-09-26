import io
from datetime import date
from decimal import Decimal
from django.utils import timezone
from celery import shared_task
from django.db.models import Sum, Q, OuterRef, Subquery
from django.core.files.base import ContentFile

def get_payroll_rows(month_date: date):
    """
    Returns list of dicts: empID, salary_amount, reimbursement_amount, total_amount
    for given month (first day of month). Reimbursement sum is for expense_date in month and status APPROVED.
    """
    from apps.employees.models import Employee, SalaryStructure
    from apps.reimbursements.models import Reimbursement

    year = month_date.year
    month = month_date.month

    # Annotate reimbursement sum per employee
    # Use subquery for efficiency
    # We'll do direct query with aggregation
    employees = Employee.objects.select_related("salary").filter(status="ACTIVE").order_by("employee_id")
    # Prefetch reimbursements? For 10k, loop with query per employee could be N+1, so aggregate separately
    reimb_sums = (
        Reimbursement.objects.filter(status="APPROVED", expense_date__year=year, expense_date__month=month)
        .values("employee_id")
        .annotate(total=Sum("amount"))
    )
    reimb_map = {r["employee_id"]: r["total"] for r in reimb_sums}

    rows = []
    for emp in employees.iterator():
        try:
            sal = emp.salary.net_in_hand if hasattr(emp, "salary") and emp.salary else Decimal("0.00")
        except Exception:
            sal = Decimal("0.00")
        reimb = reimb_map.get(emp.id, Decimal("0.00")) or Decimal("0.00")
        total = (sal + reimb).quantize(Decimal("0.01"))
        rows.append({
            "empID": emp.employee_id,
            "full_name": emp.full_name,
            "salary_amount": sal.quantize(Decimal("0.01")),
            "reimbursement_amount": reimb.quantize(Decimal("0.01")),
            "total_amount": total,
        })
    return rows

@shared_task(bind=True)
def generate_payroll_export(self, export_id: int):
    from .models import PayrollExport
    try:
        export = PayrollExport.objects.get(id=export_id)
    except PayrollExport.DoesNotExist:
        return {"error": "Export not found"}

    export.status = PayrollExport.Status.PROCESSING
    export.celery_task_id = self.request.id or ""
    export.save(update_fields=["status", "celery_task_id"])

    try:
        rows = get_payroll_rows(export.month)
        buf = io.BytesIO()

        if export.format == PayrollExport.Format.EXCEL:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = f"Payroll {export.month:%Y-%m}"
            headers = ["empID", "Full Name", "Salary Amount", "Reimbursement Amount", "Total Amount"]
            ws.append(headers)
            for r in rows:
                ws.append([r["empID"], r["full_name"], float(r["salary_amount"]), float(r["reimbursement_amount"]), float(r["total_amount"])])
            # style
            ws.auto_filter.ref = ws.dimensions
            ws.freeze_panes = "A2"
            for col in ws.columns:
                max_len = max(len(str(cell.value)) if cell.value else 0 for cell in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 30)
            wb.save(buf)
            filename = f"payroll_{export.month:%Y_%m}.{export.format.lower()}.xlsx"
            if export.format == PayrollExport.Format.EXCEL:
                filename = f"payroll_{export.month:%Y_%m}.xlsx"
            export.file.save(filename, ContentFile(buf.getvalue()), save=False)

        else:  # PDF
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet

            styles = getSampleStyleSheet()
            elements = []
            elements.append(Paragraph(f"Payroll — {export.month:%B %Y}", styles["Title"]))
            elements.append(Spacer(1, 6*mm))
            header = ["empID", "Name", "Salary", "Reimb.", "Total"]
            data = [header]
            for r in rows[:2000]:  # cap for PDF rendering sanity at 10k — split pages automatically via platypus
                data.append([r["empID"], r["full_name"][:24], f"{r['salary_amount']}", f"{r['reimbursement_amount']}", f"{r['total_amount']}"])
            # add totals row
            total_sal = sum((r["salary_amount"] for r in rows), Decimal("0"))
            total_reimb = sum((r["reimbursement_amount"] for r in rows), Decimal("0"))
            total_all = sum((r["total_amount"] for r in rows), Decimal("0"))
            data.append(["", "TOTAL", f"{total_sal}", f"{total_reimb}", f"{total_all}"])

            t = Table(data, repeatRows=1, colWidths=[28*mm, 50*mm, 28*mm, 28*mm, 28*mm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                ("ALIGN", (0,0), (-1,-1), "LEFT"),
                ("ALIGN", (2,1), (-1,-1), "RIGHT"),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 7),
                ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0,1), (-1,-2), [colors.white, colors.HexColor("#f9fafb")]),
                ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#e5e7eb")),
                ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
            ]))
            elements.append(t)
            doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=10*mm, rightMargin=10*mm, topMargin=12*mm, bottomMargin=12*mm, title=f"Payroll {export.month:%Y-%m}")
            doc.build(elements)
            filename = f"payroll_{export.month:%Y_%m}.pdf"
            export.file.save(filename, ContentFile(buf.getvalue()), save=False)

        export.status = PayrollExport.Status.COMPLETED
        export.completed_at = timezone.now()
        export.error = ""
        export.save(update_fields=["status", "completed_at", "error", "file"])
        return {"rows": len(rows), "file": export.file.name}

    except Exception as e:
        import traceback
        export.status = PayrollExport.Status.FAILED
        export.error = f"{e}\n{traceback.format_exc()}"
        export.save(update_fields=["status", "error"])
        raise
