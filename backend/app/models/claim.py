from sqlalchemy import Boolean, Column, Float, String
from app.core.database import Base


class Claim(Base):
    __tablename__ = "claims"

    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    member_id = Column(String, nullable=False)
    member_name = Column(String, nullable=False)
    treatment_date = Column(String, nullable=False)
    submission_date = Column(String, nullable=False)
    claim_amount = Column(Float, nullable=False)
    hospital_name = Column(String, nullable=True)
    cashless_requested = Column(Boolean, default=False)
    status = Column(String, default="CREATED")
