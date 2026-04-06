from sqlalchemy import Boolean, Column, Float, String
from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, index=True)
    claim_id = Column(String, index=True, nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    document_type = Column(String, nullable=True)
    ocr_text = Column(String, nullable=True)
    quality_score = Column(Float, nullable=True)
    is_legible = Column(Boolean, default=True)
