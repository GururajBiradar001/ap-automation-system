"""Seeds demo users, vendors, POs, GRNs, approval matrix and sample invoice files.
   python manage.py seed_demo
"""
from datetime import date
from decimal import Decimal as D
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from accounts.models import User
from invoices.sample_generator import generate_samples
from purchasing.models import PurchaseOrder, POLine, GoodsReceipt, GRNLine
from vendors.gst import make_gstin
from vendors.models import Vendor, VendorBank
from workflow.models import ApprovalRule, ApprovalStep

PASSWORD = "Pass@1234"


class Command(BaseCommand):
    help = "Create demo data"

    def handle(self, *a, **kw):
        for username, role in [("admin", "ADMIN"), ("clerk", "AP_CLERK"), ("manager", "MANAGER"),
                               ("finance", "FINANCE_HEAD"), ("cfo", "CFO")]:
            u, _ = User.objects.get_or_create(username=username, defaults={"role": role,
                                              "email": f"{username}@example.com", "is_staff": role == "ADMIN",
                                              "is_superuser": role == "ADMIN"})
            u.role = role
            u.set_password(PASSWORD)
            u.save()

        g1, g2, g3 = (make_gstin("29AABCS1429B1Z"), make_gstin("27AAACM2314K1Z"), make_gstin("29AADCK5521M1Z"))
        specs = [("Sharma Electricals Pvt Ltd", g1, "HDFC Bank", "HDFC0001234", "50100234567891"),
                 ("Mehta Industrial Supplies", g2, "ICICI Bank", "ICIC0004567", "000405012345"),
                 ("Kaveri Stationers", g3, "State Bank of India", "SBIN0001122", "30123456789")]
        vendors = []
        for name, g, bank, ifsc, acc in specs:
            v, _ = Vendor.objects.get_or_create(name=name, defaults=dict(
                gstin=g, pan=g[2:12], state_code=g[:2], status="ACTIVE", email="accounts@vendor.example"))
            if not v.banks.exists():
                VendorBank.objects.create(vendor=v, account_name=name, account_number=acc, ifsc=ifsc,
                                          bank_name=bank, is_primary=True, is_verified=True)
            vendors.append(v)
        pend, _ = Vendor.objects.get_or_create(name="NewTech Solutions LLP", defaults=dict(
            gstin=make_gstin("29AAFFN7788P1Z"), pan="AAFFN7788P", state_code="29", status="PENDING_APPROVAL"))
        if not pend.banks.exists():
            VendorBank.objects.create(vendor=pend, account_name="NewTech Solutions LLP",
                                      account_number="77001122334", ifsc="KARB0000123", bank_name="Karnataka Bank")
        v1, v2, v3 = vendors

        def po(num, vendor, mt, lines):
            p, created = PurchaseOrder.objects.get_or_create(
                po_number=num, defaults=dict(vendor=vendor, po_date=date(2026, 11, 1), match_type=mt))
            if created:
                for i, (code, d, qty, price, gst) in enumerate(lines, 1):
                    POLine.objects.create(po=p, line_no=i, item_code=code, description=d, quantity=qty,
                                          unit_price=price, gst_rate=gst)
            return p
        po("PO-2026-001", v1, "2WAY", [("ELC-101", "LED Panel Light 40W", 100, 850, 18),
                                       ("ELC-102", "Copper Wire 2.5mm (90m)", 50, 1450, 18)])
        p2 = po("PO-2026-002", v2, "3WAY", [("MCH-201", "Hydraulic Pump HP-20", 10, 24500, 18),
                                            ("MCH-202", "Pressure Valve PV-5", 20, 3200, 18)])
        po("PO-2026-003", v3, "2WAY", [(f"STN-{i:03d}", f"Office Stationery Item {i}", 100, 40 + i, 12)
                                       for i in range(1, 31)])
        po("PO-2026-004", v1, "2WAY", [("ELC-301", "Switch Gear Box", 20, 2000, 18)])
        po("PO-2026-006", v3, "2WAY", [("STN-900", "A4 Paper Ream 75GSM", 500, 320, 12)])
        if not GoodsReceipt.objects.filter(grn_number="GRN-0001").exists():
            g = GoodsReceipt.objects.create(grn_number="GRN-0001", po=p2, received_date=date(2026, 11, 10))
            for pl, qty in zip(p2.lines.all(), (6, 20)):       # only 6 of 10 pumps received so far
                GRNLine.objects.create(grn=g, po_line=pl, quantity_received=qty)

        if not ApprovalRule.objects.exists():
            for name, lo, hi, steps in [
                ("Up to 50,000", 0, 50000, [(1, "MANAGER", 24, "FINANCE_HEAD")]),
                ("50,000 - 2,00,000 (sequential)", 50000.01, 200000, [(1, "MANAGER", 24, "FINANCE_HEAD"),
                                                                      (2, "FINANCE_HEAD", 24, "CFO")]),
                ("Above 2,00,000 (parallel + CFO)", 200000.01, None, [(1, "MANAGER", 24, "FINANCE_HEAD"),
                                                                       (1, "FINANCE_HEAD", 24, "CFO"),
                                                                       (2, "CFO", 48, "")])]:
                r = ApprovalRule.objects.create(name=name, min_amount=lo, max_amount=hi)
                for stage, role, sla, esc in steps:
                    ApprovalStep.objects.create(rule=r, stage=stage, role=role, sla_hours=sla, escalation_role=esc)

        out = Path(settings.BASE_DIR).parent / "sample_invoices"
        files = generate_samples(str(out), settings.COMPANY_GSTIN, (g1, g2, g3))
        self.stdout.write(self.style.SUCCESS(f"Seeded. Users: admin/clerk/manager/finance/cfo  password: {PASSWORD}"))
        self.stdout.write(f"Sample invoices in {out}: {files}")
