from app.llm.openai_provider import OpenAIProvider
from app.llm.groq_provider import GroqProvider


class LLMProviderFactory:
    @staticmethod
    def create(provider: str, api_key: str, model: str, *, trace=None, trace_meta: dict | None = None):
        if not api_key or not model:
            raise ValueError("LLM provider configuration missing api_key/model.")
        if provider == "openai":
            p = OpenAIProvider(api_key=api_key, model=model)
            if trace is not None and hasattr(p, "set_trace"):
                p.set_trace(trace, trace_meta)
            return p
        if provider == "groq":
            p = GroqProvider(api_key=api_key, model=model)
            if trace is not None and hasattr(p, "set_trace"):
                p.set_trace(trace, trace_meta)
            return p
        raise ValueError(f"Unsupported provider: {provider}")
