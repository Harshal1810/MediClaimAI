from app.rules.engine import adjudicate_claim
from app.services.policy_loader import PolicyLoader
from app.services.extraction_service import ExtractionService
from app.services.normalization_service import NormalizationService
from app.services.document_classifier import DocumentClassifier
from app.services.medical_necessity_service import MedicalNecessityService
from app.services.runtime_config import RuntimeProcessingConfig
from app.repositories.claim_repository import ClaimRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.extraction_repository import ExtractionRepository
from app.repositories.decision_repository import DecisionRepository
from app.core.logging import logger
from app.services.claim_trace_logger import ClaimTraceLogger
from app.services.retention_service import RetentionService
from app.core.config import settings
from app.llm.provider_factory import LLMProviderFactory
from app.rules.limits import compute_financial_breakdown


class AdjudicationService:
    def run(self, claim_context: dict, *, trace=None):
        policy = PolicyLoader.load_policy()
        derived_rules = PolicyLoader.load_derived_rules()
        return adjudicate_claim(claim_context, policy, derived_rules, trace=trace)

    def process_documents_for_claim(self, db, claim_id: str, runtime: RuntimeProcessingConfig) -> dict:
        claim = ClaimRepository(db).get_claim(claim_id)
        if not claim:
            return {"ok": False, "error": "Claim not found"}

        trace = ClaimTraceLogger(claim_id)
        logger.info(
            "process_documents.start claim_id=%s use_llm=%s provider=%s model=%s",
            claim_id,
            bool(runtime.use_llm),
            runtime.llm_provider if runtime.use_llm else None,
            runtime.llm_model if runtime.use_llm else None,
        )
        trace.log(
            "process_documents.start",
            {
                "use_llm": bool(runtime.use_llm),
                "provider": runtime.llm_provider if runtime.use_llm else None,
                "model": runtime.llm_model if runtime.use_llm else None,
            },
        )

        documents = DocumentRepository(db).list_by_claim_id(claim_id)
        extraction_repo = ExtractionRepository(db)
        extractor = ExtractionService()
        classifier = DocumentClassifier()
        normalizer = NormalizationService()
        medical = MedicalNecessityService()

        # Keep all documents without overwriting by type.
        docs_by_type: dict[str, list[dict]] = {}
        docs_by_id: dict[str, dict] = {}
        ocr_by_doc: dict[str, str] = {}
        extraction_meta_by_doc: dict[str, dict] = {}
        classification_meta_by_doc: dict[str, dict] = {}
        processing_flags: list[str] = []
        processed_docs: list[dict] = []

        for doc in documents:
            doc_type = doc.document_type
            classification_method = "rule_based"
            classification_conf = 0.95

            ocr_text = extractor.ocr_service.extract_text(doc.file_path)
            ocr_blob = trace.write_text_blob(name=f"ocr_{doc.id}", text=ocr_text or "", ext="txt")
            trace.log(
                "ocr.text",
                {
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "document_type_existing": doc_type,
                    "ocr_chars": len((ocr_text or "").strip()),
                    "ocr_blob": ocr_blob,
                },
            )

            if not doc_type:
                cls = classifier.classify(
                    filename=doc.filename,
                    ocr_text=ocr_text,
                    runtime=runtime,
                    trace=trace,
                    trace_meta={
                        "claim_id": claim_id,
                        "document_id": doc.id,
                        "filename": doc.filename,
                        "stage": "classification",
                    },
                )
                doc_type = cls.document_type
                classification_method = cls.classification_method
                classification_conf = float(cls.confidence)
                DocumentRepository(db).set_document_type(doc.id, doc_type if doc_type != "unknown" else None)
                classification_meta_by_doc[doc.id] = {"document_type": doc_type, "classification_method": classification_method, "confidence": classification_conf}
            else:
                classification_meta_by_doc[doc.id] = {"document_type": doc_type, "classification_method": "rule_based", "confidence": 0.95}

            logger.info(
                "process_documents.classified claim_id=%s document_id=%s filename=%s type=%s method=%s conf=%.2f",
                claim_id,
                doc.id,
                doc.filename,
                doc_type,
                classification_method,
                classification_conf,
            )
            trace.log(
                "document.classified",
                {
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "document_type": doc_type,
                    "method": classification_method,
                    "confidence": classification_conf,
                },
            )

            result = extractor.extract_document_data(
                file_path=doc.file_path,
                runtime=runtime,
                document_type_hint=doc_type,
                ocr_text_override=ocr_text,
                trace=trace,
                trace_meta={
                    "claim_id": claim_id,
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "document_type": doc_type,
                    "stage": "extraction",
                },
            )
            extracted_payload = result.get("extracted") or {}
            docs_by_id[doc.id] = {
                "document_id": doc.id,
                "filename": doc.filename,
                "document_type": doc_type,
                "extracted": extracted_payload,
            }
            docs_by_type.setdefault(doc_type, []).append(extracted_payload)
            ocr_by_doc[doc.id] = result.get("ocr_text") or ""
            extraction_meta_by_doc[doc.id] = {
                "document_id": doc.id,
                "document_type": doc_type,
                "extraction_method": result.get("extraction_method"),
                "extraction_confidence": result.get("extraction_confidence"),
                "field_confidences": result.get("field_confidences") or {},
                "missing_fields": result.get("missing_fields") or [],
                "schema_valid": result.get("schema_valid", True),
            }
            if result.get("flags"):
                processing_flags.extend(list(result.get("flags") or []))

            extraction_repo.upsert_extraction(doc.id, result)

            logger.info(
                "process_documents.extracted claim_id=%s document_id=%s type=%s method=%s conf=%.2f missing=%s schema_valid=%s flags=%s ocr_chars=%s",
                claim_id,
                doc.id,
                doc_type,
                result.get("extraction_method") or "rule_based",
                float(result.get("extraction_confidence") or 0.0),
                ",".join(result.get("missing_fields") or []) or "-",
                bool(result.get("schema_valid", True)),
                ",".join(result.get("flags") or []) if result.get("flags") else "-",
                len((result.get("ocr_text") or "").strip()),
            )
            trace.log(
                "document.extracted",
                {
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "document_type": doc_type,
                    "extraction_method": result.get("extraction_method") or "rule_based",
                    "extraction_confidence": float(result.get("extraction_confidence") or 0.0),
                    "missing_fields": result.get("missing_fields") or [],
                    "schema_valid": bool(result.get("schema_valid", True)),
                    "flags": result.get("flags") or [],
                    # Content fields are optionally stripped by ClaimTraceLogger when TRACE_INCLUDE_CONTENT=false.
                    "ocr_excerpt": ((result.get("ocr_text") or "")[:240] or None),
                    "extracted": extracted_payload,
                },
            )

            processed_docs.append(
                {
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "document_type": doc_type,
                    "classification_method": classification_method,
                    "classification_confidence": classification_conf,
                    "extraction_method": result.get("extraction_method") or "rule_based",
                    "extraction_confidence": float(result.get("extraction_confidence") or 0.0),
                    "schema_valid": bool(result.get("schema_valid", True)),
                    "missing_fields": result.get("missing_fields") or [],
                    "extracted": result.get("extracted") or {},
                    "ocr_text_excerpt": (result.get("ocr_text") or "")[:800] or None,
                    "flags": result.get("flags"),
                }
            )

        def _pick_best_doc_id(doc_type: str) -> str | None:
            candidates = [m for m in extraction_meta_by_doc.values() if m.get("document_type") == doc_type]
            if not candidates:
                return None
            candidates = sorted(candidates, key=lambda x: float(x.get("extraction_confidence") or 0.0), reverse=True)
            return str(candidates[0].get("document_id"))

        def _coerce_bill_like(extracted: dict, doc_type: str) -> dict:
            if not isinstance(extracted, dict):
                return {}
            # Map pharmacy bill to bill-like numeric bucket so rules can categorize it.
            if doc_type == "pharmacy_bill":
                total = extracted.get("total")
                if isinstance(total, (int, float)):
                    return {"pharmacy_total": float(total)}
            # Deterministic bill extraction uses bill_total; map to total as well.
            numeric: dict[str, float] = {}
            for k, v in extracted.items():
                if isinstance(v, (int, float)):
                    numeric[str(k)] = float(v)

            # Avoid double-counting: if itemized keys exist, drop "total".
            itemized_keys = {k for k in numeric.keys() if k not in {"total", "bill_total"}}
            if itemized_keys and "total" in numeric:
                numeric.pop("total", None)
            if itemized_keys and "bill_total" in numeric:
                numeric.pop("bill_total", None)

            if not itemized_keys:
                if "bill_total" in extracted and isinstance(extracted.get("bill_total"), (int, float)):
                    numeric["total"] = float(extracted.get("bill_total"))
            return numeric

        # Build primary context for the deterministic rule engine (keeps backward compat with existing rules).
        primary_prescription_id = _pick_best_doc_id("prescription")
        primary_prescription = docs_by_id.get(primary_prescription_id, {}).get("extracted") if primary_prescription_id else None
        primary_prescription = primary_prescription if isinstance(primary_prescription, dict) else {}

        bill_like_docs: list[tuple[str, dict]] = []
        for t in ("bill", "pharmacy_bill"):
            for d in docs_by_type.get(t, []):
                if isinstance(d, dict):
                    bill_like_docs.append((t, d))
        combined_bill: dict[str, float] = {"document_type": "bill"}
        for t, d in bill_like_docs:
            coerced = _coerce_bill_like(d, t)
            for k, v in coerced.items():
                combined_bill[k] = float(combined_bill.get(k) or 0.0) + float(v or 0.0)

        # Preserve bill header metadata (strings) for validation/audit (doesn't affect numeric categorization).
        primary_bill_id = _pick_best_doc_id("bill")
        primary_bill = docs_by_id.get(primary_bill_id, {}).get("extracted") if primary_bill_id else None
        primary_bill = primary_bill if isinstance(primary_bill, dict) else {}
        if primary_bill.get("hospital_name") and isinstance(primary_bill.get("hospital_name"), str):
            combined_bill["hospital_name"] = primary_bill.get("hospital_name")  # type: ignore[assignment]
        if primary_bill.get("date") and isinstance(primary_bill.get("date"), str):
            combined_bill["date"] = primary_bill.get("date")  # type: ignore[assignment]
        if primary_bill.get("patient_name") and isinstance(primary_bill.get("patient_name"), str):
            combined_bill["patient_name"] = primary_bill.get("patient_name")  # type: ignore[assignment]

        # OCR text for validation: primary prescription + merged bill-like text.
        ocr_texts: dict[str, str] = {}
        if primary_prescription_id:
            ocr_texts["prescription"] = ocr_by_doc.get(primary_prescription_id) or ""
        bill_text_parts = []
        for t in ("bill", "pharmacy_bill"):
            for meta in extraction_meta_by_doc.values():
                if meta.get("document_type") == t:
                    did = str(meta.get("document_id"))
                    bill_text_parts.append(ocr_by_doc.get(did) or "")
        ocr_texts["bill"] = "\n\n".join([x for x in bill_text_parts if (x or "").strip()]).strip()

        extraction_meta: dict[str, dict] = {}
        if primary_prescription_id:
            extraction_meta["prescription"] = extraction_meta_by_doc.get(primary_prescription_id) or {}
        classification_meta: dict[str, dict] = {}
        if primary_prescription_id:
            classification_meta["prescription"] = classification_meta_by_doc.get(primary_prescription_id) or {}

        engine_documents = {
            "prescription": primary_prescription,
            "bill": combined_bill,
        }

        normalized = normalizer.normalize_extracted_data(
            [
                {"document_type": meta.get("document_type"), "extracted": docs_by_id.get(str(meta.get("document_id")), {}).get("extracted")}
                for meta in extraction_meta_by_doc.values()
            ]
        )
        medical_result = medical.assess(
            normalized=normalized,
            runtime=runtime,
            trace=trace,
            trace_meta={
                "claim_id": claim_id,
                "stage": "medical_necessity",
            },
        )

        logger.info(
            "process_documents.normalized claim_id=%s diagnosis=%s tests=%s medicines=%s",
            claim_id,
            (normalized.get("diagnosis") if isinstance(normalized, dict) else None),
            len((normalized.get("tests") or []) if isinstance(normalized, dict) else []),
            len((normalized.get("medicines") or []) if isinstance(normalized, dict) else []),
        )
        logger.info(
            "process_documents.medical claim_id=%s method=%s aligned=%s conf=%.2f flags=%s",
            claim_id,
            medical_result.medical_method,
            bool(medical_result.is_aligned),
            float(medical_result.confidence or 0.0),
            ",".join(medical_result.flags or []) or "-",
        )
        trace.log(
            "medical.assessed",
            {
                "method": medical_result.medical_method,
                "is_aligned": bool(medical_result.is_aligned),
                "confidence": float(medical_result.confidence or 0.0),
                "flags": medical_result.flags or [],
            },
        )

        claim_context = {
            "claim": {
                "claim_id": claim.id,
                "session_id": claim.session_id,
                "member_id": claim.member_id,
                "member_name": claim.member_name,
                "treatment_date": claim.treatment_date,
                "submission_date": claim.submission_date,
                "claim_amount": claim.claim_amount,
                "hospital": claim.hospital_name,
                "cashless_request": claim.cashless_requested,
            },
            "documents": engine_documents,
            "documents_by_type": docs_by_type,
            "documents_by_id": docs_by_id,
            "document_types": sorted(set([str(k) for k in docs_by_type.keys()])),
            "ocr_texts": ocr_texts,
            "ocr_texts_by_doc": ocr_by_doc,
            "extraction_meta": extraction_meta,
            "extraction_meta_by_doc": extraction_meta_by_doc,
            "classification_meta": classification_meta,
            "classification_meta_by_doc": classification_meta_by_doc,
            "normalized": normalized,
            "medical": {
                "is_aligned": medical_result.is_aligned,
                "rationale": medical_result.rationale,
                "confidence": medical_result.confidence,
                "medical_method": medical_result.medical_method,
                "flags": medical_result.flags,
            },
            "processing": {
                "use_llm": runtime.use_llm,
                "llm_provider": runtime.llm_provider if runtime.use_llm else None,
                "llm_model": runtime.llm_model if runtime.use_llm else None,
                "classification_method": "llm" if any((v.get("classification_method") == "llm") for v in classification_meta_by_doc.values()) else "rule_based",
                "extraction_method": "llm" if any((v.get("extraction_method") == "llm") for v in extraction_meta_by_doc.values()) else "rule_based",
                "medical_method": medical_result.medical_method,
                "flags": sorted(set(processing_flags + medical_result.flags)),
            },
        }

        # Deterministic breakdown used for debugging and optional LLM final cross-check.
        try:
            policy = PolicyLoader.load_policy()
            derived_rules = PolicyLoader.load_derived_rules()
            claim_context["financial_breakdown"] = compute_financial_breakdown(claim_context, policy, derived_rules)
            trace.log("financial.breakdown_snapshot", claim_context["financial_breakdown"])
        except Exception:
            claim_context["financial_breakdown"] = None

        logger.info(
            "process_documents.done claim_id=%s doc_types=%s flags=%s",
            claim_id,
            ",".join(sorted(set(docs_by_type.keys()))) if docs_by_type else "-",
            ",".join(sorted(set(processing_flags + medical_result.flags))) if (processing_flags or medical_result.flags) else "-",
        )
        trace.log(
            "process_documents.done",
            {
                "doc_types": sorted(set(docs_by_type.keys())),
                "flags": sorted(set(processing_flags + (medical_result.flags or []))),
            },
        )
        return {"ok": True, "claim_context": claim_context, "processed_docs": processed_docs}

    def run_for_claim(self, db, claim_id: str, use_llm: bool, llm_config: dict | None) -> dict:
        claim = ClaimRepository(db).get_claim(claim_id)
        if not claim:
            return {"decision": "REJECTED", "approved_amount": 0, "rejection_reasons": ["INVALID_CLAIM"], "confidence_score": 1.0, "notes": "Claim not found"}

        runtime = RuntimeProcessingConfig(
            use_llm=bool(use_llm),
            llm_provider=(llm_config or {}).get("provider"),
            llm_model=(llm_config or {}).get("model"),
            llm_api_key=(llm_config or {}).get("api_key"),
        )

        logger.info(
            "adjudication.start claim_id=%s use_llm=%s provider=%s model=%s",
            claim_id,
            bool(runtime.use_llm),
            runtime.llm_provider if runtime.use_llm else None,
            runtime.llm_model if runtime.use_llm else None,
        )
        trace = ClaimTraceLogger(claim_id)
        trace.log(
            "adjudication.start",
            {
                "use_llm": bool(runtime.use_llm),
                "provider": runtime.llm_provider if runtime.use_llm else None,
                "model": runtime.llm_model if runtime.use_llm else None,
            },
        )

        processed = self.process_documents_for_claim(db=db, claim_id=claim_id, runtime=runtime)
        if not processed.get("ok"):
            return {"decision": "REJECTED", "approved_amount": 0, "rejection_reasons": ["INVALID_CLAIM"], "confidence_score": 1.0, "notes": processed.get("error") or "Processing failed"}
        claim_context = processed["claim_context"]

        result = self.run(claim_context, trace=trace)

        if runtime.use_llm:
            try:
                provider = LLMProviderFactory.create(
                    provider=runtime.llm_provider or "",
                    api_key=runtime.llm_api_key or "",
                    model=runtime.llm_model or "",
                    trace=trace,
                    trace_meta={"claim_id": claim_id, "stage": "final_review"},
                )
                review = provider.review_final_decision(claim_context=claim_context, deterministic_result=result)
                agrees = (
                    str(review.get("recommended_decision")) == str(result.get("decision"))
                    and abs(float(review.get("recommended_approved_amount") or 0.0) - float(result.get("approved_amount") or 0.0)) < 0.01
                )
                result["llm_final_review"] = {**review, "agrees_with_deterministic": agrees}
            except Exception:
                result["llm_final_review"] = {"error": "llm_final_review_failed"}
        logger.info(
            "adjudication.done claim_id=%s decision=%s approved_amount=%s confidence=%.2f action=%s rejection_reasons=%s",
            claim_id,
            result.get("decision"),
            result.get("approved_amount"),
            float(result.get("confidence_score") or 0.0),
            result.get("confidence_action"),
            ",".join(result.get("rejection_reasons") or []) or "-",
        )
        trace.log(
            "adjudication.done",
            {
                "decision": result.get("decision"),
                "approved_amount": result.get("approved_amount"),
                "rejection_reasons": result.get("rejection_reasons") or [],
                "confidence_score": float(result.get("confidence_score") or 0.0),
                "confidence_action": result.get("confidence_action"),
                "flags": result.get("flags") or [],
                "confidence_flags": result.get("confidence_flags") or [],
            },
        )
        # Attach processing metadata to response without exposing api keys.
        processing = claim_context["processing"]
        existing_flags = list(result.get("flags") or [])
        processing_flags_out = list(processing.get("flags") or [])
        merged_flags = sorted(set(existing_flags + processing_flags_out)) if (existing_flags or processing_flags_out) else None
        for k, v in processing.items():
            if k == "flags":
                continue
            result[k] = v
        if merged_flags is not None:
            result["flags"] = merged_flags
        DecisionRepository(db).upsert_decision(claim_id, result)

        if settings.DELETE_UPLOADS_AFTER_ADJUDICATION:
            try:
                deleted = RetentionService().delete_uploads_for_claim(claim_id)
                if deleted:
                    logger.info("uploads.deleted claim_id=%s files=%s", claim_id, deleted)
                    trace.log("uploads.deleted", {"files": deleted})
            except Exception:
                # Never block response if cleanup fails.
                pass
        return result
