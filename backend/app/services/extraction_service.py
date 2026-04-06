from app.services.ocr_service import OCRService
from app.services.deterministic_extraction import ExtractionEnvelope, extract_structured_by_type
from app.services.runtime_config import RuntimeProcessingConfig
from app.llm.provider_factory import LLMProviderFactory


class ExtractionService:
    def __init__(self):
        self.ocr_service = OCRService()

    def extract_document_data(
        self,
        file_path: str,
        runtime: RuntimeProcessingConfig,
        document_type_hint: str | None = None,
        *,
        ocr_text_override: str | None = None,
        trace=None,
        trace_meta: dict | None = None,
    ) -> dict:
        text = ocr_text_override if ocr_text_override is not None else self.ocr_service.extract_text(file_path)
        doc_type = document_type_hint or "unknown"
        if not (text or "").strip():
            env = extract_structured_by_type(ocr_text=text, document_type=doc_type)
            payload = env.to_dict()
            payload["flags"] = ["empty_ocr_text"]
            return payload

        if not runtime.use_llm:
            env = extract_structured_by_type(ocr_text=text, document_type=doc_type)
            return env.to_dict()

        # LLM-assisted extraction with deterministic fallback.
        try:
            provider = LLMProviderFactory.create(
                provider=runtime.llm_provider or "",
                api_key=runtime.llm_api_key or "",
                model=runtime.llm_model or "",
                trace=trace,
                trace_meta=trace_meta,
            )
            extracted = provider.extract_structured_document(ocr_text=text, document_type_hint=doc_type)
            flags: list[str] = []
            if isinstance(extracted, dict):
                # Compute missing fields and never allow "0.99 confidence" when key fields are null.
                base_conf = float(extracted.get("confidence") or 0.75)
                field_confidences = extracted.get("field_confidences") or {}
                schema_valid = True

                if doc_type == "prescription":
                    required = ["doctor_reg", "diagnosis", "patient_name"]
                elif doc_type in ("bill", "pharmacy_bill"):
                    required = ["total"]
                else:
                    required = []

                missing_fields = [f for f in required if extracted.get(f) in (None, "", [], {})]

                # Fill missing key fields using deterministic heuristics (even if LLM call "succeeded").
                deterministic = extract_structured_by_type(ocr_text=text, document_type=doc_type).to_dict().get("extracted") or {}
                filled = []
                for f in list(missing_fields):
                    if deterministic.get(f) not in (None, "", [], {}):
                        extracted[f] = deterministic.get(f)
                        filled.append(f)
                if filled:
                    flags.append("llm_missing_fields_filled_by_rules:" + ",".join(sorted(set(filled))))
                    missing_fields = [f for f in required if extracted.get(f) in (None, "", [], {})]

                # Build field_confidences if provider didn't supply them.
                if not isinstance(field_confidences, dict):
                    field_confidences = {}
                for f in required:
                    if f in field_confidences:
                        continue
                    present = extracted.get(f) not in (None, "", [], {})
                    # If we filled it from deterministic extraction, it's still decent but not "perfect".
                    if filled and f in filled:
                        field_confidences[f] = 0.85
                    else:
                        field_confidences[f] = 0.92 if present else 0.35

                completeness = 1.0
                if required:
                    completeness = 1.0 - (len(missing_fields) / max(len(required), 1))

                # Penalize base confidence when key fields are missing.
                confidence_cap = 0.55 + 0.45 * max(0.0, completeness)
                confidence = max(0.05, min(base_conf, confidence_cap))
                if missing_fields:
                    flags.append("llm_missing_required_fields:" + ",".join(missing_fields))
            else:
                confidence = 0.7
                field_confidences = {}
                schema_valid = False
                missing_fields = []
            env = ExtractionEnvelope(
                ocr_text=text,
                extracted=extracted if isinstance(extracted, dict) else {"raw": extracted},
                extraction_method="llm",
                extraction_confidence=confidence,
                field_confidences=field_confidences,
                missing_fields=missing_fields,
                schema_valid=schema_valid,
            )
            payload = env.to_dict()
            if flags:
                payload["flags"] = flags
            return payload
        except Exception:
            env = extract_structured_by_type(ocr_text=text, document_type=doc_type)
            payload = env.to_dict()
            payload["flags"] = ["llm_extraction_failed_fallback_used"]
            return payload
