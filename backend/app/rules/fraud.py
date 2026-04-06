from __future__ import annotations


def detect_fraud_signals(claim_context: dict) -> dict:
    claim = claim_context.get("claim") or {}
    previous_claims_same_day = int(claim.get("previous_claims_same_day") or 0)
    flags: list[str] = []

    if previous_claims_same_day >= 3:
        flags.append("Multiple claims same day")
        flags.append("Unusual pattern detected")
        return {"manual_review": True, "flags": flags, "confidence": 0.65}

    return {"manual_review": False, "flags": [], "confidence": 0.95}
