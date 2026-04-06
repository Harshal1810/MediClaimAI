from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.adjudication import AdjudicateStoredClaimRequest, AdjudicationRequest, AdjudicationResponse
from app.services.adjudication_service import AdjudicationService

router = APIRouter(tags=["Adjudication"])


@router.post("/adjudicate", response_model=AdjudicationResponse)
def adjudicate(payload: AdjudicationRequest):
    result = AdjudicationService().run(payload.claim_context)
    return AdjudicationResponse(**result)


@router.post("/claims/{claim_id}/adjudicate", response_model=AdjudicationResponse)
def adjudicate_stored_claim(claim_id: str, payload: AdjudicateStoredClaimRequest, db: Session = Depends(get_db)):
    result = AdjudicationService().run_for_claim(
        db=db,
        claim_id=claim_id,
        use_llm=payload.use_llm,
        llm_config=payload.llm_config.model_dump() if payload.llm_config else None,
    )
    return AdjudicationResponse(**result)
