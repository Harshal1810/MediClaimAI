from __future__ import annotations


CLASSIFY_DOCUMENT_SYSTEM = """You are a document classification assistant.
Classify the medical insurance document into one of:
  prescription, bill, report, pharmacy_bill, unknown

You MUST ONLY classify type. Do not extract fields and do not adjudicate.
Return only valid JSON matching the schema."""


def classify_document_user_prompt(*, filename: str | None, ocr_text: str) -> str:
    return f"""Filename: {filename or ""}

OCR text:
--- OCR TEXT START ---
{ocr_text}
--- OCR TEXT END ---
"""

