from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.schemas.claim import ClaimCreateRequest, LLMRuntimeConfig
from app.services.extraction_service import ExtractionService
from app.services.runtime_config import RuntimeProcessingConfig


def test_claim_create_use_llm_false_allows_null_llm_config():
    payload = ClaimCreateRequest(
        session_id="S1",
        member_id="EMP001",
        member_name="Rajesh Kumar",
        treatment_date="2024-11-01",
        submission_date="2024-11-01",
        claim_amount=1000,
        use_llm=False,
        llm_config=None,
    )
    assert payload.use_llm is False
    assert payload.llm_config is None


def test_claim_create_use_llm_true_requires_llm_config():
    with pytest.raises(ValueError):
        ClaimCreateRequest(
            session_id="S1",
            member_id="EMP001",
            member_name="Rajesh Kumar",
            treatment_date="2024-11-01",
            submission_date="2024-11-01",
            claim_amount=1000,
            use_llm=True,
            llm_config=None,
        )


def _make_local_tmp_file() -> str:
    base = Path(__file__).resolve().parents[2] / ".tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"tmp_{uuid.uuid4().hex}.bin"
    path.write_bytes(b"")
    return str(path)


def test_rule_based_mode_never_calls_provider_factory(monkeypatch):
    # If provider factory gets called, fail the test.
    from app.llm import provider_factory

    def boom(*args, **kwargs):
        raise AssertionError("Provider factory should not be called in rule-based mode")

    monkeypatch.setattr(provider_factory.LLMProviderFactory, "create", boom)

    # Make an empty file; OCR will likely return empty text, but extraction must still be deterministic.
    file_path = _make_local_tmp_file()

    runtime = RuntimeProcessingConfig(use_llm=False)
    result = ExtractionService().extract_document_data(file_path=file_path, runtime=runtime, document_type_hint="prescription")
    assert result["extraction_method"] == "rule_based"


def test_llm_mode_provider_failure_falls_back(monkeypatch):
    from app.llm import provider_factory

    def boom(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(provider_factory.LLMProviderFactory, "create", boom)

    file_path = _make_local_tmp_file()

    runtime = RuntimeProcessingConfig(use_llm=True, llm_provider="openai", llm_model="gpt-4.1-mini", llm_api_key="sk-test-1234567890")
    result = ExtractionService().extract_document_data(file_path=file_path, runtime=runtime, document_type_hint="prescription")
    assert result["extraction_method"] == "rule_based"
    # For empty/unsupported files OCR can be empty; in that case we short-circuit with `empty_ocr_text`.
    assert any(
        f in (result.get("flags") or [])
        for f in ("llm_extraction_failed_fallback_used", "empty_ocr_text")
    )
