import os
from pathlib import Path
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.repositories.document_repository import DocumentRepository


_BACKEND_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = _BACKEND_ROOT / "uploads"


class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DocumentRepository(db)
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    def save_document(self, claim_id: str, file: UploadFile, document_type: str | None = None):
        # Store files under a stable absolute directory (independent of server CWD).
        safe_name = os.path.basename(file.filename or "document")
        file_path = UPLOAD_DIR / f"{claim_id}_{safe_name}"
        with open(file_path, "wb") as f:
            f.write(file.file.read())
        return self.repo.create_document(claim_id, safe_name, str(file_path), document_type=document_type)
