export type LLMProvider = "openai" | "groq";

export interface LLMConfig {
  provider: LLMProvider;
  api_key: string;
  model: string;
}
