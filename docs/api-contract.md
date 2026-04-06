# API Contract

Base URL: `http://<host>:8000/api/v1`

## Health

- `GET /health`

Response:
```json
{ "status": "ok" }
```

## Policy (read-only)

- `GET /policy`

Response:
```json
{ "policy": { "..." : "..." }, "derived_rules": { "...": "..." } }
```

## Claims

### Create claim

- `POST /claims`

Request (example):
```json
{
  "session_id": "uuid-from-frontend",
  "member_id": "EMP100",
  "member_name": "Harry Khamkar",
  "treatment_date": "2026-04-01",
  "submission_date": "2026-04-05",
  "claim_amount": 1500,
  "hospital_name": "Jeevika Hospital",
  "cashless_requested": false,
  "use_llm": false,
  "llm_config": null
}
```

Response:
```json
{ "claim_id": "CLM_XXXXXXXXXX", "status": "CREATED" }
```

### Upload document

- `POST /claims/{claim_id}/documents?document_type=<optional>`
  - `document_type` can be: `prescription | bill | pharmacy_bill | report`
  - if omitted, backend will classify during processing.

Request: `multipart/form-data` with field `file`.

Response:
```json
{ "document_id": "DOC_XXXXXXXXXX", "filename": "01_prescription.pdf", "status": "uploaded" }
```

### Process documents (OCR → classify → extract → normalize → medical signal)

- `POST /claims/{claim_id}/process-documents`

Request (rule-based):
```json
{ "use_llm": false, "llm_config": null }
```

Request (LLM-assisted):
```json
{
  "use_llm": true,
  "llm_config": { "provider": "openai", "api_key": "sk-...", "model": "gpt-5-mini" }
}
```

Response (shape, simplified):
```json
{
  "claim_id": "CLM_...",
  "use_llm": true,
  "llm_provider": "openai",
  "llm_model": "gpt-5-mini",
  "documents": [
    {
      "document_id": "DOC_...",
      "filename": "01_prescription.pdf",
      "document_type": "prescription",
      "extracted": { "..." : "..." },
      "missing_fields": [],
      "schema_valid": true,
      "flags": []
    }
  ],
  "normalized": { "...": "..." },
  "medical": { "...": "..." },
  "flags": []
}
```

## Adjudication

### Adjudicate (stored claim)

- `POST /claims/{claim_id}/adjudicate`

Request: same `use_llm` / `llm_config` shape as `/process-documents`.

Response: an `AdjudicationResponse` including:
- deterministic decision (`APPROVED | PARTIAL | REJECTED | MANUAL_REVIEW`)
- `approved_amount` (capped to claim amount)
- rejection reasons, deductions, flags/notes
- processing metadata (`use_llm`, methods)
- optional `llm_final_review` (advisory cross-check only; no api keys are ever returned)

### Adjudicate (direct / stateless)

- `POST /adjudicate`

Used for debugging: caller supplies `claim_context` directly.
