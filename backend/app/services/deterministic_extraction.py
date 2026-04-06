from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.rules.date_utils import parse_date


DOCTOR_REG_PATTERNS = [
    re.compile(r"\b([A-Z]{2})\s*/\s*(\d{3,6})\s*/\s*(\d{4})\b"),
    re.compile(r"\b(AYUR)\s*/\s*([A-Z]{2})\s*/\s*(\d{3,6})\s*/\s*(\d{4})\b"),
]


def extract_doctor_reg(text: str) -> str | None:
    t = (text or "").upper()
    for pat in DOCTOR_REG_PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        return "/".join([g.strip() for g in m.groups()])
    return None


def extract_patient_name(text: str) -> str | None:
    """
    Best-effort extraction of patient name from common prescription/report layouts.

    Keep it lightweight and dependency-free: this is only a heuristic fallback used in
    rule-based mode, and as a safety net even in LLM mode.
    """
    t = (text or "").strip()
    if not t:
        return None

    patterns = [
        r"(?im)^\s*patient\s*name\s*[:\-]\s*([A-Z][A-Z .']{2,60})\s*$",
        r"(?im)^\s*patient\s*[:\-]\s*([A-Z][A-Z .']{2,60})\s*$",
        r"(?im)^\s*name\s*[:\-]\s*([A-Z][A-Z .']{2,60})\s*$",
        r"(?im)\bpatient\s*name\s*[:\-]\s*([A-Za-z][A-Za-z .']{2,60})",
        r"(?im)\bpatient\s*[:\-]\s*([A-Za-z][A-Za-z .']{2,60})",
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if not m:
            continue
        name = re.sub(r"\s{2,}", " ", (m.group(1) or "").strip())
        # Avoid obviously-bad captures.
        if any(bad in name.lower() for bad in ("hospital", "clinic", "doctor", "dr.", "date")):
            continue
        if len(name) < 3:
            continue
        return name.title()

    return None


def extract_provider_name(text: str) -> str | None:
    """
    Best-effort provider/hospital/clinic name extraction from headers.

    Example PDFs in `claims_test_pack/` start with lines like:
      "Apollo Hospitals - OPD Bill"
      "CityCare Clinic - Outpatient Prescription"
    """
    t = (text or "").strip()
    if not t:
        return None
    first_line = t.splitlines()[0].strip()
    if not first_line:
        return None
    # Take text before a dash if present (common pattern).
    head = first_line.split("-")[0].strip()
    if len(head) >= 4 and any(k in head.lower() for k in ("hospital", "clinic", "center", "centre", "labs", "lab")):
        return head
    # Fallback: scan first few lines for a plausible provider name.
    for line in t.splitlines()[:5]:
        s = (line or "").strip()
        if len(s) < 4:
            continue
        if any(k in s.lower() for k in ("hospitals", "hospital", "clinic", "diagnostic", "laboratory", "lab")):
            return s.split("-")[0].strip()
    return None


def extract_primary_date(text: str) -> str | None:
    t = text or ""

    # Prefer labeled dates like "Date: 01/04/2026".
    m = re.search(r"(?im)\bdate\s*[:\-]\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b", t)
    if m:
        d = parse_date(m.group(1))
        if d:
            return d.isoformat()

    dates = extract_dates(t)
    return dates[0] if dates else None


def extract_total_amount(text: str) -> float | None:
    t = text or ""
    # Prefer "Grand Total" / "Total" style amounts.
    m = re.search(
        r"(?im)\b(?:grand\s*total|gross\s*amount|gross\s*total|total\s*amount|net\s*amount|amount\s*payable|total)\b\s*[:\-]?\s*(?:₹|rs\.?|inr)?\s*(\d{2,8})(?:\.(\d{1,2}))?\b",
        t,
    )
    if m:
        try:
            whole = m.group(1)
            frac = m.group(2)
            return float(f"{whole}.{frac}" if frac is not None else whole)
        except Exception:
            return None
    return None


def extract_dates(text: str) -> list[str]:
    t = text or ""
    candidates: list[str] = []
    for m in re.finditer(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", t):
        candidates.append(m.group(1))
    for m in re.finditer(r"\b(\d{4}-\d{2}-\d{2})\b", t):
        candidates.append(m.group(1))
    normalized = []
    for c in candidates:
        d = parse_date(c)
        if d:
            normalized.append(d.isoformat())
    return sorted(set(normalized))


def extract_amounts(text: str) -> list[float]:
    t = text or ""
    amounts: list[float] = []
    pattern = re.compile(
        r"(?<![A-Za-z0-9-])(?:₹|rs\.?|inr)?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{2,8})(?:\.(\d{1,2}))?",
        flags=re.IGNORECASE,
    )
    for m in pattern.finditer(t):
        try:
            whole = (m.group(1) or "").replace(",", "")
            frac = m.group(2)
            value = float(f"{whole}.{frac}" if frac is not None else whole)

            # Skip years / date fragments (very common in PDFs).
            end = m.end()
            if frac is None:
                if 1900 <= value <= 2100:
                    nxt = t[end : end + 1]
                    prv = t[m.start() - 1 : m.start()] if m.start() > 0 else ""
                    if nxt in ("-", "/") or prv in ("-", "/"):
                        continue
                if value <= 31:
                    continue
                # Avoid treating small integers as amounts unless currency is explicit.
                token = (m.group(0) or "").strip().lower()
                has_currency = token.startswith(("₹", "rs", "inr"))
                if value < 100 and not has_currency:
                    continue

            if value <= 0:
                continue
            amounts.append(value)
        except Exception:
            continue

    # Deduplicate while preserving approximate order; keep top N.
    uniq: list[float] = []
    for a in amounts:
        if any(abs(a - x) < 0.01 for x in uniq):
            continue
        uniq.append(a)
    return uniq[:30]


def detect_diagnosis_keywords(text: str) -> str | None:
    t = (text or "").lower()
    for keyword in [
        "viral fever",
        "fever",
        "migraine",
        "gastroenteritis",
        "hypertension",
        "diabetes",
        "obesity",
        "bronchitis",
        "joint pain",
    ]:
        if keyword in t:
            return keyword.title()
    return None


def detect_tests(text: str) -> list[str]:
    t = (text or "").lower()
    tests = []
    for name in ["cbc", "dengue", "mri", "ct", "ecg", "x-ray", "ultrasound", "urine", "blood"]:
        if name in t:
            tests.append(name.upper() if len(name) <= 3 else name.title())
    return sorted(set(tests))


def detect_medicines(text: str) -> list[str]:
    t = (text or "").lower()
    meds = []
    for name in ["paracetamol", "metformin", "glimepiride", "sumatriptan", "propranolol", "antibiotic", "probiotic", "vitamin c"]:
        if name in t:
            meds.append(name.title())
    return sorted(set(meds))


@dataclass(frozen=True)
class ExtractionEnvelope:
    ocr_text: str
    extracted: dict[str, Any]
    extraction_method: str  # "rule_based" | "llm"
    extraction_confidence: float
    field_confidences: dict[str, float]
    missing_fields: list[str]
    schema_valid: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ocr_text": self.ocr_text,
            "extracted": self.extracted,
            "extraction_method": self.extraction_method,
            "extraction_confidence": self.extraction_confidence,
            "field_confidences": self.field_confidences,
            "missing_fields": self.missing_fields,
            "schema_valid": self.schema_valid,
        }


def extract_structured_by_type(*, ocr_text: str, document_type: str) -> ExtractionEnvelope:
    doc_type = (document_type or "unknown").lower()
    text = ocr_text or ""

    extracted: dict[str, Any] = {"document_type": doc_type}
    field_confidences: dict[str, float] = {}

    if doc_type == "prescription":
        reg = extract_doctor_reg(text)
        diagnosis = detect_diagnosis_keywords(text)
        patient_name = extract_patient_name(text)
        provider_name = extract_provider_name(text)
        dates = extract_dates(text)
        primary_date = extract_primary_date(text) or (dates[0] if dates else None)
        extracted.update(
            {
                "patient_name": patient_name,
                "provider_name": provider_name,
                "doctor_reg": reg,
                "diagnosis": diagnosis,
                "date": primary_date,
                "dates": dates,
                "medicines_prescribed": detect_medicines(text),
                "tests_prescribed": detect_tests(text),
            }
        )
        field_confidences["patient_name"] = 0.75 if patient_name else 0.45
        field_confidences["provider_name"] = 0.85 if provider_name else 0.55
        field_confidences["date"] = 0.75 if primary_date else 0.5
        field_confidences["doctor_reg"] = 0.9 if reg else 0.4
        field_confidences["diagnosis"] = 0.8 if diagnosis else 0.45
    elif doc_type in ("bill", "pharmacy_bill", "report"):
        amounts = extract_amounts(text)
        dates = extract_dates(text)
        primary_date = extract_primary_date(text) or (dates[0] if dates else None)
        total = extract_total_amount(text)
        provider_name = extract_provider_name(text)
        extracted.update(
            {
                "bill_total": total,
                "total": total,
                "amounts": amounts,
                "date": primary_date,
                "dates": dates,
                "hospital_name": provider_name,
                "tests": detect_tests(text),
            }
        )
        field_confidences["bill_total"] = 0.8 if total else (0.65 if amounts else 0.4)
        field_confidences["amounts"] = 0.75 if amounts else 0.45
    else:
        extracted.update({"raw_text_excerpt": text[:400]})

    required = ["doctor_reg", "diagnosis", "patient_name"] if doc_type == "prescription" else []
    missing = [f for f in required if not extracted.get(f)]
    schema_valid = True
    confidence = 0.72 if not missing else 0.55

    return ExtractionEnvelope(
        ocr_text=text,
        extracted=extracted,
        extraction_method="rule_based",
        extraction_confidence=confidence,
        field_confidences=field_confidences,
        missing_fields=missing,
        schema_valid=schema_valid,
    )
