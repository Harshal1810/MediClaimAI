from __future__ import annotations

from dataclasses import dataclass

from app.llm.provider_factory import LLMProviderFactory
from app.services.runtime_config import RuntimeProcessingConfig


@dataclass(frozen=True)
class MedicalNecessityResult:
    is_aligned: bool
    rationale: str
    confidence: float
    medical_method: str  # "rule_based" | "llm_assisted"
    flags: list[str]


class MedicalNecessityService:
    EXCLUSION_KEYWORDS = ["cosmetic", "whitening", "weight loss", "diet plan"]

    def assess_rule_based(self, *, normalized: dict) -> MedicalNecessityResult:
        diagnosis = (normalized.get("diagnosis") or "").lower()
        tests = " ".join([str(x).lower() for x in (normalized.get("tests") or [])])
        meds = " ".join([str(x).lower() for x in (normalized.get("medicines") or [])])
        combined = " ".join([diagnosis, tests, meds])

        flags: list[str] = []
        if not diagnosis:
            flags.append("diagnosis_missing_or_weak")
        if any(k in combined for k in self.EXCLUSION_KEYWORDS):
            flags.append("possible_exclusion_or_cosmetic_signal")

        # Conservative: treat as aligned if diagnosis exists and no strong exclusion signals.
        is_aligned = bool(diagnosis) and "possible_exclusion_or_cosmetic_signal" not in flags
        confidence = 0.78 if is_aligned else (0.55 if diagnosis else 0.45)
        rationale = "Diagnosis present and supports billed items." if is_aligned else "Limited evidence of medical necessity from extracted fields."
        return MedicalNecessityResult(is_aligned=is_aligned, rationale=rationale, confidence=confidence, medical_method="rule_based", flags=flags)

    def assess(self, *, normalized: dict, runtime: RuntimeProcessingConfig, trace=None, trace_meta: dict | None = None) -> MedicalNecessityResult:
        base = self.assess_rule_based(normalized=normalized)
        if not runtime.use_llm:
            return base

        try:
            provider = LLMProviderFactory.create(
                provider=runtime.llm_provider or "",
                api_key=runtime.llm_api_key or "",
                model=runtime.llm_model or "",
                trace=trace,
                trace_meta=trace_meta,
            )
            resp = provider.assess_medical_necessity(normalized_context=normalized)
            llm_is_aligned = bool(resp.get("is_aligned", resp.get("is_medically_necessary", True)))
            llm_conf = float(resp.get("confidence") or 0.7)
            llm_conf = max(0.05, min(0.98, llm_conf))
            llm_rationale = str(resp.get("rationale") or resp.get("reason") or "LLM assessment provided.")

            # Guardrail: LLM must not be the sole decider of medical necessity.
            # If deterministic rule-based checks say "not aligned", keep it not aligned.
            if not base.is_aligned:
                return MedicalNecessityResult(
                    is_aligned=False,
                    rationale=base.rationale,
                    confidence=base.confidence,
                    medical_method="rule_based",
                    flags=list(base.flags),
                )

            flags = list(base.flags)
            if llm_is_aligned:
                confidence = max(base.confidence, llm_conf)
                rationale = base.rationale if not llm_rationale else f"{base.rationale} | LLM: {llm_rationale}"
                return MedicalNecessityResult(
                    is_aligned=True,
                    rationale=rationale,
                    confidence=confidence,
                    medical_method="llm_assisted",
                    flags=flags,
                )

            # Disagreement: deterministic says aligned but LLM says not aligned.
            # Do NOT reject purely based on LLM; instead reduce confidence + flag for caution/manual review.
            flags.append("llm_medical_mismatch")
            confidence = min(base.confidence, max(0.4, llm_conf))
            rationale = base.rationale if not llm_rationale else f"{base.rationale} | LLM flagged potential mismatch: {llm_rationale}"
            return MedicalNecessityResult(
                is_aligned=True,
                rationale=rationale,
                confidence=confidence,
                medical_method="llm_assisted",
                flags=flags,
            )
        except Exception:
            flags = list(base.flags) + ["llm_medical_check_failed_fallback_used"]
            return MedicalNecessityResult(
                is_aligned=base.is_aligned,
                rationale=base.rationale,
                confidence=base.confidence,
                medical_method="rule_based",
                flags=flags,
            )
