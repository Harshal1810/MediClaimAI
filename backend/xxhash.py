from __future__ import annotations

"""
Tiny pure-Python fallback for the `xxhash` package.

The project originally depended on the native `xxhash` wheels (pulled in via
LangSmith/LangGraph). On some Windows setups, `pip` install/uninstall can fail
due to temp-dir ACL issues; this shim keeps the app runnable.

It is *not* a drop-in cryptographic hash, nor an optimized xxHash implementation.
It only implements the small subset used by LangSmith/LangGraph:
  - `xxh3_128(data).digest()/hexdigest()`
  - `xxh3_128_hexdigest(data)`
"""

import hashlib
from dataclasses import dataclass
from typing import Any


def _to_bytes(data: Any) -> bytes:
    if data is None:
        return b""
    if isinstance(data, (bytes, bytearray, memoryview)):
        return bytes(data)
    if isinstance(data, str):
        return data.encode("utf-8", errors="ignore")
    return str(data).encode("utf-8", errors="ignore")


@dataclass(frozen=True)
class _Hash128:
    _digest: bytes

    def digest(self) -> bytes:
        return self._digest

    def hexdigest(self) -> str:
        return self._digest.hex()

    def intdigest(self) -> int:
        return int.from_bytes(self._digest, "big", signed=False)


def xxh3_128(data: Any = b"", seed: int = 0) -> _Hash128:  # noqa: ARG001
    payload = _to_bytes(data)
    # Use BLAKE2b as a stable, widely-available 128-bit digest.
    digest = hashlib.blake2b(payload, digest_size=16).digest()
    return _Hash128(digest)


def xxh3_128_hexdigest(data: Any = b"", seed: int = 0) -> str:  # noqa: ARG001
    return xxh3_128(data).hexdigest()


__all__ = ["xxh3_128", "xxh3_128_hexdigest"]

