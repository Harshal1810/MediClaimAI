from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


@dataclass
class StageScore:
    score: float
    components: dict[str, float] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["score"] = round(_clamp(self.score), 4)
        payload["components"] = {k: round(_clamp(v), 4) for k, v in self.components.items()}
        return payload


@dataclass
class ConfidenceBreakdown:
    ocr: StageScore
    extraction: StageScore
    consistency: StageScore
    rules: StageScore
    medical: StageScore
    final_score: float
    action: str
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ocr": self.ocr.to_dict(),
            "extraction": self.extraction.to_dict(),
            "consistency": self.consistency.to_dict(),
            "rules": self.rules.to_dict(),
            "medical": self.medical.to_dict(),
            "final_score": round(_clamp(self.final_score), 4),
            "action": self.action,
            "flags": self.flags,
            "notes": self.notes,
        }


class ConfidenceService:
    """
    Hybrid confidence scoring service.

    Final weighted formula:
        0.20 * OCR
      + 0.25 * Extraction
      + 0.20 * Cross-document consistency
      + 0.20 * Rule certainty
      + 0.15 * Medical necessity certainty

    Suggested actions:
      >= 0.85 -> AUTO
      0.70-0.84 -> AUTO_WITH_CAUTION
      < 0.70 -> MANUAL_REVIEW

    Hard overrides:
      - fraud/manual-review flags
      - critical patient mismatch
      - critical missing fields
    """

    FINAL_WEIGHTS = {
        "ocr": 0.20,
        "extraction": 0.25,
        "consistency": 0.20,
        "rules": 0.20,
        "medical": 0.15,
    }

    def compute_ocr_quality(
        self,
        *,
        avg_ocr_confidence: float | None,
        extracted_text: str,
        expected_min_chars: int = 100,
        image_quality_score: float | None = None,
    ) -> StageScore:
        text = (extracted_text or "").strip()

        engine_confidence = _clamp(avg_ocr_confidence if avg_ocr_confidence is not None else 0.65)
        text_coverage = _clamp(len(text) / max(expected_min_chars, 1))

        allowed_chars = set(".,:/-%()#&+")
        total_chars = max(len(text), 1)
        noisy_chars = sum(1 for c in text if not (c.isalnum() or c.isspace() or c in allowed_chars))
        noise_ratio = _safe_div(noisy_chars, total_chars)
        noise_score = _clamp(1 - noise_ratio)

        tokens = [t for t in text.split() if t.strip()]
        valid_tokens = 0
        for token in tokens:
            cleaned = token.strip(".,:/-%()")
            if any(ch.isdigit() for ch in cleaned) or len(cleaned) >= 3:
                valid_tokens += 1
        valid_token_ratio = _clamp(_safe_div(valid_tokens, max(len(tokens), 1)))

        img_score = _clamp(image_quality_score if image_quality_score is not None else 0.70)

        score = (
            0.40 * engine_confidence
            + 0.20 * text_coverage
            + 0.20 * noise_score
            + 0.10 * valid_token_ratio
            + 0.10 * img_score
        )

        flags: list[str] = []
        notes: list[str] = []

        if text_coverage < 0.5:
            flags.append("low_text_coverage")
            notes.append("OCR extracted less text than expected for this document type.")
        if noise_score < 0.6:
            flags.append("high_ocr_noise")
            notes.append("OCR text contains substantial noise or unreadable characters.")
        if engine_confidence < 0.6:
            flags.append("low_ocr_engine_confidence")
            notes.append("OCR engine returned low confidence.")

        return StageScore(
            score=_clamp(score),
            components={
                "engine_confidence": engine_confidence,
                "text_coverage": text_coverage,
                "noise_score": noise_score,
                "valid_token_ratio": valid_token_ratio,
                "image_quality_score": img_score,
            },
            flags=flags,
            notes=notes,
        )

    def compute_extraction_quality(
        self,
        *,
        field_confidences: dict[str, float],
        required_fields: list[str],
        extracted_payload: dict[str, Any],
        schema_valid: bool = True,
        normalization_success: float = 1.0,
        evidence_alignment: float = 0.9,
    ) -> StageScore:
        normalized_fields = {key: _clamp(value) for key, value in (field_confidences or {}).items()}

        avg_field_confidence = _clamp(_safe_div(sum(normalized_fields.values()), max(len(normalized_fields), 1)))

        required_present = 0
        missing_required: list[str] = []
        for field_name in required_fields:
            value = extracted_payload.get(field_name)
            if value not in (None, "", [], {}):
                required_present += 1
            else:
                missing_required.append(field_name)

        completeness = _clamp(_safe_div(required_present, max(len(required_fields), 1)))
        schema_validity = 1.0 if schema_valid else 0.4
        normalization_success = _clamp(normalization_success)
        evidence_alignment = _clamp(evidence_alignment)

        score = (
            0.45 * avg_field_confidence
            + 0.25 * completeness
            + 0.15 * schema_validity
            + 0.10 * normalization_success
            + 0.05 * evidence_alignment
        )

        flags: list[str] = []
        notes: list[str] = []

        if missing_required:
            flags.append("missing_required_fields")
            notes.append(f"Missing required extracted fields: {', '.join(missing_required)}")
        if avg_field_confidence < 0.7:
            flags.append("low_field_confidence")
            notes.append("Several extracted fields have low confidence.")
        if not schema_valid:
            flags.append("schema_validation_failed")
            notes.append("Extracted payload did not fully match expected schema.")
        if evidence_alignment < 0.7:
            flags.append("weak_evidence_alignment")
            notes.append("Some extracted fields are weakly grounded in OCR text.")

        return StageScore(
            score=_clamp(score),
            components={
                "avg_field_confidence": avg_field_confidence,
                "completeness": completeness,
                "schema_validity": schema_validity,
                "normalization_success": normalization_success,
                "evidence_alignment": evidence_alignment,
            },
            flags=flags,
            notes=notes,
        )

    def compute_cross_document_consistency(
        self,
        *,
        patient_match_score: float,
        date_consistency_score: float,
        diagnosis_treatment_alignment: float,
        prescription_bill_overlap: float,
        amount_consistency_score: float,
    ) -> StageScore:
        patient_match_score = _clamp(patient_match_score)
        date_consistency_score = _clamp(date_consistency_score)
        diagnosis_treatment_alignment = _clamp(diagnosis_treatment_alignment)
        prescription_bill_overlap = _clamp(prescription_bill_overlap)
        amount_consistency_score = _clamp(amount_consistency_score)

        score = (
            0.30 * patient_match_score
            + 0.20 * date_consistency_score
            + 0.25 * diagnosis_treatment_alignment
            + 0.15 * prescription_bill_overlap
            + 0.10 * amount_consistency_score
        )

        flags: list[str] = []
        notes: list[str] = []

        if patient_match_score < 0.4:
            score *= 0.5
            flags.append("critical_patient_mismatch")
            notes.append("Patient identity mismatch across documents.")
        elif patient_match_score < 0.75:
            flags.append("weak_patient_match")
            notes.append("Patient identity match is weaker than expected.")

        if date_consistency_score < 0.6:
            flags.append("date_inconsistency")
            notes.append("Dates across claim documents are inconsistent.")
        if diagnosis_treatment_alignment < 0.6:
            flags.append("diagnosis_treatment_mismatch")
            notes.append("Diagnosis does not strongly support billed treatment/tests.")
        if prescription_bill_overlap < 0.5:
            flags.append("low_prescription_bill_overlap")
            notes.append("Many billed items are not supported by prescription/report.")
        if amount_consistency_score < 0.7:
            flags.append("amount_inconsistency")
            notes.append("Bill totals and line-item sums do not align cleanly.")

        return StageScore(
            score=_clamp(score),
            components={
                "patient_match_score": patient_match_score,
                "date_consistency_score": date_consistency_score,
                "diagnosis_treatment_alignment": diagnosis_treatment_alignment,
                "prescription_bill_overlap": prescription_bill_overlap,
                "amount_consistency_score": amount_consistency_score,
            },
            flags=flags,
            notes=notes,
        )

    def compute_rule_certainty(
        self,
        *,
        decision_path_determinism: float,
        category_mapping_confidence: float,
        policy_match_confidence: float,
        conflict_penalty: float,
    ) -> StageScore:
        decision_path_determinism = _clamp(decision_path_determinism)
        category_mapping_confidence = _clamp(category_mapping_confidence)
        policy_match_confidence = _clamp(policy_match_confidence)
        conflict_penalty = _clamp(conflict_penalty)

        score = (
            0.40 * decision_path_determinism
            + 0.25 * category_mapping_confidence
            + 0.20 * policy_match_confidence
            + 0.15 * (1 - conflict_penalty)
        )

        flags: list[str] = []
        notes: list[str] = []

        if decision_path_determinism < 0.75:
            flags.append("non_deterministic_decision_path")
            notes.append("Decision required judgment-heavy interpretation.")
        if category_mapping_confidence < 0.7:
            flags.append("ambiguous_category_mapping")
            notes.append("One or more services were mapped to policy categories ambiguously.")
        if policy_match_confidence < 0.75:
            flags.append("weak_policy_match")
            notes.append("Decision does not map strongly to explicit policy configuration.")
        if conflict_penalty > 0.35:
            flags.append("rule_conflicts_present")
            notes.append("Multiple rules or signals pulled in different directions.")

        return StageScore(
            score=_clamp(score),
            components={
                "decision_path_determinism": decision_path_determinism,
                "category_mapping_confidence": category_mapping_confidence,
                "policy_match_confidence": policy_match_confidence,
                "conflict_adjusted_score": 1 - conflict_penalty,
            },
            flags=flags,
            notes=notes,
        )

    def compute_medical_necessity_certainty(
        self,
        *,
        diagnosis_present_score: float,
        diagnosis_service_compatibility: float,
        prescription_support_score: float,
        llm_alignment_confidence: float,
        exclusion_penalty: float,
    ) -> StageScore:
        diagnosis_present_score = _clamp(diagnosis_present_score)
        diagnosis_service_compatibility = _clamp(diagnosis_service_compatibility)
        prescription_support_score = _clamp(prescription_support_score)
        llm_alignment_confidence = _clamp(llm_alignment_confidence)
        exclusion_penalty = _clamp(exclusion_penalty)

        exclusion_adjusted_score = 1 - exclusion_penalty

        score = (
            0.20 * diagnosis_present_score
            + 0.30 * diagnosis_service_compatibility
            + 0.20 * prescription_support_score
            + 0.20 * llm_alignment_confidence
            + 0.10 * exclusion_adjusted_score
        )

        flags: list[str] = []
        notes: list[str] = []

        if diagnosis_present_score < 0.5:
            flags.append("diagnosis_missing_or_weak")
            notes.append("Diagnosis is missing or weakly evidenced.")
        if diagnosis_service_compatibility < 0.6:
            flags.append("low_medical_compatibility")
            notes.append("Diagnosis does not strongly justify billed services.")
        if prescription_support_score < 0.6:
            flags.append("weak_prescription_support")
            notes.append("Prescription support for billed items is limited.")
        if llm_alignment_confidence < 0.65:
            flags.append("low_llm_necessity_confidence")
            notes.append("LLM was not strongly confident in medical necessity alignment.")
        if exclusion_penalty > 0.4:
            flags.append("possible_exclusion_or_cosmetic_signal")
            notes.append("Claim contains exclusion, wellness, or cosmetic indicators.")

        return StageScore(
            score=_clamp(score),
            components={
                "diagnosis_present_score": diagnosis_present_score,
                "diagnosis_service_compatibility": diagnosis_service_compatibility,
                "prescription_support_score": prescription_support_score,
                "llm_alignment_confidence": llm_alignment_confidence,
                "exclusion_adjusted_score": exclusion_adjusted_score,
            },
            flags=flags,
            notes=notes,
        )

    def aggregate(
        self,
        *,
        ocr: StageScore,
        extraction: StageScore,
        consistency: StageScore,
        rules: StageScore,
        medical: StageScore,
        manual_review_flags: list[str] | None = None,
        critical_missing_fields: list[str] | None = None,
    ) -> ConfidenceBreakdown:
        manual_review_flags = manual_review_flags or []
        critical_missing_fields = critical_missing_fields or []

        final_score = (
            self.FINAL_WEIGHTS["ocr"] * ocr.score
            + self.FINAL_WEIGHTS["extraction"] * extraction.score
            + self.FINAL_WEIGHTS["consistency"] * consistency.score
            + self.FINAL_WEIGHTS["rules"] * rules.score
            + self.FINAL_WEIGHTS["medical"] * medical.score
        )

        flags: list[str] = []
        notes: list[str] = []

        flags.extend(ocr.flags)
        flags.extend(extraction.flags)
        flags.extend(consistency.flags)
        flags.extend(rules.flags)
        flags.extend(medical.flags)
        flags.extend(manual_review_flags)

        notes.extend(ocr.notes)
        notes.extend(extraction.notes)
        notes.extend(consistency.notes)
        notes.extend(rules.notes)
        notes.extend(medical.notes)

        if critical_missing_fields:
            final_score *= 0.75
            flags.append("critical_missing_fields")
            notes.append(f"Critical fields missing: {', '.join(critical_missing_fields)}")

        if "critical_patient_mismatch" in flags:
            final_score = min(final_score, 0.64)

        if manual_review_flags:
            final_score = min(final_score, 0.69)

        final_score = _clamp(final_score)

        if manual_review_flags or final_score < 0.70:
            action = "MANUAL_REVIEW"
        elif final_score < 0.85:
            action = "AUTO_WITH_CAUTION"
        else:
            action = "AUTO"

        return ConfidenceBreakdown(
            ocr=ocr,
            extraction=extraction,
            consistency=consistency,
            rules=rules,
            medical=medical,
            final_score=final_score,
            action=action,
            flags=sorted(set(flags)),
            notes=notes,
        )

