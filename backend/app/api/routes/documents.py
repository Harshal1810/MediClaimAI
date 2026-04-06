from fastapi import APIRouter, Depends, File, UploadFile, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.document import DocumentUploadResponse
from app.schemas.processing import ProcessDocumentsRequest, ProcessDocumentsResponse, ProcessedDocument
from app.services.document_service import DocumentService
from app.services.adjudication_service import AdjudicationService
from app.services.runtime_config import RuntimeProcessingConfig
from app.core.logging import logger

router = APIRouter(tags=["Documents"])


@router.post("/claims/{claim_id}/documents", response_model=DocumentUploadResponse)
def upload_document(
    claim_id: str,
    file: UploadFile = File(...),
    document_type: str | None = Query(default=None, description="e.g. prescription, bill, report"),
    db: Session = Depends(get_db),
):
    document = DocumentService(db).save_document(claim_id, file, document_type=document_type)
    logger.info(
        "document.uploaded claim_id=%s document_id=%s filename=%s type=%s",
        claim_id,
        document.id,
        document.filename,
        document.document_type,
    )
    return DocumentUploadResponse(document_id=document.id, filename=document.filename, status="uploaded")


@router.post("/claims/{claim_id}/process-documents", response_model=ProcessDocumentsResponse)
def process_documents(claim_id: str, payload: ProcessDocumentsRequest, db: Session = Depends(get_db)):
    runtime = RuntimeProcessingConfig(
        use_llm=payload.use_llm,
        llm_provider=payload.llm_config.provider if payload.llm_config else None,
        llm_model=payload.llm_config.model if payload.llm_config else None,
        llm_api_key=payload.llm_config.api_key if payload.llm_config else None,
    )
    processed = AdjudicationService().process_documents_for_claim(db=db, claim_id=claim_id, runtime=runtime)
    if not processed.get("ok"):
        logger.warning("process_documents.failed claim_id=%s error=%s", claim_id, processed.get("error"))
        return ProcessDocumentsResponse(
            claim_id=claim_id,
            use_llm=payload.use_llm,
            llm_provider=runtime.llm_provider if runtime.use_llm else None,
            llm_model=runtime.llm_model if runtime.use_llm else None,
            documents=[],
            normalized=None,
            medical=None,
            flags=[processed.get("error") or "processing_failed"],
        )

    ctx = processed["claim_context"]
    docs = [ProcessedDocument(**d) for d in processed["processed_docs"]]
    logger.info("process_documents.response claim_id=%s documents=%s", claim_id, len(docs))
    return ProcessDocumentsResponse(
        claim_id=claim_id,
        use_llm=payload.use_llm,
        llm_provider=runtime.llm_provider if runtime.use_llm else None,
        llm_model=runtime.llm_model if runtime.use_llm else None,
        documents=docs,
        normalized=ctx.get("normalized"),
        medical=ctx.get("medical"),
        flags=ctx.get("processing", {}).get("flags"),
    )
