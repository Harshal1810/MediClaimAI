from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.claim import ClaimCreateRequest, ClaimCreateResponse
from app.services.claim_service import ClaimService
from app.repositories.decision_repository import DecisionRepository
from app.core.logging import logger
import json

router = APIRouter(tags=["Claims"])


@router.post("/claims", response_model=ClaimCreateResponse)
def create_claim(payload: ClaimCreateRequest, db: Session = Depends(get_db)):
    claim = ClaimService(db).create_claim(payload)
    logger.info(
        "claim.created claim_id=%s session_id=%s member_id=%s treatment_date=%s submission_date=%s amount=%s",
        claim.id,
        claim.session_id,
        claim.member_id,
        claim.treatment_date,
        claim.submission_date,
        claim.claim_amount,
    )
    return ClaimCreateResponse(claim_id=claim.id, status=claim.status)


@router.get("/claims/{claim_id}/decision")
def get_claim_decision(claim_id: str, db: Session = Depends(get_db)):
    decision = DecisionRepository(db).get_by_claim_id(claim_id)
    if not decision or not decision.result_json:
        return {"found": False, "decision": None}
    return {"found": True, "decision": json.loads(decision.result_json)}
