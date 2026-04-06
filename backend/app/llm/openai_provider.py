import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.base import BaseLLMProvider
from app.llm.prompts.classify_document import CLASSIFY_DOCUMENT_SYSTEM, classify_document_user_prompt
from app.llm.prompts.extract_document import EXTRACT_DOCUMENT_SYSTEM, extract_document_user_prompt
from app.llm.prompts.medical_necessity import MEDICAL_NECESSITY_SYSTEM, medical_necessity_user_prompt
from app.llm.prompts.final_review import FINAL_REVIEW_SYSTEM, final_review_user_prompt
from app.llm.schemas import (
    BillExtraction,
    DocumentTypeClassification,
    FinalDecisionReview,
    MedicalNecessityAssessment,
    PharmacyBillExtraction,
    PrescriptionExtraction,
    ReportExtraction,
    UnknownExtraction,
)
from app.llm.structured_output import langchain_complete_json


class OpenAIProvider(BaseLLMProvider):
    def _client(self) -> ChatOpenAI:
        return ChatOpenAI(api_key=self.api_key, model=self.model, temperature=0)

    def _trace_llm(self, *, task: str, messages: list, response_model, parsed, raw: str) -> None:
        trace = getattr(self, "trace", None)
        if not trace:
            return
        try:
            prompt_payload = []
            for m in messages:
                role = getattr(m, "type", None) or m.__class__.__name__
                content = getattr(m, "content", None)
                prompt_payload.append({"role": role, "content": content})
            prompt_blob = trace.write_text_blob(name=f"{task}_prompt", text=json.dumps(prompt_payload, ensure_ascii=False, indent=2), ext="json") if hasattr(trace, "write_text_blob") else None
            raw_blob = trace.write_text_blob(name=f"{task}_raw", text=raw or "", ext="txt") if hasattr(trace, "write_text_blob") else None
            trace.log(
                "llm.call",
                {
                    "provider": "openai",
                    "model": self.model,
                    "task": task,
                    "response_model": getattr(response_model, "__name__", str(response_model)),
                    "prompt_blob": prompt_blob,
                    "raw_blob": raw_blob,
                    "parsed": parsed.model_dump() if hasattr(parsed, "model_dump") else parsed,
                    **(getattr(self, "trace_meta", {}) or {}),
                },
            )
        except Exception:
            return

    def extract_structured_document(self, ocr_text: str, document_type_hint: str | None = None):
        doc_type = (document_type_hint or "unknown").lower()
        model_map = {
            "prescription": PrescriptionExtraction,
            "bill": BillExtraction,
            "report": ReportExtraction,
            "pharmacy_bill": PharmacyBillExtraction,
            "unknown": UnknownExtraction,
        }
        response_model = model_map.get(doc_type, UnknownExtraction)
        chat = self._client()
        messages = [
            SystemMessage(content=EXTRACT_DOCUMENT_SYSTEM),
            HumanMessage(content=extract_document_user_prompt(document_type_hint=doc_type, ocr_text=ocr_text)),
        ]
        parsed, raw = langchain_complete_json(chat_model=chat, messages=messages, response_model=response_model)
        self._trace_llm(task="extract_document", messages=messages, response_model=response_model, parsed=parsed, raw=raw)
        return parsed.model_dump()

    def assess_medical_necessity(self, normalized_context: dict):
        chat = self._client()
        messages = [
            SystemMessage(content=MEDICAL_NECESSITY_SYSTEM),
            HumanMessage(content=medical_necessity_user_prompt(normalized_context=normalized_context)),
        ]
        parsed, raw = langchain_complete_json(chat_model=chat, messages=messages, response_model=MedicalNecessityAssessment)
        self._trace_llm(task="medical_necessity", messages=messages, response_model=MedicalNecessityAssessment, parsed=parsed, raw=raw)
        return parsed.model_dump()

    def classify_document_type(self, ocr_text: str, filename: str | None = None) -> str:
        chat = self._client()
        messages = [
            SystemMessage(content=CLASSIFY_DOCUMENT_SYSTEM),
            HumanMessage(content=classify_document_user_prompt(filename=filename, ocr_text=ocr_text)),
        ]
        parsed, raw = langchain_complete_json(chat_model=chat, messages=messages, response_model=DocumentTypeClassification)
        self._trace_llm(task="classify_document", messages=messages, response_model=DocumentTypeClassification, parsed=parsed, raw=raw)
        return parsed.document_type

    def review_final_decision(self, *, claim_context: dict, deterministic_result: dict) -> dict:
        chat = self._client()
        messages = [
            SystemMessage(content=FINAL_REVIEW_SYSTEM),
            HumanMessage(
                content=final_review_user_prompt(
                    claim_context=claim_context,
                    deterministic_result=deterministic_result,
                    financial_breakdown=claim_context.get("financial_breakdown"),
                )
            ),
        ]
        parsed, raw = langchain_complete_json(chat_model=chat, messages=messages, response_model=FinalDecisionReview)
        self._trace_llm(task="final_review", messages=messages, response_model=FinalDecisionReview, parsed=parsed, raw=raw)
        return parsed.model_dump()
