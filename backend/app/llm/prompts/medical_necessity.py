from __future__ import annotations


MEDICAL_NECESSITY_SYSTEM = """You are a clinical reasoning assistant for an insurance adjudication pipeline.
You MUST NOT decide approve/reject or compute payouts. Your job is only to assess semantic alignment:
whether the diagnosis reasonably supports the services/tests/medicines/procedures.
Return only valid JSON matching the schema."""


def medical_necessity_user_prompt(*, normalized_context: dict) -> str:
    return f"""Given the normalized claim context (already extracted and normalized), assess alignment.

Normalized context JSON:
{normalized_context}
"""
