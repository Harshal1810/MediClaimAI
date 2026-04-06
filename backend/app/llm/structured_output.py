from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _extract_json(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return "{}"
    m = _JSON_BLOCK_RE.search(raw)
    if m:
        return m.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1].strip()
    return raw


def parse_json_model(model_cls: type[ModelT], text: str) -> ModelT:
    payload_text = _extract_json(text)
    data = json.loads(payload_text)
    return model_cls.model_validate(data)


def langchain_complete_json(
    *,
    chat_model: Any,
    messages: list[Any],
    response_model: type[ModelT],
) -> tuple[ModelT, str]:
    """
    LangChain chat invocation returning a validated Pydantic model.

    - Prefers with_structured_output(response_model) when available
    - Falls back to parsing model text output as JSON
    """
    # Try structured output adapter when supported by the LangChain model.
    try:
        if hasattr(chat_model, "with_structured_output"):
            # langchain-openai defaults to OpenAI "structured outputs" JSON schema mode.
            # For broader schema compatibility, prefer function calling when supported.
            try:
                structured = chat_model.with_structured_output(response_model, method="function_calling")
            except TypeError:
                structured = chat_model.with_structured_output(response_model)
            out = structured.invoke(messages)
            if isinstance(out, response_model):
                return out, out.model_dump_json()
            if isinstance(out, dict):
                parsed = response_model.model_validate(out)
                return parsed, json.dumps(out, ensure_ascii=False)
    except Exception:
        pass

    resp = chat_model.invoke(messages)
    content = getattr(resp, "content", None) or str(resp) or "{}"
    return parse_json_model(response_model, content), content
