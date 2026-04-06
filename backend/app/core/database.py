from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    """
    Create DB tables for local/dev usage.

    This keeps the demo pipeline runnable without requiring migrations.
    """
    # Ensure all model modules are imported so `Base.metadata` includes their tables.
    # (Without this, `create_all()` won't create tables and SQLite will error at runtime.)
    from importlib import import_module

    for module in ("claim", "document", "decision", "extraction", "audit"):
        import_module(f"app.models.{module}")
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
