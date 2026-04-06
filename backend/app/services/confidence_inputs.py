from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.rules.date_utils import parse_date


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _safe_div(n: float, d: float) -> float:
    if d <= 0:
        return 0.0
    return n / d


def _string_similarity(a: str, b: str) -> float:
    a = (a or "").strip().lower()
    b = (b or "").strip().lower()
    if not a or not b:
        return 0.5
    if a == b:
        return 1.0
    # Very small, dependency-free approximation.
    a_tokens = {t for t in a.replace(",", " ").split() if t}
    b_tokens = {t for t in b.replace(",", " ").split() if t}
    overlap = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return _clamp(_safe_div(overlap, max(union, 1)))


def _numeric_sum(mapping: dict[str, Any]) -> float:
    total = 0.0
    for v in (mapping or {}).values():
        if isinstance(v, (int, float)):
            total += float(v)
    return total


@dataclass
class ConfidenceInputs:
    ocr_inputs: dict[str, Any]
    extraction_inputs: dict[str, Any]
    consistency_inputs: dict[str, Any]
    rule_inputs: dict[str, Any]
    medical_inputs: dict[str, Any]
    manual_review_flags: list[str]
    critical_missing_fields: list[str]


def build_confidence_inputs(*, claim_context: dict, decision: dict) -> ConfidenceInputs:
    claim = claim_context.get("claim") or {}
    documents = claim_context.get("documents") or {}
    ocr_texts = claim_context.get("ocr_texts") or {}
    extraction_meta = claim_context.get("extraction_meta") or {}
    normalized = claim_context.get("normalized") or {}
    medical_ctx = claim_context.get("medical") or {}

    def _pick_date(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        if payload.get("date"):
            return str(payload.get("date"))
        dates = payload.get("dates")
        if isinstance(dates, list) and dates:
            return str(dates[0])
        return None

    # OCR: average over available docs; if the caller provided already-structured documents (like Assignment test cases)
    # without OCR text, treat OCR as "not applicable" rather than a penalty.
    merged_text = "\n\n".join([(ocr_texts.get(k) or "") for k in sorted(ocr_texts.keys())]).strip()
    avg_ocr_conf = None
    structured_mode = (not merged_text) and bool(documents)
    if structured_mode:
        # Provide a lightweight synthetic text so OCR heuristics don't punish structured inputs.
        synth_parts: list[str] = []
        rx = documents.get("prescription") or {}
        if isinstance(rx, dict):
            for k in ("doctor_reg", "diagnosis", "doctor_name"):
                if rx.get(k):
                    synth_parts.append(str(rx.get(k)))
        bill = documents.get("bill") or {}
        if isinstance(bill, dict):
            synth_parts.extend([str(k) for k in bill.keys()][:15])
        merged_text = " ".join(synth_parts).strip()
        avg_ocr_conf = 0.8

    prescription = documents.get("prescription") or {}
    bill = documents.get("bill") or {}

    required_fields = ["doctor_reg", "diagnosis", "patient_name"]
    extracted_payload = prescription if isinstance(prescription, dict) else {}

    rx_meta = extraction_meta.get("prescription") if isinstance(extraction_meta, dict) else None
    rx_meta = rx_meta if isinstance(rx_meta, dict) else {}
    schema_valid = bool(rx_meta.get("schema_valid", True)) and isinstance(prescription, dict)

    field_confidences: dict[str, float] = {}
    if isinstance(rx_meta.get("field_confidences"), dict):
        for k, v in rx_meta.get("field_confidences", {}).items():
            try:
                field_confidences[str(k)] = float(v)
            except Exception:
                continue

    # Consistency heuristics
    member_name = claim.get("member_name") or ""
    patient_name = (prescription.get("patient_name") if isinstance(prescription, dict) else None) or ""
    patient_match_score = _string_similarity(str(member_name), str(patient_name)) if patient_name else 0.45

    treatment_date = parse_date(str(claim.get("treatment_date") or ""))
    rx_date = parse_date(str(_pick_date(prescription) or "")) if isinstance(prescription, dict) else None
    bill_date = parse_date(str(_pick_date(bill) or "")) if isinstance(bill, dict) else None
    date_consistency_score = 0.55
    if treatment_date and (rx_date or bill_date):
        matches = []
        if rx_date:
            matches.append(rx_date == treatment_date)
        if bill_date:
            matches.append(bill_date == treatment_date)
        date_consistency_score = 1.0 if all(matches) else 0.4

    diagnosis = (prescription.get("diagnosis") if isinstance(prescription, dict) else None) or normalized.get("diagnosis") or claim.get("diagnosis") or ""
    billed_text = " ".join([str(k).lower() for k in (bill or {}).keys()]) if isinstance(bill, dict) else ""
    diagnosis_treatment_alignment = 0.7 if diagnosis else 0.35
    if diagnosis and billed_text:
        # very rough alignment: if diagnosis keyword appears in billed text, bump.
        diagnosis_treatment_alignment = 0.85 if str(diagnosis).lower().split()[0] in billed_text else 0.7

    prescription_bill_overlap = 0.7
    if isinstance(bill, dict) and isinstance(prescription, dict):
        meds = prescription.get("medicines_prescribed") or []
        meds_text = " ".join([str(m).lower() for m in meds])
        prescription_bill_overlap = 0.6 if meds and meds_text and all(m.lower().split()[0] not in billed_text for m in meds if isinstance(m, str)) else 0.75

    claim_amount = float(claim.get("claim_amount") or 0)
    bill_total = None
    if isinstance(bill, dict):
        if isinstance(bill.get("bill_total"), (int, float)):
            bill_total = float(bill.get("bill_total"))
        elif isinstance(bill.get("amounts"), list) and bill.get("amounts"):
            try:
                bill_total = float(max([float(x) for x in bill.get("amounts") if isinstance(x, (int, float, str))]))
            except Exception:
                bill_total = None
    amount_consistency_score = 0.45 if (claim_amount and bill_total is None) else 0.7
    if claim_amount and bill_total:
        ratio = bill_total / claim_amount
        amount_consistency_score = 1.0 if 0.85 <= ratio <= 1.15 else 0.6

    # Rule certainty: penalize partials and manual review; reward straight-through deterministic outcomes.
    decision_value = decision.get("decision") or ""
    rejection_reasons = decision.get("rejection_reasons") or []
    decision_flags = decision.get("flags") or []

    decision_path_determinism = 0.9
    conflict_penalty = 0.1
    if decision_value == "MANUAL_REVIEW":
        decision_path_determinism = 0.6
        conflict_penalty = 0.5
    elif decision_value == "PARTIAL":
        decision_path_determinism = 0.75
        conflict_penalty = 0.35
    elif rejection_reasons:
        decision_path_determinism = 0.85
        conflict_penalty = 0.2

    category_mapping_confidence = 0.8 if isinstance(bill, dict) and bill else 0.6
    policy_match_confidence = 0.9 if rejection_reasons or decision_value in ("APPROVED", "PARTIAL") else 0.7

    # Medical necessity: use service output when available; otherwise fall back to heuristics.
    diagnosis_present_score = 1.0 if (normalized.get("diagnosis") or diagnosis) else 0.35
    llm_alignment_confidence = float(medical_ctx.get("confidence") or 0.6)
    exclusion_penalty = 0.0
    if "SERVICE_NOT_COVERED" in rejection_reasons:
        exclusion_penalty = 0.7

    medical_inputs = {
        "diagnosis_present_score": diagnosis_present_score,
        "diagnosis_service_compatibility": diagnosis_treatment_alignment,
        "prescription_support_score": prescription_bill_overlap,
        "llm_alignment_confidence": llm_alignment_confidence,
        "exclusion_penalty": exclusion_penalty,
    }

    manual_review_flags: list[str] = []
    # Only treat specific signals as "manual review override" signals for confidence aggregation.
    if decision_value == "MANUAL_REVIEW":
        if isinstance(decision_flags, list):
            manual_review_flags.extend([str(x) for x in decision_flags if x])
        manual_review_flags.append("manual_review_decision")
    else:
        for f in (decision_flags or []):
            if str(f) in {"weak_patient_match", "patient_name_missing"}:
                manual_review_flags.append(str(f))

    critical_missing_fields: list[str] = []
    if "MISSING_DOCUMENTS" in rejection_reasons:
        critical_missing_fields.extend(["prescription", "bill"])

    # Treat key missing extracted fields as critical for confidence.
    for f in required_fields:
        if not (isinstance(extracted_payload, dict) and extracted_payload.get(f) not in (None, "", [], {})):
            critical_missing_fields.append(f)
    if isinstance(rx_meta.get("missing_fields"), list):
        critical_missing_fields.extend([str(x) for x in rx_meta.get("missing_fields") if x])

    expected_min_chars = 30 if structured_mode else 120
    return ConfidenceInputs(
        ocr_inputs={"avg_ocr_confidence": avg_ocr_conf, "extracted_text": merged_text, "expected_min_chars": expected_min_chars},
        extraction_inputs={
            "field_confidences": field_confidences,
            "required_fields": required_fields,
            "extracted_payload": extracted_payload,
            "schema_valid": schema_valid,
            "normalization_success": 0.9,
            "evidence_alignment": 0.85,
        },
        consistency_inputs={
            "patient_match_score": patient_match_score,
            "date_consistency_score": date_consistency_score,
            "diagnosis_treatment_alignment": diagnosis_treatment_alignment,
            "prescription_bill_overlap": prescription_bill_overlap,
            "amount_consistency_score": amount_consistency_score,
        },
        rule_inputs={
            "decision_path_determinism": decision_path_determinism,
            "category_mapping_confidence": category_mapping_confidence,
            "policy_match_confidence": policy_match_confidence,
            "conflict_penalty": conflict_penalty,
        },
        medical_inputs=medical_inputs,
        manual_review_flags=manual_review_flags,
        critical_missing_fields=sorted(set(critical_missing_fields)),
    )
