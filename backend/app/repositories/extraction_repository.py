from __future__ import annotations

import json
import uuid
from sqlalchemy.orm import Session

from app.models.extraction import Extraction


class ExtractionRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert_extraction(self, document_id: str, extracted: dict) -> Extraction:
        existing = self.db.query(Extraction).filter(Extraction.document_id == document_id).first()
        if existing:
            existing.extracted_json = json.dumps(extracted, ensure_ascii=False)
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        row = Extraction(
            id=f"EXT_{uuid.uuid4().hex[:10].upper()}",
            document_id=document_id,
            extracted_json=json.dumps(extracted, ensure_ascii=False),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_document_id(self, document_id: str) -> Extraction | None:
        return self.db.query(Extraction).filter(Extraction.document_id == document_id).first()
