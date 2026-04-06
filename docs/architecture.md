# Architecture

This system is built around a **deterministic adjudication engine** with an optional **LLM-assisted document understanding** layer.

- The **LLM never makes the final decision** (approval/rejection/payout).
- The **rules engine is the source of truth** for limits, eligibility, exclusions, co-pay/discounts, and payout calculations.

## High-level components

- **Frontend (Next.js)**: create claim → upload documents → preview extracted fields → adjudicate → view result
- **Backend (FastAPI)**:
  - document ingestion (`backend/uploads/`)
  - OCR
  - document classification (rule-based first, LLM fallback only when enabled and uncertain)
  - structured extraction (rule-based or LLM-assisted with fallback)
  - deterministic normalization + optional constrained LLM mapping suggestions
  - medical-necessity signal (rule-based or LLM-assisted; LLM is input-only)
  - deterministic adjudication (policy + derived rules)
  - confidence breakdown (works in both modes)

## End-to-end pipeline

```mermaid
flowchart TD
  UI[Next.js UI] -->|Create Claim| API1[FastAPI /claims]
  UI -->|Upload Docs| API2[FastAPI /claims/{id}/documents]
  UI -->|Process & Preview| API3[FastAPI /claims/{id}/process-documents]
  UI -->|Adjudicate| API4[FastAPI /claims/{id}/adjudicate]
  API3 --> OCR[OCR Service]
  OCR --> CLASS[Doc Classifier]
  CLASS --> EXTRACT[Extraction Service]
  EXTRACT --> NORM[Normalization]
  NORM --> CONSIST[Consistency / Validation]
  CONSIST --> MED[Medical Necessity Signal]
  MED --> RULES[Deterministic Rule Engine]
  RULES --> CONF[Confidence Service]
  CONF --> API4
  API4 --> UI
```

## Processing modes

### Rule-based only (`use_llm=false`)

- classification: deterministic keyword scorer only
- extraction: deterministic heuristics/regex by document type
- medical necessity: rule-based signal only
- decision/payout: deterministic rules engine

### LLM-assisted (`use_llm=true`)

- classification: rule-based first, then LLM only if uncertain
- extraction: LLM structured extraction + schema validation, with rule-based fallback
- normalization: deterministic mapping, with optional LLM suggestions constrained to allowed canonical values
- medical necessity: LLM semantic alignment signal (input-only) + rule-based checks
- decision/payout: deterministic rules engine (authoritative)

## Data retention & logging (important for small disks)

- Uploaded documents are stored under `backend/uploads/` for processing.
- Debug traces can be written to `backend/logs/` (per-claim JSONL + optional OCR/prompt blobs), but should be disabled for production/free-tier deployments.
- A background retention worker can delete uploads, traces, and related DB rows after a configured retention window.
