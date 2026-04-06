from sqlalchemy import Column, String, Text
from app.core.database import Base


class Extraction(Base):
    __tablename__ = "extractions"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, index=True, nullable=False)
    extracted_json = Column(Text, nullable=True)
