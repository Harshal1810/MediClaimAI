from __future__ import annotations

import json
import uuid
from sqlalchemy.orm import Session

from app.models.decision import Decision


class DecisionRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert_decision(self, claim_id: str, result: dict) -> Decision:
        existing = self.db.query(Decision).filter(Decision.claim_id == claim_id).first()
        reasons = result.get("rejection_reasons") or []
        result_json = json.dumps(result, ensure_ascii=False)
        if existing:
            existing.decision = result.get("decision")
            existing.approved_amount = float(result.get("approved_amount") or 0)
            existing.reasons_json = json.dumps(reasons, ensure_ascii=False)
            existing.result_json = result_json
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        row = Decision(
            id=f"DEC_{uuid.uuid4().hex[:10].upper()}",
            claim_id=claim_id,
            decision=result.get("decision"),
            approved_amount=float(result.get("approved_amount") or 0),
            reasons_json=json.dumps(reasons, ensure_ascii=False),
            result_json=result_json,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_claim_id(self, claim_id: str) -> Decision | None:
        return self.db.query(Decision).filter(Decision.claim_id == claim_id).first()
