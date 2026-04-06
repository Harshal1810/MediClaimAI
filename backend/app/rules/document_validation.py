from __future__ import annotations

from app.rules.codes import (
    DATE_MISMATCH,
    DOCTOR_REG_INVALID,
    ILLEGIBLE_DOCUMENTS,
    INVALID_PRESCRIPTION,
    MISSING_DOCUMENTS,
    PATIENT_MISMATCH,
)
from app.rules.date_utils import parse_date


def _token_overlap_similarity(a: str, b: str) -> float:
    a = (a or "").strip().lower()
    b = (b or "").strip().lower()
    if not a or not b:
        return 0.5
    if a == b:
        return 1.0
    a_tokens = {t for t in a.replace(",", " ").split() if t}
    b_tokens = {t for t in b.replace(",", " ").split() if t}
    overlap = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return overlap / union if union else 0.0


def _extract_patient_name_from_text(text: str) -> str | None:
    t = (text or "").strip()
    if not t:
        return None
    # Minimal heuristic (keep rules layer dependency-free).
    import re

    for pat in [
        r"(?im)^\s*patient\s*name\s*[:\-]\s*([A-Z][A-Z .']{2,60})\s*$",
        r"(?im)^\s*patient\s*[:\-]\s*([A-Z][A-Z .']{2,60})\s*$",
        r"(?im)^\s*name\s*[:\-]\s*([A-Z][A-Z .']{2,60})\s*$",
        r"(?im)\bpatient\s*name\s*[:\-]\s*([A-Za-z][A-Za-z .']{2,60})",
    ]:
        m = re.search(pat, t)
        if not m:
            continue
        name = re.sub(r"\s{2,}", " ", (m.group(1) or "").strip())
        if len(name) < 3:
            continue
        return name.title()
    return None


def _pick_date(payload: dict) -> str | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("date"):
        return str(payload.get("date"))
    dates = payload.get("dates")
    if isinstance(dates, list) and dates:
        return str(dates[0])
    return None


