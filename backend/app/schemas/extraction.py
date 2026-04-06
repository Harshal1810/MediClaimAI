from pydantic import BaseModel
from typing import Any


class ExtractionResult(BaseModel):
    ocr_text: str
    extracted: dict[str, Any]
