from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import os
from contextlib import contextmanager

from app.core.config import settings

_REDACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'("api_key"\s*:\s*")[^"]+(")', re.IGNORECASE), r"\1***\2"),
    (re.compile(r"(api_key=)\S+", re.IGNORECASE), r"\1***"),
    (re.compile(r"\bsk-[A-Za-z0-9]{10,}\b"), "sk-***"),
]


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        for pat, repl in _REDACT_PATTERNS:
            msg = pat.sub(repl, msg)
        return msg


@contextmanager
def _file_lock(lock_path: Path):
    """
    Best-effort cross-process lock for log writes (helps with uvicorn --reload interleaving).

    On Windows we use msvcrt.locking; elsewhere we no-op.
    """
    try:
        import msvcrt  # type: ignore

        lock_path.parent.mkdir(parents=True, exist_ok=True)
        f = open(lock_path, "a+")
        try:
            # Lock 1 byte. Block until acquired.
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            yield
        finally:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
            try:
                f.close()
            except Exception:
                pass
    except Exception:
        yield


class LockedRotatingFileHandler(RotatingFileHandler):
    def __init__(self, filename: str | os.PathLike[str], *args, lock_path: str | os.PathLike[str] | None = None, **kwargs):
        super().__init__(filename, *args, **kwargs)
        self._lock_path = Path(lock_path) if lock_path else Path(str(filename) + ".lock")

    def emit(self, record: logging.LogRecord) -> None:
        with _file_lock(self._lock_path):
            return super().emit(record)


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("claims-adjudication")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = RedactingFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    if settings.LOG_TO_FILE:
        try:
            backend_root = Path(__file__).resolve().parents[2]
            log_dir = backend_root / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            fh = LockedRotatingFileHandler(
                log_dir / "app.log",
                maxBytes=2_000_000,
                backupCount=5,
                encoding="utf-8",
                lock_path=log_dir / "app.log.lock",
            )
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        except Exception:
            pass

    logger.propagate = False
    return logger


logger = setup_logging()
