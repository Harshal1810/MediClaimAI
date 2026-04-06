from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class LLMRuntimeConfig(BaseModel):
    provider: Literal["openai", "groq"]
    api_key: str = Field(..., min_length=10)
    model: str


class ClaimCreateRequest(BaseModel):
    session_id: str
    member_id: str
    member_name: str
    treatment_date: str
    submission_date: str
    claim_amount: float
    hospital_name: Optional[str] = None
    cashless_requested: bool = False
    use_llm: bool = False
    llm_config: Optional[LLMRuntimeConfig] = None

    @model_validator(mode="after")
    def validate_llm_config(self):
        if self.use_llm and not self.llm_config:
            raise ValueError("use_llm=true requires llm_config {provider, api_key, model}.")
        if not self.use_llm and self.llm_config is not None:
            raise ValueError("use_llm=false must not include llm_config.")
        return self


class ClaimCreateResponse(BaseModel):
    claim_id: str
    status: str
