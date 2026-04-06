from __future__ import annotations

from app.llm.schemas import DocumentType


EXTRACT_DOCUMENT_SYSTEM = """You are a medical insurance document extraction engine.
You ONLY extract fields from OCR text. You MUST NOT adjudicate, approve, reject, or compute payouts.
Return only valid JSON that matches the requested schema.

General rules:
- If a field is not present in the text, set it to null (or [] for lists).
- Prefer ISO dates: YYYY-MM-DD when possible.
- Amounts should be numbers (no currency symbols).
- Populate field_confidences with 0.0-1.0 per field you fill (omit unknown fields).
- confidence is your overall extraction confidence 0.0-1.0.
"""


def extract_document_user_prompt(*, document_type_hint: DocumentType, ocr_text: str) -> str:
    return f"""Document type hint: {document_type_hint}

Extract the relevant fields from the following OCR text:
--- OCR TEXT START ---
{ocr_text}
--- OCR TEXT END ---
"""
