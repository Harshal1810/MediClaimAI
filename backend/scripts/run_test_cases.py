from __future__ import annotations

import json
from pathlib import Path

from app.rules.engine import adjudicate_claim
from app.services.policy_loader import PolicyLoader


def _repo_root() -> Path:
    # scripts/ -> backend/ -> MediClaimAI/
    return Path(__file__).resolve().parents[2]


def load_assignment_test_cases() -> list[dict]:
    test_cases_path = _repo_root() / "Assignment" / "test_cases.json"
    with open(test_cases_path, "r", encoding="utf-8") as f:
        return json.load(f)["test_cases"]


def build_claim_context(input_data: dict) -> dict:
    claim = {
        "member_id": input_data.get("member_id"),
        "member_name": input_data.get("member_name"),
        "member_join_date": input_data.get("member_join_date"),
        "treatment_date": input_data.get("treatment_date"),
        "submission_date": input_data.get("submission_date") or input_data.get("treatment_date"),
        "claim_amount": input_data.get("claim_amount"),
        "previous_claims_same_day": input_data.get("previous_claims_same_day", 0),
        "hospital": input_data.get("hospital"),
        "cashless_request": input_data.get("cashless_request", False),
    }
    return {"claim": claim, "documents": input_data.get("documents") or {}}


def _diff_expected(expected: dict, actual: dict) -> list[str]:
    diffs: list[str] = []
    for key, expected_value in expected.items():
        if key not in actual:
            diffs.append(f"Missing key: {key}")
            continue
        actual_value = actual[key]
        if isinstance(expected_value, (int, float)) and isinstance(actual_value, (int, float)):
            if round(float(actual_value), 2) != round(float(expected_value), 2):
                diffs.append(f"{key}: expected {expected_value}, got {actual_value}")
        elif actual_value != expected_value:
            diffs.append(f"{key}: expected {expected_value}, got {actual_value}")
    return diffs


def _basic_invariants(actual: dict, policy: dict) -> list[str]:
    errors: list[str] = []
    if "decision" not in actual:
        errors.append("Missing decision")
    if "approved_amount" not in actual:
        errors.append("Missing approved_amount")
        return errors
    try:
        approved = float(actual["approved_amount"])
    except Exception:
        errors.append("approved_amount is not numeric")
        return errors
    if approved < 0:
        errors.append("approved_amount is negative")
    per_claim = float(policy["coverage_details"]["per_claim_limit"])
    if approved > per_claim + 1e-6 and actual.get("decision") != "MANUAL_REVIEW":
        errors.append(f"approved_amount exceeds per-claim limit ({approved} > {per_claim})")
    return errors


def main() -> int:
    policy = PolicyLoader.load_policy()
    derived_rules = PolicyLoader.load_derived_rules()

    failures = 0
    mismatches = 0
    for tc in load_assignment_test_cases():
        case_id = tc["case_id"]
        ctx = build_claim_context(tc["input_data"])
        actual = adjudicate_claim(ctx, policy, derived_rules)
        invariant_errors = _basic_invariants(actual, policy)
        if invariant_errors:
            failures += 1
            print(f"[FAIL] {case_id} - {tc['case_name']} (invariant)")
            for e in invariant_errors:
                print(f"  - {e}")
            print(f"  actual: {actual}")
            continue

        diffs = _diff_expected(tc["expected_output"], actual)
        if diffs:
            mismatches += 1
            print(f"[WARN] {case_id} - {tc['case_name']} (diff vs sample expected)")
            for d in diffs:
                safe = str(d).replace("₹", "Rs ")
                print(f"  - {safe}")
            if actual.get("notes"):
                notes = str(actual["notes"]).replace("₹", "Rs ")
                print(f"  notes: {notes}")
        else:
            print(f"[OK] {case_id} - {tc['case_name']}")

    total = len(load_assignment_test_cases())
    print()
    print(f"Done. Invariant pass {total - failures}/{total}. Sample-expected diffs {mismatches}/{total}.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
