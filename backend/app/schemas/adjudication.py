from typing import Any
from pydantic import BaseModel
from app.schemas.claim import LLMRuntimeConfig


class AdjudicationRequest(BaseModel):
    claim_context: dict[str, Any]


class AdjudicateStoredClaimRequest(BaseModel):
    use_llm: bool = False
    llm_config: LLMRuntimeConfig | None = None

    @staticmethod
    def _err(msg: str) -> None:
        raise ValueError(msg)

    def model_post_init(self, __context: Any) -> None:
        if self.use_llm and not self.llm_config:
            self._err("use_llm=true requires llm_config {provider, api_key, model}.")
        if not self.use_llm and self.llm_config is not None:
            self._err("use_llm=false must not include llm_config.")


class AdjudicationResponse(BaseModel):
    decision: str
    approved_amount: float
    rejection_reasons: list[str]
    confidence_score: float
    deductions: dict[str, float] | None = None
    # Note: "flags" is used both for fraud/manual-review flags and processing flags. Keep as a single list.
    flags: list[str] | None = None
    notes: str | None = None
    next_steps: str | None = None
    rejected_items: list[str] | None = None
    cashless_approved: bool | None = None
    network_discount: float | None = None
    confidence_action: str | None = None
    confidence_flags: list[str] | None = None
    confidence_breakdown: dict[str, Any] | None = None
    # When decision is MANUAL_REVIEW, these may contain the deterministic recommendation.
    recommended_decision: str | None = None
    recommended_approved_amount: float | None = None
    # Processing metadata
    use_llm: bool | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    classification_method: str | None = None
    extraction_method: str | None = None
    medical_method: str | None = None
    flags: list[str] | None = None
    # Optional advisory-only LLM cross-check of the final result (never authoritative).
    llm_final_review: dict[str, Any] | None = None
