from __future__ import annotations

from app.rules.calculators import apply_network_discount, apply_percentage_deduction
from app.rules.codes import APPROVED, MANUAL_REVIEW, NOT_MEDICALLY_NECESSARY, PARTIAL, REJECTED
from app.rules.coverage import evaluate_coverage
from app.rules.document_validation import validate_required_documents
from app.rules.eligibility import check_basic_eligibility, check_waiting_period
from app.rules.fraud import detect_fraud_signals
from app.rules.limits import check_minimum_amount, check_submission_timeline, compute_financial_outcome
from app.rules.limits import compute_financial_breakdown
from app.services.confidence_inputs import build_confidence_inputs
from app.services.confidence_service import ConfidenceService


def adjudicate_claim(claim_context: dict, policy: dict, derived_rules: dict, *, trace=None) -> dict:
    claim = claim_context.get("claim") or {}

    if trace is None:
        claim_id = (claim or {}).get("claim_id")
        if claim_id:
            try:
                from app.services.claim_trace_logger import ClaimTraceLogger

                trace = ClaimTraceLogger(str(claim_id))
            except Exception:
                trace = None

    def _t(event: str, payload: dict | None = None) -> None:
        if trace is None:
            return
        try:
            trace.log(event, payload or {})
        except Exception:
            return

    pipeline_flags: list[str] = []
    pipeline_notes: list[str] = []

    def _merge_meta(meta: dict | None) -> None:
        if not meta or not isinstance(meta, dict):
            return
        flags = meta.get("flags")
        if isinstance(flags, list):
            pipeline_flags.extend([str(f) for f in flags if f])
        note = meta.get("notes")
        if isinstance(note, str) and note.strip():
            pipeline_notes.append(note.strip())

    _t(
        "rules.start",
        {
            "claim": {
                "claim_id": claim.get("claim_id"),
                "member_id": claim.get("member_id"),
                "member_name": claim.get("member_name"),
                "treatment_date": claim.get("treatment_date"),
                "submission_date": claim.get("submission_date"),
                "claim_amount": claim.get("claim_amount"),
                "hospital": claim.get("hospital") or claim.get("hospital_name"),
                "cashless_requested": bool(claim.get("cashless_request") or claim.get("cashless_requested")),
            },
            "processing": claim_context.get("processing") or {},
        },
    )

    ok, reason, meta = check_minimum_amount(claim_context, policy)
    _t("rules.check_minimum_amount", {"ok": ok, "reason": reason, "meta": meta})
    if not ok:
        result = {
            "decision": REJECTED,
            "approved_amount": 0,
            "rejection_reasons": [reason],
            "confidence_score": 0.0,
            **meta,
        }
        return _attach_confidence(claim_context, result, trace=trace)
    _merge_meta(meta)

    ok, reason, meta = check_submission_timeline(claim_context, policy)
    _t("rules.check_submission_timeline", {"ok": ok, "reason": reason, "meta": meta})
    if not ok:
        result = {
            "decision": REJECTED,
            "approved_amount": 0,
            "rejection_reasons": [reason],
            "confidence_score": 0.0,
            **meta,
        }
        return _attach_confidence(claim_context, result, trace=trace)
    _merge_meta(meta)

    ok, reason, meta = check_basic_eligibility(claim_context, policy)
    _t("rules.check_basic_eligibility", {"ok": ok, "reason": reason, "meta": meta})
    if not ok:
        result = {
            "decision": REJECTED,
            "approved_amount": 0,
            "rejection_reasons": [reason],
            "confidence_score": 0.0,
            **meta,
        }
        return _attach_confidence(claim_context, result, trace=trace)
    _merge_meta(meta)

    ok, reason, meta = check_waiting_period(claim_context, policy, derived_rules)
    _t("rules.check_waiting_period", {"ok": ok, "reason": reason, "meta": meta})
    if not ok:
        result = {
            "decision": REJECTED,
            "approved_amount": 0,
            "rejection_reasons": [reason],
            "confidence_score": 0.0,
            **meta,
        }
        return _attach_confidence(claim_context, result, trace=trace)
    _merge_meta(meta)

    ok, reason, meta = validate_required_documents(claim_context, policy)
    _t("rules.validate_documents", {"ok": ok, "reason": reason, "meta": meta})
    if not ok:
        result = {
            "decision": REJECTED,
            "approved_amount": 0,
            "rejection_reasons": [reason],
            "confidence_score": 0.0,
            **meta,
        }
        return _attach_confidence(claim_context, result, trace=trace)
    _merge_meta(meta)

    fraud = detect_fraud_signals(claim_context)
    _t("rules.fraud_signals", fraud)
    if fraud["manual_review"]:
        result = {
            "decision": MANUAL_REVIEW,
            "approved_amount": 0,
            "rejection_reasons": [],
            "flags": fraud["flags"],
            "confidence_score": 0.0,
        }
        return _attach_confidence(claim_context, result, manual_review_override=True, trace=trace)

    # If document validation flagged a provider/hospital mismatch, do not auto-approve.
    if "hospital_name_mismatch" in pipeline_flags:
        result = {
            "decision": MANUAL_REVIEW,
            "approved_amount": 0,
            "rejection_reasons": [],
            "flags": sorted(set(pipeline_flags)),
            "confidence_score": 0.0,
            "notes": "Claim hospital name does not match hospital name on bill. Please verify and correct if needed.",
        }
        _t("rules.hospital_name_mismatch", {"manual_review": True})
        return _attach_confidence(claim_context, result, manual_review_override=True, trace=trace)

    ok, reason, meta = evaluate_coverage(claim_context, policy, derived_rules)
    _t("rules.evaluate_coverage", {"ok": ok, "reason": reason, "meta": meta})
    if not ok:
        result = {
            "decision": REJECTED,
            "approved_amount": 0,
            "rejection_reasons": [reason],
            "confidence_score": 0.0,
            **meta,
        }
        return _attach_confidence(claim_context, result, trace=trace)

    # Persist coverage exclusions into claim_context so payout calculation can drop them deterministically.
    if isinstance(meta, dict) and isinstance(meta.get("excluded_categories"), list):
        claim_context["coverage_exclusions"] = [str(x) for x in meta.get("excluded_categories") if x]
    _merge_meta(meta)

    # Medical necessity is mandatory for approval (deterministic signal; LLM cannot override this).
    medical_ctx = claim_context.get("medical") or {}
    if medical_ctx and medical_ctx.get("is_aligned") is False:
        result = {
            "decision": REJECTED,
            "approved_amount": 0,
            "rejection_reasons": [NOT_MEDICALLY_NECESSARY],
            "confidence_score": 0.0,
            "notes": str(medical_ctx.get("rationale") or "Medical necessity not established."),
            "flags": medical_ctx.get("flags") or None,
        }
        _t("rules.medical_necessity_gate", {"ok": False, "medical": medical_ctx})
        return _attach_confidence(claim_context, result, trace=trace)
    _t("rules.medical_necessity_gate", {"ok": True, "medical": medical_ctx})

    _t("financial.breakdown", compute_financial_breakdown(claim_context, policy, derived_rules))
    financial = compute_financial_outcome(claim_context, policy, derived_rules)
    _t("financial.outcome", financial)
    if not financial.get("ok"):
        reason = financial.get("reason")
        meta = {k: v for k, v in financial.items() if k not in {"ok", "reason"}}
        result = {
            "decision": REJECTED,
            "approved_amount": 0,
            "rejection_reasons": [reason],
            "confidence_score": 0.0,
            **meta,
        }
        return _attach_confidence(claim_context, result, trace=trace)

    approved_amount = float(financial.get("approved_amount") or claim.get("claim_amount") or 0)
    deductions = financial.get("deductions")
    rejected_items = financial.get("rejected_items")
    decision_hint = financial.get("decision_hint")
    categories = financial.get("categories") or {}
    financial_notes = financial.get("notes")

    hospital = (claim.get("hospital") or claim.get("hospital_name") or "").strip()
    cashless_requested = bool(claim.get("cashless_request") or claim.get("cashless_requested"))
    is_network = hospital in set(policy.get("network_hospitals") or [])
    cashless_approved = False
    if cashless_requested and is_network and policy.get("cashless_facilities", {}).get("available"):
        instant_limit = float(policy["cashless_facilities"]["instant_approval_limit"])
        cashless_approved = approved_amount <= instant_limit

    # Network discount: apply on total approved amount for network providers (adjudication rules).
    consultation_amount = float(categories.get("consultation_fees") or 0.0)
    non_consultation = max(approved_amount - float(categories.get("consultation_fees") or 0.0), 0.0)
    network_discount = 0.0
    if is_network and approved_amount > 0 and (derived_rules.get("network_cashless") or {}).get("apply_network_discount", True):
        discounted_total, discount_total = apply_network_discount(approved_amount, policy)
        # Apply the same discount rate to both components to preserve additivity.
        discount_rate = 1.0 - (discounted_total / approved_amount)
        consultation_amount = consultation_amount * (1.0 - discount_rate)
        non_consultation = non_consultation * (1.0 - discount_rate)
        network_discount = discount_total

    # Consultation co-pay applies only to consultation component (user decision).
    copay_percent = float(policy["coverage_details"]["consultation_fees"]["copay_percentage"])
    consultation_after_copay, copay = apply_percentage_deduction(consultation_amount, copay_percent) if consultation_amount > 0 else (0.0, 0.0)

    # Rebuild payout: consultation component is adjusted by discount + copay; remaining components keep discount only.
    final_amount = round(non_consultation + consultation_after_copay, 2)

    # Safety cap: never pay more than the claimed amount.
    claimed_amount = float(claim.get("claim_amount") or 0.0)
    if claimed_amount > 0 and final_amount > claimed_amount:
        _t("financial.cap_to_claim_amount", {"before": final_amount, "cap": claimed_amount})
        final_amount = round(claimed_amount, 2)
    _t(
        "financial.final_components",
        {
            "approved_before_adjustments": approved_amount,
            "consultation_component_before": float(categories.get("consultation_fees") or 0.0),
            "network_discount": float(network_discount or 0.0),
            "copay": float(copay or 0.0),
            "final_amount": float(final_amount),
        },
    )

    extra_deductions: dict[str, float] = {}
    if network_discount:
        extra_deductions["network_discount"] = round(network_discount, 2)
    if copay:
        extra_deductions["copay"] = round(copay, 2)
    if extra_deductions:
        deductions = {**(deductions or {}), **extra_deductions}
    claim_amount = float(claim.get("claim_amount") or 0.0)
    should_partial = False
    if decision_hint == PARTIAL:
        should_partial = True
    # If we applied any deductions (sub-limits, per-claim cap, network discount, co-pay), treat as partial.
    if deductions and any(float(v or 0.0) > 0.0 for v in (deductions or {}).values()):
        should_partial = True
    # If the payout is less than what the user claimed, treat as partial approval (assignment behavior).
    if claim_amount > 0 and (final_amount + 0.01) < claim_amount:
        should_partial = True

    base: dict = {
        "decision": PARTIAL if should_partial else APPROVED,
        "approved_amount": round(final_amount, 2),
        "rejection_reasons": [],
        "confidence_score": 0.0,
        "deductions": deductions or None,
    }
    if cashless_requested:
        base["cashless_approved"] = bool(cashless_approved)
    if network_discount:
        base["network_discount"] = round(network_discount, 2)

    if decision_hint == PARTIAL and rejected_items:
        base["rejected_items"] = rejected_items
    if decision_hint == PARTIAL:
        base["deductions"] = deductions or None
    if financial_notes:
        base["notes"] = financial_notes if not base.get("notes") else f"{base['notes']} | {financial_notes}"

    if pipeline_flags:
        base["flags"] = sorted(set([*(base.get("flags") or []), *pipeline_flags]))
    if pipeline_notes:
        merged_notes = " | ".join([n for n in pipeline_notes if n])
        if merged_notes:
            base["notes"] = merged_notes if not base.get("notes") else f"{base['notes']} | {merged_notes}"

    return _attach_confidence(claim_context, base)


