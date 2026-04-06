from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.utils.redaction import redact_secrets
from app.core.config import settings


class ClaimTraceLogger:
    """
    Writes per-claim JSONL traces to `backend/logs/claims/<claim_id>.jsonl`.
    Never logs API keys (payload is redacted).
    """

    def __init__(self, claim_id: str):
        self.claim_id = claim_id
        backend_root = Path(__file__).resolve().parents[2]
        self.dir = backend_root / "logs" / "claims"
        self.path = self.dir / f"{claim_id}.jsonl"
        self.blob_dir = self.dir / claim_id

        self.enabled = bool(settings.TRACE_ENABLED)
        self.blobs_enabled = bool(settings.TRACE_BLOBS_ENABLED)
        self.include_content = bool(settings.TRACE_INCLUDE_CONTENT)

    def log(self, event: str, payload: dict[str, Any] | None = None) -> None:
        if not self.enabled:
            return
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "claim_id": self.claim_id,
            "event": event,
            "payload": redact_secrets(payload or {}),
        }
        if not self.include_content:
            # Remove PHI-heavy keys by default. (Blob files are also disabled by default in prod.)
            for key in ("ocr_excerpt", "ocr_text_excerpt", "ocr_texts", "ocr_texts_by_doc", "extracted", "prompt", "raw"):
                record["payload"].pop(key, None)
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            # Logging must never break adjudication.
            return

    def write_text_blob(self, *, name: str, text: str, ext: str = "txt") -> str | None:
        """
        Write large text payloads (OCR text, prompts, raw LLM output) as separate files.

        Returns a relative path under `backend/logs/claims/` for easy navigation.
        """
        if not self.enabled or not self.blobs_enabled:
            return None
        try:
            safe = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in (name or "blob")])[:80]
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            token = uuid.uuid4().hex[:8]
            self.blob_dir.mkdir(parents=True, exist_ok=True)
            path = self.blob_dir / f"{ts}_{safe}_{token}.{ext}"
            with open(path, "w", encoding="utf-8") as f:
                f.write(text or "")
            # store relative path for portability
            return str(Path("logs") / "claims" / self.claim_id / path.name)
        except Exception:
            return None
