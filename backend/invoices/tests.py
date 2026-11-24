"""End-to-end tests: upload -> OCR -> validate -> match -> approve (parallel) -> pay -> reports."""
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import User
from vendors.gst import make_gstin, validate_gstin
from workflow import engine
from workflow.models import ApprovalTask

SAMPLES = Path(settings.BASE_DIR).parent / "sample_invoices"


class APFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def client_for(self, username):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION="Token " + Token.objects.get_or_create(user=User.objects.get(username=username))[0].key)
        return c

    def upload(self, fname, user="clerk"):
        f = SimpleUploadedFile(fname, (SAMPLES / fname).read_bytes())
        r = self.client_for(user).post("/api/invoices/upload/", {"files": [f]}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        res = r.json()["results"][0]
        self.assertNotIn("error", res, res)
        return res["id"]

    def test_gstin_validation(self):
        self.assertTrue(validate_gstin(make_gstin("29AABCS1429B1Z"))[0])
        self.assertFalse(validate_gstin("29AABCS1429B1ZX")[0])          # bad check digit
        self.assertFalse(validate_gstin("99ABC")[0])

    def test_login(self):
        r = APIClient().post("/api/auth/login/", {"username": "clerk", "password": "Pass@1234"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.json())

    def test_parallel_approval_payment_and_reports(self):
        iid = self.upload("INV-2001_clean_3way_parallel.pdf")
        inv = self.client_for("clerk").get(f"/api/invoices/{iid}/").json()
        self.assertEqual(inv["status"], "PENDING_APPROVAL")
        self.assertEqual(inv["match_type_used"], "3WAY")
        self.assertEqual(inv["ocr_accuracy"], 100.0)
        tasks = ApprovalTask.objects.filter(invoice_id=iid, status="PENDING")
        self.assertEqual(sorted(t.role for t in tasks), ["FINANCE_HEAD", "MANAGER"])     # parallel stage 1

        # role-based: a clerk cannot approve
        t_mgr = tasks.get(role="MANAGER")
        r = self.client_for("clerk").post(f"/api/approval-tasks/{t_mgr.id}/decide/", {"approve": True}, format="json")
        self.assertIn(r.status_code, (403, 404))
        # manager approves -> stage still open until finance approves too
        r = self.client_for("manager").post(f"/api/approval-tasks/{t_mgr.id}/decide/", {"approve": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(ApprovalTask.objects.filter(invoice_id=iid, stage=2).count(), 0)
        t_fin = ApprovalTask.objects.get(invoice_id=iid, role="FINANCE_HEAD", stage=1)
        self.client_for("finance").post(f"/api/approval-tasks/{t_fin.id}/decide/", {"approve": True}, format="json")
        t_cfo = ApprovalTask.objects.get(invoice_id=iid, stage=2)
        self.assertEqual(t_cfo.role, "CFO")
        self.client_for("cfo").post(f"/api/approval-tasks/{t_cfo.id}/decide/", {"approve": True, "comment": "ok"}, format="json")

        inv = self.client_for("clerk").get(f"/api/invoices/{iid}/").json()
        self.assertEqual(inv["status"], "PAYMENT_REQUESTED")
        pay = self.client_for("finance").get("/api/payments/").json()["results"][0]
        self.assertEqual(pay["mode"], "RTGS")
        # clerk cannot release, finance can
        self.assertEqual(self.client_for("clerk").post(f"/api/payments/{pay['id']}/release/").status_code, 403)
        r = self.client_for("finance").post(f"/api/payments/{pay['id']}/release/")
        self.assertEqual(r.json()["status"], "PAID")
        self.assertTrue(r.json()["bank_reference"].startswith("UTR"))
        adv = self.client_for("finance").get(f"/api/payments/{pay['id']}/advice/")
        self.assertEqual(adv.status_code, 200)
        self.assertTrue(adv.content.startswith(b"%PDF"))

        dash = self.client_for("manager").get("/api/dashboard/").json()
        self.assertEqual(dash["payments"]["PAID"]["count"], 1)
        self.assertEqual(dash["ocr"]["accuracy_pct"], 100.0)
        gst = self.client_for("manager").get("/api/reports/gst/").json()
        self.assertEqual(gst["rows"][-1][7], 37980.0)                                    # IGST total
        for rep in ("ap-aging", "invoice-status", "exceptions", "audit-log"):
            self.assertEqual(self.client_for("manager").get(f"/api/reports/{rep}/").status_code, 200)
        csvr = self.client_for("manager").get("/api/reports/gst/?export=csv")
        self.assertIn("text/csv", csvr["Content-Type"])

    def test_three_way_overbilling_is_exception(self):
        self.upload("INV-2001_clean_3way_parallel.pdf")
        iid = self.upload("INV-2002_overbilled_3way.pdf")
        inv = self.client_for("clerk").get(f"/api/invoices/{iid}/").json()
        self.assertEqual(inv["status"], "EXCEPTION")
        msgs = " ".join(i["message"] for i in inv["issues"])
        self.assertIn("received qty", msgs)
        self.assertIn("differs from PO price", msgs)

    def test_duplicate_detected(self):
        self.upload("INV-1001_clean_2way.pdf")
        iid = self.upload("INV-1001_clean_2way.pdf")
        inv = self.client_for("clerk").get(f"/api/invoices/{iid}/").json()
        self.assertEqual(inv["status"], "EXCEPTION")
        self.assertTrue(any(i["category"] == "DUPLICATE" for i in inv["issues"]))

    def test_correct_exception_then_revalidate_lowers_ocr_accuracy(self):
        iid = self.upload("INV-4004_bad_tax.pdf")
        c = self.client_for("clerk")
        self.assertEqual(c.get(f"/api/invoices/{iid}/").json()["status"], "EXCEPTION")
        r = c.patch(f"/api/invoices/{iid}/", {"igst": "0", "cgst": "900", "sgst": "900"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        r = c.post(f"/api/invoices/{iid}/revalidate/")
        self.assertEqual(r.json()["status"], "PENDING_APPROVAL", r.json()["issues"])
        self.assertLess(r.json()["ocr_accuracy"], 100.0)                                 # human corrections counted

    def test_force_submit_requires_manager_and_comment(self):
        iid = self.upload("INV-4004_bad_tax.pdf")
        self.assertEqual(self.client_for("clerk").post(f"/api/invoices/{iid}/force-submit/", {"comment": "x"}, format="json").status_code, 403)
        self.assertEqual(self.client_for("manager").post(f"/api/invoices/{iid}/force-submit/", {}, format="json").status_code, 400)
        r = self.client_for("manager").post(f"/api/invoices/{iid}/force-submit/", {"comment": "vendor confirmed"}, format="json")
        self.assertEqual(r.json()["status"], "PENDING_APPROVAL")

    def test_escalation_and_reminder(self):
        iid = self.upload("INV-1001_clean_2way.pdf")
        t = ApprovalTask.objects.get(invoice_id=iid, status="PENDING")
        self.assertEqual(t.role, "MANAGER")
        ApprovalTask.objects.filter(pk=t.pk).update(due_at=timezone.now() - timedelta(hours=1))
        res = engine.run_escalations()
        self.assertEqual(res["escalated"], 1)
        t.refresh_from_db()
        self.assertEqual(t.status, "ESCALATED")
        self.assertTrue(ApprovalTask.objects.filter(invoice_id=iid, status="PENDING", role="FINANCE_HEAD", escalated=True).exists())

    def test_rejection_stops_workflow(self):
        iid = self.upload("INV-1001_clean_2way.pdf")
        t = ApprovalTask.objects.get(invoice_id=iid, status="PENDING")
        self.client_for("manager").post(f"/api/approval-tasks/{t.id}/decide/", {"approve": False, "comment": "no"}, format="json")
        self.assertEqual(self.client_for("clerk").get(f"/api/invoices/{iid}/").json()["status"], "REJECTED")

    def test_vendor_onboarding_flow(self):
        c = self.client_for("clerk")
        r = c.post("/api/vendors/", {"name": "Acme Traders", "gstin": make_gstin("29AAAAA0000A1Z")}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        vid = r.json()["id"]
        self.assertEqual(c.post(f"/api/vendors/{vid}/submit/").status_code, 400)         # needs a bank account
        r = c.post("/api/vendor-banks/", {"vendor": vid, "account_name": "Acme", "account_number": "123456789012",
                                         "ifsc": "HDFC0001234", "bank_name": "HDFC"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(c.post(f"/api/vendors/{vid}/submit/").json()["status"], "PENDING_APPROVAL")
        self.assertEqual(c.post(f"/api/vendors/{vid}/decide/", {"approve": True}, format="json").status_code, 403)
        r = self.client_for("manager").post(f"/api/vendors/{vid}/decide/", {"approve": True}, format="json")
        self.assertEqual(r.json()["status"], "ACTIVE")
        self.assertTrue(r.json()["banks"][0]["is_verified"])
        bad = c.post("/api/vendors/", {"name": "Bad", "gstin": "29AAAAA0000A1ZX"}, format="json")
        self.assertEqual(bad.status_code, 400)
