from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.audit import AuditLog
from app.models.claim import Claim
from app.models.decision import Decision
from app.models.document import Document
from app.models.extraction import Extraction


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _iter_claim_ids_from_uploads(uploads_dir: Path) -> set[str]:
    claim_ids: set[str] = set()
    if not uploads_dir.exists():
        return claim_ids
    for p in uploads_dir.glob("*"):
        if not p.is_file():
            continue
        # filenames are stored as "{claim_id}_{safe_name}"
        name = p.name
        if "_" not in name:
            continue
        claim_id = name.split("_", 1)[0]
        if claim_id.startswith("CLM_"):
            claim_ids.add(claim_id)
    return claim_ids


def _iter_claim_ids_from_traces(trace_dir: Path) -> set[str]:
    claim_ids: set[str] = set()
    if not trace_dir.exists():
        return claim_ids
    for p in trace_dir.glob("CLM_*.jsonl"):
        claim_ids.add(p.stem)
    # Also consider blob folders
    for d in trace_dir.glob("CLM_*"):
        if d.is_dir():
            claim_ids.add(d.name)
    return claim_ids


def _latest_mtime(paths: list[Path]) -> datetime | None:
    latest: float | None = None
    for p in paths:
        try:
            if p.exists():
                t = p.stat().st_mtime
                latest = t if latest is None else max(latest, t)
        except Exception:
            continue
    if latest is None:
        return None
    return datetime.fromtimestamp(latest, tz=timezone.utc)


class RetentionService:
    """
    Best-effort cleanup of per-claim artifacts after a retention window:
      - uploaded documents under `backend/uploads/`
      - per-claim traces under `backend/logs/claims/`
      - DB rows for claim/documents/extractions/decisions/audit logs

    We intentionally avoid relying on DB timestamps (tables don't have them);
    instead we treat file mtimes as "last activity".
    """

    def __init__(self):
        root = _backend_root()
        self.uploads_dir = root / "uploads"
        self.trace_dir = root / "logs" / "claims"

    def delete_uploads_for_claim(self, claim_id: str) -> int:
        deleted = 0
        try:
            for p in self.uploads_dir.glob(f"{claim_id}_*"):
                try:
                    if p.is_file():
                        p.unlink(missing_ok=True)
                        deleted += 1
                except Exception:
                    continue
        except Exception:
            return deleted
        return deleted

    def cleanup_once(self) -> dict[str, int]:
        if not settings.CLEANUP_ENABLED:
            return {"deleted_claims": 0, "deleted_files": 0, "deleted_db_rows": 0}

        cutoff = datetime.now(timezone.utc) - timedelta(hours=max(int(settings.SESSION_RETENTION_HOURS), 1))

        claim_ids = set()
        claim_ids |= _iter_claim_ids_from_uploads(self.uploads_dir)
        claim_ids |= _iter_claim_ids_from_traces(self.trace_dir)

        deleted_claims = 0
        deleted_files = 0
        deleted_db_rows = 0
        did_db_work = False

        for claim_id in sorted(claim_ids):
            artifacts: list[Path] = []
            artifacts.append(self.trace_dir / f"{claim_id}.jsonl")
            artifacts.append(self.trace_dir / claim_id)
            artifacts.extend(list(self.uploads_dir.glob(f"{claim_id}_*")))
            last = _latest_mtime(artifacts)
            if last is None or last > cutoff:
                continue

            # Delete filesystem artifacts first (space pressure)
            deleted_files += self.delete_uploads_for_claim(claim_id)
            for p in artifacts:
                try:
                    if not p.exists():
                        continue
                    if p.parent == self.uploads_dir:
                        # Already handled by delete_uploads_for_claim() above.
                        continue
                    if p.is_dir():
                        # Delete files bottom-up then remove dirs.
                        for child in sorted(p.rglob("*"), key=lambda x: len(x.parts), reverse=True):
                            try:
                                if child.is_file():
                                    child.unlink(missing_ok=True)
                                elif child.is_dir():
                                    child.rmdir()
                            except Exception:
                                continue
                        p.rmdir()
                    else:
                        p.unlink(missing_ok=True)
                    deleted_files += 1
                except Exception:
                    continue

            # Best-effort DB cleanup
            try:
                with SessionLocal() as db:
                    rows = self._delete_claim_rows(db, claim_id)
                    if rows:
                        did_db_work = True
                        deleted_db_rows += rows
            except Exception:
                pass

            deleted_claims += 1

        # SQLite won't shrink on deletes; vacuum occasionally when we did real DB cleanup.
        if did_db_work and settings.DATABASE_URL.startswith("sqlite"):
            try:
                with SessionLocal() as db:
                    db.execute(text("VACUUM"))
                    db.commit()
            except Exception:
                pass

        return {"deleted_claims": deleted_claims, "deleted_files": deleted_files, "deleted_db_rows": deleted_db_rows}

    def _delete_claim_rows(self, db: Session, claim_id: str) -> int:
        # Gather document ids, then delete dependent extractions.
        doc_ids = [d.id for d in db.query(Document).filter(Document.claim_id == claim_id).all()]

        rows = 0
        if doc_ids:
            rows += db.query(Extraction).filter(Extraction.document_id.in_(doc_ids)).delete(synchronize_session=False)
        rows += db.query(Document).filter(Document.claim_id == claim_id).delete(synchronize_session=False)
        rows += db.query(Decision).filter(Decision.claim_id == claim_id).delete(synchronize_session=False)
        rows += db.query(AuditLog).filter(AuditLog.claim_id == claim_id).delete(synchronize_session=False)
        rows += db.query(Claim).filter(Claim.id == claim_id).delete(synchronize_session=False)
        db.commit()
        return int(rows)


_thread: threading.Thread | None = None


def start_retention_worker() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    if not settings.CLEANUP_ENABLED:
        return

    def _loop():
        svc = RetentionService()
        interval = max(int(settings.CLEANUP_INTERVAL_MINUTES), 5) * 60
        # Initial cleanup pass
        try:
            svc.cleanup_once()
        except Exception:
            pass
        while True:
            time.sleep(interval)
            try:
                svc.cleanup_once()
            except Exception:
                continue

    _thread = threading.Thread(target=_loop, name="retention-worker", daemon=True)
    _thread.start()