def _attach_confidence(claim_context: dict, result: dict, manual_review_override: bool = False, *, trace=None) -> dict:
    svc = ConfidenceService()
    inputs = build_confidence_inputs(claim_context=claim_context, decision=result)
    breakdown = svc.aggregate(
        ocr=svc.compute_ocr_quality(**inputs.ocr_inputs),
        extraction=svc.compute_extraction_quality(**inputs.extraction_inputs),
        consistency=svc.compute_cross_document_consistency(**inputs.consistency_inputs),
        rules=svc.compute_rule_certainty(**inputs.rule_inputs),
        medical=svc.compute_medical_necessity_certainty(**inputs.medical_inputs),
        manual_review_flags=inputs.manual_review_flags,
        critical_missing_fields=inputs.critical_missing_fields,
    )

    if manual_review_override:
        breakdown.final_score = min(breakdown.final_score, 0.69)
        breakdown.action = "MANUAL_REVIEW"

    # Merge flags and notes back into result (without overwriting business flags).
    result["confidence_score"] = breakdown.final_score
    result["confidence_action"] = breakdown.action
    payload = breakdown.to_dict()
    processing = claim_context.get("processing") or {}
    payload["sources"] = {
        "use_llm": bool(processing.get("use_llm")),
        "classification_source": processing.get("classification_method"),
        "extraction_source": processing.get("extraction_method"),
        "medical_source": processing.get("medical_method"),
    }
    result["confidence_breakdown"] = payload
    if breakdown.flags:
        result["confidence_flags"] = breakdown.flags

    # Manual review trigger when confidence is low (assignment rule).
    if breakdown.action == "MANUAL_REVIEW" and result.get("decision") in (APPROVED, PARTIAL):
        result["recommended_decision"] = result.get("decision")
        result["recommended_approved_amount"] = result.get("approved_amount")
        result["decision"] = MANUAL_REVIEW
        result["approved_amount"] = 0
        flags = list(result.get("flags") or [])
        flags.append("low_confidence_manual_review")
        result["flags"] = sorted(set(flags))
        result["next_steps"] = "Manual review required (confidence below 70%)."

    if trace is not None:
        try:
            trace.log(
                "rules.final_result",
                {
                    "decision": result.get("decision"),
                    "approved_amount": result.get("approved_amount"),
                    "recommended_decision": result.get("recommended_decision"),
                    "recommended_approved_amount": result.get("recommended_approved_amount"),
                    "rejection_reasons": result.get("rejection_reasons") or [],
                    "flags": result.get("flags") or [],
                    "confidence_score": result.get("confidence_score"),
                    "confidence_action": result.get("confidence_action"),
                    "confidence_flags": result.get("confidence_flags") or [],
                },
            )
        except Exception:
            pass
    return result
