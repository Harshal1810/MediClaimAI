import uuid
from sqlalchemy.orm import Session
from app.models.claim import Claim
from app.schemas.claim import ClaimCreateRequest


class ClaimRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_claim(self, payload: ClaimCreateRequest) -> Claim:
        claim = Claim(
            id=f"CLM_{uuid.uuid4().hex[:10].upper()}",
            session_id=payload.session_id,
            member_id=payload.member_id,
            member_name=payload.member_name,
            treatment_date=payload.treatment_date,
            submission_date=payload.submission_date,
            claim_amount=payload.claim_amount,
            hospital_name=payload.hospital_name,
            cashless_requested=payload.cashless_requested,
            status="CREATED",
        )
        self.db.add(claim)
        self.db.commit()
        self.db.refresh(claim)
        return claim

    def get_claim(self, claim_id: str) -> Claim | None:
        return self.db.query(Claim).filter(Claim.id == claim_id).first()
