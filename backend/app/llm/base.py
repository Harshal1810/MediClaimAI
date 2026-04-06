from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.trace = None
        self.trace_meta: dict = {}

    def set_trace(self, trace, meta: dict | None = None) -> None:
        self.trace = trace
        self.trace_meta = meta or {}

    @abstractmethod
    def extract_structured_document(self, ocr_text: str, document_type_hint: str | None = None):
        raise NotImplementedError

    @abstractmethod
    def assess_medical_necessity(self, normalized_context: dict):
        raise NotImplementedError

    @abstractmethod
    def classify_document_type(self, ocr_text: str, filename: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def review_final_decision(self, *, claim_context: dict, deterministic_result: dict) -> dict:
        """
        Advisory-only cross-check of the deterministic decision.

        Must never be used as the source of truth for final adjudication.
        """
        raise NotImplementedError
