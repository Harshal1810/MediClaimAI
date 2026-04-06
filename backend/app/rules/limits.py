from __future__ import annotations

from app.rules.codes import BELOW_MIN_AMOUNT, LATE_SUBMISSION, PARTIAL
from app.rules.date_utils import parse_date


def check_minimum_amount(claim_context: dict, policy: dict) -> tuple[bool, str | None, dict]:
    claim_amount = float((claim_context.get("claim") or {}).get("claim_amount") or 0)
    minimum = float(policy["claim_requirements"]["minimum_claim_amount"])
    if claim_amount < minimum:
        return False, BELOW_MIN_AMOUNT, {"notes": f"Claim below ₹{int(minimum)} minimum."}
    return True, None, {}


def check_submission_timeline(claim_context: dict, policy: dict) -> tuple[bool, str | None, dict]:
    claim = claim_context.get("claim") or {}
    treatment_date = parse_date(claim.get("treatment_date"))
    submission_date = parse_date(claim.get("submission_date"))
    if not treatment_date or not submission_date:
        return True, None, {}
    allowed_days = int(policy["claim_requirements"]["submission_timeline_days"])
    if (submission_date - treatment_date).days > allowed_days:
        return False, LATE_SUBMISSION, {"notes": f"Submitted after {allowed_days}-day window."}
    return True, None, {}


def _sum_numeric_values(mapping: dict) -> float:
    total = 0.0
    for v in mapping.values():
        if isinstance(v, (int, float)):
            total += float(v)
    return total


def _categorize_bill(bill: dict) -> tuple[dict[str, float], list[str]]:
    categories: dict[str, float] = {}
    rejected_items: list[str] = []

    # Avoid double counting: if the bill contains itemized amounts (consultation/tests/etc),
    # ignore summary total/gross/net fields.
    numeric_keys = [k for k, v in bill.items() if isinstance(v, (int, float))]
    has_itemized = any(
        ("total" not in str(k).lower() and "gross" not in str(k).lower() and "net" not in str(k).lower())
        for k in numeric_keys
    )
    for key, value in bill.items():
        if not isinstance(value, (int, float)):
            continue
        k = key.lower().replace("_", " ").strip()
        if has_itemized and any(x in k for x in ("total", "gross", "net", "amount payable")):
            continue
        amount = float(value)
        if "consultation" in k:
            categories["consultation_fees"] = categories.get("consultation_fees", 0) + amount
            continue
        if "medicine" in k or "pharmacy" in k:
            categories["pharmacy"] = categories.get("pharmacy", 0) + amount
            continue
        if "mri" in k or "ct" in k or "scan" in k or "test" in k or "diagnostic" in k:
            categories["diagnostic_tests"] = categories.get("diagnostic_tests", 0) + amount
            continue
        if "root canal" in k or "filling" in k or "extraction" in k or "cleaning" in k or "dental" in k:
            categories["dental"] = categories.get("dental", 0) + amount
            continue
        if "whitening" in k:
            rejected_items.append("Teeth whitening - cosmetic procedure")
            continue
        if "therapy" in k or "ayur" in k:
            categories["alternative_medicine"] = categories.get("alternative_medicine", 0) + amount
            continue
        if "glasses" in k or "lens" in k or "vision" in k or "eye" in k:
            categories["vision"] = categories.get("vision", 0) + amount
            continue
        categories["other"] = categories.get("other", 0) + amount
    return categories, rejected_items


def categorize_bill(bill: dict) -> tuple[dict[str, float], list[str]]:
    """
    Public wrapper around bill categorization.

    Returns (category_amounts, rejected_items).
    """
    return _categorize_bill(bill or {})


