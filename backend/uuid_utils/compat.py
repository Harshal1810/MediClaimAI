from __future__ import annotations

import secrets
import threading
import time
from uuid import UUID

_lock = threading.Lock()
_last_ms: int | None = None
_counter: int = 0


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def _rand_counter_42() -> int:
    # 42-bit counter with MSB forced to 0 (so effectively 41 random bits).
    return secrets.randbits(41)


def uuid7(*, timestamp: int | None = None, nanos: int | None = None) -> UUID:
    """
    Minimal UUIDv7 generator compatible with `uuid_utils.compat.uuid7`.

    - When called with no args, uses current time (monotonic within a millisecond).
    - When called with `timestamp` (seconds) and `nanos`, derives the millisecond timestamp.
    """
    if timestamp is None and nanos is None:
        unix_ts_ms = _now_ms()
    else:
        if timestamp is None or nanos is None:
            raise TypeError("uuid7() requires both `timestamp` (seconds) and `nanos` when either is provided")
        unix_ts_ms = (int(timestamp) * 1_000) + (int(nanos) // 1_000_000)

    with _lock:
        global _last_ms, _counter
        if _last_ms == unix_ts_ms:
            _counter += 1
            if _counter >= (1 << 42):
                unix_ts_ms += 1
                _counter = _rand_counter_42()
                _last_ms = unix_ts_ms
        else:
            _last_ms = unix_ts_ms
            _counter = _rand_counter_42()

        counter = _counter & ((1 << 42) - 1)

    counter_hi = (counter >> 30) & ((1 << 12) - 1)
    counter_lo = counter & ((1 << 30) - 1)
    rand32 = secrets.randbits(32)

    bits = (
        ((unix_ts_ms & ((1 << 48) - 1)) << 80)
        | (0x7 << 76)
        | (counter_hi << 64)
        | (0x2 << 62)  # RFC 4122 variant (10xx)
        | (counter_lo << 32)
        | rand32
    )
    return UUID(int=bits)


__all__ = ["uuid7"]

