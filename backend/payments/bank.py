"""Banking integration layer.

`BankGateway` is the single integration point. The default `MockBankGateway` simulates a bank API
(NEFT/RTGS/IMPS file/API). To go live, implement `transfer()` against your bank's host-to-host / API
banking (ICICI, HDFC, Yes Bank...) and point settings.BANK_GATEWAY at it.
"""
import uuid


class BankGateway:
    def transfer(self, payment):
        raise NotImplementedError


class MockBankGateway(BankGateway):
    def transfer(self, payment):
        if not payment.bank or not payment.bank.is_verified:
            return {"ok": False, "reason": "Beneficiary bank account is not verified"}
        return {"ok": True, "utr": "UTR" + uuid.uuid4().hex[:12].upper()}


def get_gateway():
    return MockBankGateway()


def choose_mode(amount):
    return "RTGS" if amount >= 200000 else "NEFT"      # RTGS minimum is INR 2 lakh
