from __future__ import annotations

import json
from typing import Any


FINAL_REVIEW_SYSTEM = """You are an insurance claim adjudication assistant used ONLY for auditing.

Hard guardrails:
- You MUST NOT be the source of truth for the final decision. The deterministic rule engine is authoritative.
- You MUST NOT invent policy rules or new categories.
- Your job is to cross-check the provided deterministic decision and calculations against the provided evidence.

Return a single JSON object matching the provided schema.
"""


def final_review_user_prompt(*, claim_context: dict[str, Any], deterministic_result: dict[str, Any], financial_breakdown: dict[str, Any] | None) -> str:
    payload = {
        "claim": claim_context.get("claim") or {},
        "documents_primary": claim_context.get("documents") or {},
        "documents_by_type": claim_context.get("documents_by_type") or {},
        "normalized": claim_context.get("normalized") or {},
        "medical": claim_context.get("medical") or {},
        "processing": claim_context.get("processing") or {},
        "deterministic_result": deterministic_result or {},
        "financial_breakdown": financial_breakdown or {},
    }
    return (
        "Cross-check the deterministic decision.\n"
        "- Verify basic invariants (e.g., approved_amount should not exceed claim_amount).\n"
        "- Verify calculations are consistent with the extracted bill breakdown.\n"
        "- If anything looks missing/uncertain, list it explicitly.\n\n"
        f"INPUT:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

