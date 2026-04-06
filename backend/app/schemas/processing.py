from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.schemas.claim import LLMRuntimeConfig


class ProcessDocumentsRequest(BaseModel):
    use_llm: bool = False
    llm_config: LLMRuntimeConfig | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.use_llm and not self.llm_config:
            raise ValueError("use_llm=true requires llm_config {provider, api_key, model}.")
        if not self.use_llm and self.llm_config is not None:
            raise ValueError("use_llm=false must not include llm_config.")


class ProcessedDocument(BaseModel):
    document_id: str
    filename: str
    document_type: str | None = None
    classification_method: str
    classification_confidence: float
    extraction_method: str
    extraction_confidence: float
    schema_valid: bool
    missing_fields: list[str] = []
    extracted: dict[str, Any]
    ocr_text_excerpt: str | None = None
    flags: list[str] | None = None


class ProcessDocumentsResponse(BaseModel):
    claim_id: str
    use_llm: bool
    llm_provider: str | None = None
    llm_model: str | None = None
    documents: list[ProcessedDocument]
    normalized: dict[str, Any] | None = None
    medical: dict[str, Any] | None = None
    flags: list[str] | None = None

