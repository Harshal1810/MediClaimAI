import uuid
from sqlalchemy.orm import Session
from app.models.document import Document


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_document(self, claim_id: str, filename: str, file_path: str, document_type: str | None = None) -> Document:
        document = Document(
            id=f"DOC_{uuid.uuid4().hex[:10].upper()}",
            claim_id=claim_id,
            filename=filename,
            file_path=file_path,
            document_type=document_type,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def list_by_claim_id(self, claim_id: str) -> list[Document]:
        return self.db.query(Document).filter(Document.claim_id == claim_id).all()

    def set_document_type(self, document_id: str, document_type: str | None) -> Document | None:
        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return None
        doc.document_type = document_type
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc
