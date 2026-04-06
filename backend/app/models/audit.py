from sqlalchemy import Column, String, Text
from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, index=True)
    claim_id = Column(String, index=True, nullable=False)
    step = Column(String, nullable=False)
    payload = Column(Text, nullable=True)
