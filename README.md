# MediClaimAI — AI‑Assisted OPD Claims Adjudication (Deterministic Core)

This repo implements an OPD claims adjudication demo with **two processing modes**:

- **Rule-based only**: deterministic document classification + heuristic extraction + deterministic rules engine.
- **LLM-assisted**: LLM can help with document understanding (classification/extraction/medical-necessity signals), but **final adjudication decision and payout remain deterministic in code**.

LLM keys are provided **per request/session** and are **never stored**.

---

## Repo Layout

- `Assignment/` — assignment prompt + reference policy/rules/test cases
- `backend/` — FastAPI backend (OCR → classify → extract → normalize → validate → adjudicate → confidence)
- `frontend/` — Next.js UI (create claim → upload docs → preview extraction → adjudicate → view result)
- `shared/` — policy files (`shared/policy/base_policy.json`)
- `docs/` — optional notes/design docs (if present)

---

## Prerequisites

- **Python** 3.11+ (project has been run with 3.13 on Windows)
- **Node.js** 18+ (Next.js 15)
- **Tesseract OCR** installed and available on PATH (required for image OCR)
  - Windows: install Tesseract and set `TESSERACT_PATH` if needed.

---

## Quickstart (Local)

### 1) Backend (FastAPI)

From `MediClaimAI/backend`:

```bash
python -m venv .venv
```

Activate:

- Windows (PowerShell):
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- macOS/Linux:
  ```bash
  source .venv/bin/activate
  ```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `backend/.env` (minimal local dev):

```env
APP_ENV=development
APP_DEBUG=true

# Optional: if Tesseract isn't on PATH
# TESSERACT_PATH=C:\path\to\tesseract.exe
```

Run the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Notes:
- Backend loads env from `backend/.env` and uses an absolute default SQLite DB under `backend/claims.db`.
- Backend creates SQLite tables automatically on startup (no migrations needed for the demo).
- Policy is read from `shared/policy/base_policy.json` by default.

### 2) Frontend (Next.js)

From `MediClaimAI/frontend`:

```bash
npm ci
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Run dev server:

```bash
npm run dev
```

Open:
- `http://127.0.0.1:3000/`

---

## Using the App

1) Create a claim (member details, treatment date, claim amount, optional hospital name).
2) Upload documents (PDF/images). You can choose `Auto-detect` or explicitly select type.
3) Click **Process & Preview** to see extracted fields.
4) Click **Run Adjudication** to compute a deterministic decision/payout.

---

## LLM Toggle (OpenAI / Groq)

- If `Use LLM-assisted processing` is **off**, the backend **never** calls any LLM provider.
- If it is **on**, you must provide:
  - `provider`: `openai` or `groq`
  - `api_key`
  - `model`

LLM is allowed to influence:
- extracted fields (as inputs)
- semantic medical-necessity alignment signals (as inputs)
- confidence inputs and notes

LLM is **not allowed** to make final approval/rejection/payment decisions.

---

## Data Retention / No Persistent Logs (Recommended for EC2 Free Tier)

For production/free-tier deployments, prefer **stdout-only** logs and do **not** persist OCR/prompt blobs.

Put this in `backend/.env`:

```env
APP_ENV=production
APP_DEBUG=false

# Retention / deletion
CLEANUP_ENABLED=true
CLEANUP_INTERVAL_MINUTES=15
SESSION_RETENTION_HOURS=1
DELETE_UPLOADS_AFTER_ADJUDICATION=true

# Disable per-claim traces/blobs and disable file logging
TRACE_ENABLED=false
TRACE_BLOBS_ENABLED=false
TRACE_INCLUDE_CONTENT=false
LOG_TO_FILE=false
```

What this does:
- Deletes `backend/uploads/<claim_id>_*` right after adjudication (best-effort).
- Periodic cleanup worker purges leftover uploads/traces/DB rows after `SESSION_RETENTION_HOURS` and vacuums SQLite.
- No `backend/logs/app.log` and no per-claim trace JSONL/blobs are written when `TRACE_ENABLED=false` / `LOG_TO_FILE=false`.

---

## Testing

Backend unit tests (from `MediClaimAI/backend`):

```bash
pytest -q
```

---

## Deployment Notes (EC2 backend + Render frontend)

Backend needs `backend/` and `shared/` at runtime (policy file is under `shared/`).

### EC2 sparse checkout (clone only what backend needs)

```bash
git clone --no-checkout <REPO_URL> mediclaimai
cd mediclaimai
git sparse-checkout init --cone
git sparse-checkout set backend shared
git checkout main
cd backend
```

Then create `backend/.env` (see “Data Retention” section) and run uvicorn behind a process manager (systemd) and optionally nginx.

### Render (frontend)

- Root directory: `frontend`
- Build: `npm ci && npm run build`
- Start: `npm run start -- -p $PORT`
- Env var: `NEXT_PUBLIC_API_BASE_URL=https://<your-backend-domain>/api/v1`

---

## Troubleshooting

### Backend: claim creation fails after changing `.env`
Restart `uvicorn` completely after changing env vars.

### Frontend: `.next` / build cache issues
Stop the frontend server, delete `.next`, then restart:

- PowerShell:
  ```powershell
  Remove-Item -Recurse -Force .\.next
  npm run dev
  ```

