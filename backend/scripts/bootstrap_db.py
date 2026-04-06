from app.core.database import Base, engine
from app.models.claim import Claim
from app.models.document import Document
from app.models.extraction import Extraction
from app.models.decision import Decision
from app.models.audit import AuditLog

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")
