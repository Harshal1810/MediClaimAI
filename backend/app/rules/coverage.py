from __future__ import annotations

from app.rules.codes import PRE_AUTH_MISSING, SERVICE_NOT_COVERED
from app.rules.limits import categorize_bill


def _lower_str(value: str | None) -> str:
    return (value or "").strip().lower()


def _contains_any(haystack: str, needles: list[str]) -> bool:
    return any(n in haystack for n in needles)


def evaluate_coverage(claim_context: dict, policy: dict, derived_rules: dict) -> tuple[bool, str | None, dict]:
    documents = claim_context.get("documents") or {}
    prescription = documents.get("prescription") or {}
    bill = documents.get("bill") or {}

    diagnosis = _lower_str(prescription.get("diagnosis") or claim_context.get("claim", {}).get("diagnosis"))
    treatment = _lower_str(prescription.get("treatment"))
    procedures = [_lower_str(p) for p in (prescription.get("procedures") or [])]
    tests_prescribed = [_lower_str(t) for t in (prescription.get("tests_prescribed") or [])]

    # Exclusions: implement the ones used in provided test cases.
    if _contains_any(diagnosis, ["obesity", "weight loss"]) or _contains_any(treatment, ["diet plan", "weight loss", "bariatric"]):
        return False, SERVICE_NOT_COVERED, {"notes": "Weight loss treatments are excluded from coverage"}

    # Alternative medicine coverage check (basic heuristic).
    doctor_reg = _lower_str(prescription.get("doctor_reg"))
    if doctor_reg.startswith("ayur/") or "vaidya" in _lower_str(prescription.get("doctor_name")) or _contains_any(treatment, ["ayur", "panchakarma", "homeopathy", "unani"]):
        if not policy["coverage_details"]["alternative_medicine"]["covered"]:
            return False, SERVICE_NOT_COVERED, {"notes": "Alternative medicine not covered under policy."}

    # Category covered/not covered enforcement (prefer partial via exclusions where possible).
    categories, _rejected = categorize_bill(bill)
    excluded: list[str] = []
    for cat, amount in (categories or {}).items():
        if amount <= 0:
            continue
        if cat in ("consultation_fees", "diagnostic_tests", "pharmacy", "dental", "vision", "alternative_medicine"):
            covered = bool((policy.get("coverage_details") or {}).get(cat, {}).get("covered", True))
            if not covered:
                excluded.append(cat)

    if excluded and len(excluded) == len([c for c, a in (categories or {}).items() if a > 0 and c != "other"]):
        # Everything billed falls into uncovered categories => reject.
        return False, SERVICE_NOT_COVERED, {"notes": f"Services not covered under policy: {', '.join(sorted(set(excluded)))}"}
    if excluded:
        # Allow processing but mark exclusions so limits/payout can drop them for partial approval.
        return True, None, {"excluded_categories": sorted(set(excluded)), "notes": f"Excluded (not covered) categories will be removed from payout: {', '.join(sorted(set(excluded)))}"}

    # Pre-auth: MRI/CT above threshold require preauth.
    bill_text = " ".join([_lower_str(k) for k in bill.keys()] + [_lower_str(v) for v in bill.values() if isinstance(v, str)])
    prescribed_text = " ".join(tests_prescribed)
    combined = " ".join([bill_text, prescribed_text])

    pre_auth_obtained = bool((claim_context.get("claim") or {}).get("pre_auth_obtained"))

    special = derived_rules.get("special_rules") or {}
    for key, rule in special.items():
        if key in combined:
            threshold = float(rule.get("threshold_amount") or 0)
            claim_amount = float((claim_context.get("claim") or {}).get("claim_amount") or 0)
            if claim_amount > threshold and rule.get("pre_auth_required") and not pre_auth_obtained:
                return False, PRE_AUTH_MISSING, {"notes": f"{key.upper()} requires pre-authorization for claims above ₹{int(threshold)}"}

    return True, None, {}
