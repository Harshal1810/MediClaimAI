from __future__ import annotations

from typing import Any


SENSITIVE_KEYS = {
    "api_key",
    "llm_api_key",
    "authorization",
    "x-api-key",
    "apikey",
    "access_token",
    "token",
}


def redact_secrets(value: Any) -> Any:
    """
    Recursively redact common secret fields from dict/list payloads.
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if str(k).lower() in SENSITIVE_KEYS:
                out[k] = "***redacted***"
            else:
                out[k] = redact_secrets(v)
        return out
    if isinstance(value, list):
        return [redact_secrets(v) for v in value]
    return value

