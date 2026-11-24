"""GSTIN / PAN / IFSC validation helpers (India)."""
import re

GSTIN_RE = re.compile(r"^(\d{2})([A-Z]{5}\d{4}[A-Z])([1-9A-Z])Z([0-9A-Z])$")
PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
VALID_STATE_CODES = {f"{i:02d}" for i in range(1, 39)} | {"97", "99"}


def gstin_checksum(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        prod = CHARSET.index(ch) * (1 if i % 2 == 0 else 2)
        total += prod // 36 + prod % 36
    return CHARSET[(36 - total % 36) % 36]


def make_gstin(first14: str) -> str:
    return first14 + gstin_checksum(first14)


def validate_gstin(gstin: str):
    """Returns (ok, message). Checks format, state code and check digit."""
    g = (gstin or "").strip().upper()
    if not GSTIN_RE.match(g):
        return False, "GSTIN format is invalid (expected 15 characters)"
    if g[:2] not in VALID_STATE_CODES:
        return False, f"GSTIN has invalid state code {g[:2]}"
    if gstin_checksum(g[:14]) != g[14]:
        return False, "GSTIN check digit does not match"
    return True, "ok"


def pan_from_gstin(gstin: str) -> str:
    return gstin[2:12] if gstin and len(gstin) == 15 else ""
