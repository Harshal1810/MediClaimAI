export const DEFAULT_OPENAI_MODEL = "gpt-5-mini";
export const DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile";

export const RECOMMENDED_OPENAI_MODELS = [
  "gpt-5-mini",
  "gpt-5.2",
  "gpt-5.2-chat-latest",
  "gpt-4.1",
] as const;

export const RECOMMENDED_GROQ_MODELS = [
  "llama-3.3-70b-versatile",
  "llama-3.1-8b-instant",
  "openai/gpt-oss-20b",
  "openai/gpt-oss-120b",
] as const;
