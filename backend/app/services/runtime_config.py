from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeProcessingConfig:
    use_llm: bool
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None

    def __repr__(self) -> str:
        # Never leak API keys via logs/tracebacks.
        return (
            "RuntimeProcessingConfig("
            f"use_llm={self.use_llm}, "
            f"llm_provider={self.llm_provider!r}, "
            f"llm_model={self.llm_model!r}, "
            "llm_api_key='***redacted***'"
            ")"
        )