def apply_sub_limits(categories: dict[str, float], policy: dict) -> tuple[dict[str, float], dict[str, float]]:
    """Return (approved_by_category, deductions_by_category)."""
    approved: dict[str, float] = {}
    deductions: dict[str, float] = {}
    for category, amount in categories.items():
        if category == "consultation_fees":
            limit = float(policy["coverage_details"]["consultation_fees"]["sub_limit"])
        elif category in ("diagnostic_tests", "pharmacy", "dental", "vision", "alternative_medicine"):
            limit = float(policy["coverage_details"][category]["sub_limit"])
        else:
            limit = amount

        approved_amount = min(amount, limit)
        approved[category] = approved_amount
        if approved_amount < amount:
            deductions[f"{category}_sub_limit"] = round(amount - approved_amount, 2)
    return approved, deductions


def enforce_per_claim_limit(approved_by_category: dict[str, float], policy: dict, derived_rules: dict) -> tuple[bool, str | None, dict]:
    # Strict mode: per-claim limit is a hard cap on approved payout (handled as partial approval with deductions),
    # not a hard rejection.
    return True, None, {}


def compute_financial_breakdown(claim_context: dict, policy: dict, derived_rules: dict) -> dict:
    documents = claim_context.get("documents") or {}
    bill = documents.get("bill") or {}

    categories, rejected_items = categorize_bill(bill)
    if not categories and bill:
        categories = {"other": _sum_numeric_values(bill)}

    excluded_categories = claim_context.get("coverage_exclusions") or []
    excluded_categories = [str(x) for x in excluded_categories if x]
    excluded_amounts: dict[str, float] = {}
    if excluded_categories:
        for cat in list(categories.keys()):
            if cat in excluded_categories:
                excluded_amounts[cat] = float(categories.get(cat) or 0.0)
                categories.pop(cat, None)
                rejected_items.append(f"{cat} not covered under policy")

    approved_by_category, limit_deductions = apply_sub_limits(categories, policy)
    approved_before_caps = round(sum(approved_by_category.values()), 2)

    per_claim_limit = float(policy["coverage_details"]["per_claim_limit"])
    approved_after_per_claim = min(approved_before_caps, per_claim_limit)
    per_claim_deduction = round(max(0.0, approved_before_caps - approved_after_per_claim), 2)

    return {
        "bill": bill,
        "excluded_categories": excluded_categories or None,
        "excluded_amounts": excluded_amounts or None,
        "categories": categories,
        "rejected_items": rejected_items,
        "approved_by_category": approved_by_category,
        "limit_deductions": limit_deductions,
        "approved_before_caps": approved_before_caps,
        "per_claim_limit": per_claim_limit,
        "per_claim_deduction": per_claim_deduction,
        "approved_after_per_claim": round(approved_after_per_claim, 2),
    }


def compute_financial_outcome(claim_context: dict, policy: dict, derived_rules: dict) -> dict:
    breakdown = compute_financial_breakdown(claim_context, policy, derived_rules)
    rejected_items = breakdown["rejected_items"]
    categories = breakdown["categories"]
    approved_amount = float(breakdown["approved_after_per_claim"])

    deductions: dict[str, float] = {}
    deductions.update({k: float(v) for k, v in (breakdown.get("limit_deductions") or {}).items()})

    decision_hint = None
    notes: list[str] = []
    if breakdown.get("per_claim_deduction"):
        decision_hint = PARTIAL
        deductions["per_claim_cap"] = float(breakdown["per_claim_deduction"])
        notes.append(f"Approved amount capped to per-claim limit of ₹{int(breakdown['per_claim_limit'])}")

    if rejected_items:
        return {
            "ok": True,
            "decision_hint": PARTIAL,
            "approved_amount": approved_amount,
            "deductions": deductions or None,
            "rejected_items": rejected_items,
            "categories": categories,
            "notes": " | ".join(notes) if notes else None,
        }

    return {
        "ok": True,
        "decision_hint": decision_hint,
        "approved_amount": approved_amount,
        "deductions": deductions or None,
        "categories": categories,
        "notes": " | ".join(notes) if notes else None,
    }