def validate_required_documents(claim_context: dict, policy: dict) -> tuple[bool, str | None, dict]:
    documents = claim_context.get("documents") or {}
    document_types = set(claim_context.get("document_types") or documents.keys())
    normalized = claim_context.get("normalized") or {}
    ocr_texts = claim_context.get("ocr_texts") or {}

    required_types = {"prescription", "bill"}
    missing = required_types - document_types
    if missing:
        if "prescription" in missing:
            return False, MISSING_DOCUMENTS, {"notes": "Prescription from registered doctor is required"}
        return False, MISSING_DOCUMENTS, {"notes": "Original bills and receipts are required"}

    prescription = documents.get("prescription")
    bill = documents.get("bill")

    if not prescription:
        return False, MISSING_DOCUMENTS, {"notes": "Prescription from registered doctor is required"}
    if not bill:
        return False, MISSING_DOCUMENTS, {"notes": "Original bills and receipts are required"}

    flags: list[str] = []

    # Basic legibility checks using OCR text length.
    rx_text_len = len((ocr_texts.get("prescription") or "").strip())
    bill_text_len = len((ocr_texts.get("bill") or "").strip())
    if rx_text_len and rx_text_len < 40:
        flags.append("low_rx_ocr_text")
    if bill_text_len and bill_text_len < 40:
        flags.append("low_bill_ocr_text")

    # Required fields in prescription.
    if isinstance(prescription, dict):
        doctor_reg = (prescription.get("doctor_reg") or "").strip()
        diagnosis = (prescription.get("diagnosis") or "").strip()
        patient_name = (prescription.get("patient_name") or "").strip()

        if not doctor_reg:
            if rx_text_len < 40:
                return False, ILLEGIBLE_DOCUMENTS, {"notes": "Prescription OCR is too low to validate doctor registration number.", "flags": flags}
            return False, DOCTOR_REG_INVALID, {"notes": "Doctor registration number invalid/missing", "flags": flags}
        if not diagnosis:
            if rx_text_len < 40:
                return False, ILLEGIBLE_DOCUMENTS, {"notes": "Prescription OCR is too low to validate diagnosis.", "flags": flags}
            return False, INVALID_PRESCRIPTION, {"notes": "Prescription missing diagnosis", "flags": flags}

        # Patient match (best-effort): use extracted patient_name if available, else try OCR heuristic.
        if not patient_name:
            inferred = _extract_patient_name_from_text(ocr_texts.get("prescription") or "")
            if inferred:
                patient_name = inferred
            else:
                flags.append("patient_name_missing")

        claim_name = str((claim_context.get("claim") or {}).get("member_name") or "").strip()
        if patient_name and claim_name:
            sim = _token_overlap_similarity(patient_name, claim_name)
            if sim < 0.4:
                return False, PATIENT_MISMATCH, {"notes": "Patient name on documents does not match claim member name.", "flags": flags}
            if sim < 0.75:
                flags.append("weak_patient_match")

        # Provider/hospital match (only when claim includes hospital).
        claim_hospital = str((claim_context.get("claim") or {}).get("hospital") or (claim_context.get("claim") or {}).get("hospital_name") or "").strip()
        bill_hospital = ""
        if isinstance(bill, dict):
            bill_hospital = str(bill.get("hospital_name") or bill.get("provider_name") or "").strip()
        if claim_hospital and bill_hospital:
            hsim = _token_overlap_similarity(claim_hospital, bill_hospital)
            if hsim < 0.4:
                flags.append("hospital_name_mismatch")
            elif hsim < 0.75:
                flags.append("weak_hospital_match")

        # "If applicable" documents: diagnostic reports + pharmacy bills.
        tests_indicated = False
        if isinstance(prescription.get("tests_prescribed"), list) and prescription.get("tests_prescribed"):
            tests_indicated = True
        if isinstance(normalized, dict) and isinstance(normalized.get("tests"), list) and normalized.get("tests"):
            tests_indicated = True
        if isinstance(bill, dict):
            try:
                if float(bill.get("diagnostic_tests") or 0.0) > 0:
                    tests_indicated = True
            except Exception:
                pass
            if isinstance(bill.get("test_names"), list) and bill.get("test_names"):
                tests_indicated = True

        if tests_indicated and "report" not in document_types:
            return False, MISSING_DOCUMENTS, {"notes": "Diagnostic test report(s) are required when diagnostic tests are billed/prescribed.", "flags": flags + ["missing_report"]}

        meds_indicated = False
        if isinstance(prescription.get("medicines_prescribed"), list) and prescription.get("medicines_prescribed"):
            meds_indicated = True
        if isinstance(normalized, dict) and isinstance(normalized.get("medicines"), list) and normalized.get("medicines"):
            meds_indicated = True
        if isinstance(bill, dict):
            try:
                if float(bill.get("pharmacy") or 0.0) > 0 or float(bill.get("medicines") or 0.0) > 0 or float(bill.get("pharmacy_total") or 0.0) > 0:
                    meds_indicated = True
            except Exception:
                pass

        if meds_indicated and "pharmacy_bill" not in document_types:
            return False, MISSING_DOCUMENTS, {"notes": "Pharmacy bill(s) are required when medicines are billed/prescribed.", "flags": flags + ["missing_pharmacy_bill"]}

        # Date consistency (when available).
        treatment_date = parse_date(str((claim_context.get("claim") or {}).get("treatment_date") or ""))
        rx_date = parse_date(str(_pick_date(prescription) or ""))
        bill_date = parse_date(str(_pick_date(bill) or "")) if isinstance(bill, dict) else None
        if treatment_date and rx_date and rx_date != treatment_date:
            flags.append("rx_date_mismatch")
        if treatment_date and bill_date and bill_date != treatment_date:
            flags.append("bill_date_mismatch")
        if any(f in flags for f in ("rx_date_mismatch", "bill_date_mismatch")):
            return False, DATE_MISMATCH, {"notes": "Document dates do not match treatment date.", "flags": flags}
    else:
        return False, INVALID_PRESCRIPTION, {"notes": "Prescription extraction invalid.", "flags": flags}

    return True, None, {"flags": flags} if flags else {}
