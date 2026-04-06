from __future__ import annotations

from dataclasses import dataclass

from app.llm.provider_factory import LLMProviderFactory
from app.services.runtime_config import RuntimeProcessingConfig


@dataclass(frozen=True)
class DocumentClassification:
    document_type: str
    classification_method: str  # "rule_based" | "llm"
    confidence: float


class DocumentClassifier:
    """
    Deterministic first-pass classifier with optional LLM fallback.

    Types used by the pipeline:
      - prescription
      - bill
      - report
      - pharmacy_bill
      - unknown
    """

    PRESCRIPTION_KEYWORDS = ["rx", "prescription", "reg.", "reg no", "diagnosis", "chief complaints", "doctor", "dr."]
    BILL_KEYWORDS = ["bill", "invoice", "gst", "total", "sub total", "consultation", "amount", "receipt"]
    REPORT_KEYWORDS = ["report", "result", "normal range", "hemoglobin", "wbc", "platelets", "lab", "diagnostic"]
    PHARMACY_KEYWORDS = ["pharmacy", "drug", "batch", "mrp", "qty", "tablet", "capsule"]

    def classify(self, *, filename: str, ocr_text: str, runtime: RuntimeProcessingConfig, trace=None, trace_meta: dict | None = None) -> DocumentClassification:
        text = (ocr_text or "").lower()
        name = (filename or "").lower()

        # Strong filename hints (common in our test pack).
        if "pharmacy" in name or "medicine" in name:
            return DocumentClassification(document_type="pharmacy_bill", classification_method="rule_based", confidence=0.92)
        if "prescription" in name or name.startswith("rx"):
            return DocumentClassification(document_type="prescription", classification_method="rule_based", confidence=0.92)
        if "lab" in name or "report" in name:
            return DocumentClassification(document_type="report", classification_method="rule_based", confidence=0.9)

        scores: dict[str, float] = {
            "prescription": self._keyword_score(text, name, self.PRESCRIPTION_KEYWORDS),
            "bill": self._keyword_score(text, name, self.BILL_KEYWORDS),
            "report": self._keyword_score(text, name, self.REPORT_KEYWORDS),
            "pharmacy_bill": self._keyword_score(text, name, self.PHARMACY_KEYWORDS),
        }

        best_type, best_score = max(scores.items(), key=lambda x: x[1])
        sorted_scores = sorted(scores.values(), reverse=True)
        runner_up = sorted_scores[1] if len(sorted_scores) > 1 else 0.0

        # Confidence heuristics.
        confidence = min(0.95, 0.55 + best_score)
        uncertain = (best_score < 0.35) or (best_score - runner_up < 0.15)

        if not uncertain:
            return DocumentClassification(document_type=best_type, classification_method="rule_based", confidence=confidence)

        if not runtime.use_llm:
            return DocumentClassification(document_type=best_type if best_score > 0 else "unknown", classification_method="rule_based", confidence=max(0.4, confidence - 0.15))

        # LLM fallback: only to choose a doc type label. Never used for decisions.
        try:
            provider = LLMProviderFactory.create(
                provider=runtime.llm_provider or "",
                api_key=runtime.llm_api_key or "",
                model=runtime.llm_model or "",
                trace=trace,
                trace_meta=trace_meta,
            )
            llm_type = provider.classify_document_type(ocr_text=ocr_text, filename=filename)
            llm_type = (llm_type or "").strip().lower()
            if llm_type in scores:
                return DocumentClassification(document_type=llm_type, classification_method="llm", confidence=0.75)
        except Exception:
            pass

        return DocumentClassification(document_type=best_type if best_score > 0 else "unknown", classification_method="rule_based", confidence=max(0.35, confidence - 0.2))

    @staticmethod
    def _keyword_score(text: str, filename: str, keywords: list[str]) -> float:
        if not text and not filename:
            return 0.0
        hay = f"{filename}\n{text}"
        hits = sum(1 for k in keywords if k in hay)
        return min(0.6, hits / max(len(keywords), 1))
