"use client";

import { LLMProvider } from "@/types/provider";
import { DEFAULT_GROQ_MODEL, DEFAULT_OPENAI_MODEL, RECOMMENDED_GROQ_MODELS, RECOMMENDED_OPENAI_MODELS } from "@/lib/constants";
import { useMemo, useState } from "react";

interface Props {
  provider: LLMProvider;
  api_key: string;
  model: string;
  onChange: (next: { provider: LLMProvider; api_key: string; model: string }) => void;
}

export default function ProviderSelector({ provider, api_key, model, onChange }: Props) {
  const recommended = useMemo<string[]>(
    () => (provider === "openai" ? [...RECOMMENDED_OPENAI_MODELS] : [...RECOMMENDED_GROQ_MODELS]),
    [provider],
  );
  const isRecommended = recommended.includes(model);
  const [customModel, setCustomModel] = useState(isRecommended ? "" : model);

  return (
    <div className="form">
      <div className="field">
        <label>Provider</label>
        <select
          value={provider}
          onChange={(e) => {
            const nextProvider = e.target.value as LLMProvider;
            const nextModel = nextProvider === "openai" ? DEFAULT_OPENAI_MODEL : DEFAULT_GROQ_MODEL;
            setCustomModel("");
            onChange({ provider: nextProvider, api_key, model: nextModel });
          }}
        >
          <option value="openai">OpenAI</option>
          <option value="groq">Groq</option>
        </select>
      </div>
      <div className="field">
        <label>API Key</label>
        <input type="password" value={api_key} onChange={(e) => onChange({ provider, api_key: e.target.value, model })} placeholder="Enter API key" />
      </div>
      <div className="field">
        <label>Model</label>
        <select
          value={isRecommended ? model : "__custom__"}
          onChange={(e) => {
            const v = e.target.value;
            if (v === "__custom__") {
              const fallback = provider === "openai" ? DEFAULT_OPENAI_MODEL : DEFAULT_GROQ_MODEL;
              setCustomModel(customModel || fallback);
              onChange({ provider, api_key, model: customModel || fallback });
              return;
            }
            setCustomModel("");
            onChange({ provider, api_key, model: v });
          }}
        >
          {recommended.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
          <option value="__custom__">Custom...</option>
        </select>
        {!isRecommended ? (
          <div className="field" style={{ marginTop: 8 }}>
            <label>Custom model id</label>
            <input
              value={customModel}
              onChange={(e) => {
                setCustomModel(e.target.value);
                onChange({ provider, api_key, model: e.target.value });
              }}
              placeholder="Enter custom model id"
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
