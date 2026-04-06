from sqlalchemy.orm import Session
from app.repositories.claim_repository import ClaimRepository
from app.schemas.claim import ClaimCreateRequest


class ClaimService:
    def __init__(self, db: Session):
        self.repo = ClaimRepository(db)

    def create_claim(self, payload: ClaimCreateRequest):
        return self.repo.create_claim(payload)
