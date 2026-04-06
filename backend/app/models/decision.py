from sqlalchemy import Column, Float, String, Text
from app.core.database import Base


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(String, primary_key=True, index=True)
    claim_id = Column(String, index=True, nullable=False)
    decision = Column(String, nullable=False)
    approved_amount = Column(Float, default=0)
    reasons_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
