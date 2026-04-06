# Setup

Canonical setup instructions live in the repo root README:

- `README.md` (recommended): end-to-end backend + frontend setup, env vars, and troubleshooting.

Quick commands:

## Backend

```bash
cd backend
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Frontend

```bash
cd frontend
npm ci
npm run dev
```
