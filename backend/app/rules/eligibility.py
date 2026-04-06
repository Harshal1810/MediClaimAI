from __future__ import annotations

from datetime import timedelta

from app.rules.codes import POLICY_INACTIVE, WAITING_PERIOD
from app.rules.date_utils import parse_date


def check_basic_eligibility(claim_context: dict, policy: dict) -> tuple[bool, str | None, dict]:
    claim = claim_context.get("claim") or {}
    treatment_date = parse_date(claim.get("treatment_date"))
    effective_date = parse_date(policy.get("effective_date"))
    if treatment_date and effective_date and treatment_date < effective_date:
        return False, POLICY_INACTIVE, {"notes": "Policy not active on treatment date."}
    return True, None, {}


def _diagnosis_keywords(diagnosis: str | None) -> set[str]:
    if not diagnosis:
        return set()
    tokens = set()
    lowered = diagnosis.lower()
    for key in ("diabetes", "hypertension"):
        if key in lowered:
            tokens.add(key)
    return tokens


def check_waiting_period(claim_context: dict, policy: dict, derived_rules: dict) -> tuple[bool, str | None, dict]:
    claim = claim_context.get("claim") or {}
    member_join_date = parse_date(claim.get("member_join_date"))
    treatment_date = parse_date(claim.get("treatment_date"))
    if not member_join_date or not treatment_date:
        return True, None, {}

    diagnosis = (claim_context.get("documents") or {}).get("prescription", {}).get("diagnosis") or claim.get("diagnosis")
    keywords = _diagnosis_keywords(diagnosis)

    waiting_periods = policy.get("waiting_periods", {})
    precedence = derived_rules.get("waiting_period_precedence") or ["specific_ailment", "pre_existing_disease", "initial_waiting"]

    def required_days(kind: str) -> int | None:
        if kind == "specific_ailment" and keywords:
            specific = waiting_periods.get("specific_ailments", {})
            days = max((specific.get(k) or 0) for k in keywords)
            return days or None
        if kind == "pre_existing_disease":
            return waiting_periods.get("pre_existing_diseases") or None
        if kind == "initial_waiting":
            return waiting_periods.get("initial_waiting") or None
        return None

    needed_days = None
    for kind in precedence:
        needed_days = required_days(kind)
        if needed_days:
            break

    if not needed_days:
        return True, None, {}

    eligible_date = member_join_date + timedelta(days=int(needed_days))
    if treatment_date < eligible_date:
        if "diabetes" in keywords and int(needed_days) == int(waiting_periods.get("specific_ailments", {}).get("diabetes") or 0):
            notes = f"Diabetes has {int(needed_days)}-day waiting period. Eligible from {eligible_date.isoformat()}"
        elif "hypertension" in keywords and int(needed_days) == int(waiting_periods.get("specific_ailments", {}).get("hypertension") or 0):
            notes = f"Hypertension has {int(needed_days)}-day waiting period. Eligible from {eligible_date.isoformat()}"
        else:
            notes = f"Waiting period not completed. Eligible from {eligible_date.isoformat()}"
        return (
            False,
            WAITING_PERIOD,
            {"notes": notes},
        )
    return True, None, {}
