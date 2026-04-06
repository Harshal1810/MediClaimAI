# Deployment

Recommended deployment split:

- **Backend**: AWS EC2 (small instance is fine for demo)
- **Frontend**: Render (static + Node runtime)
- **Database**: SQLite for demo (file under `backend/claims.db`)

## Backend on EC2

Backend runtime needs:
- `backend/`
- `shared/` (policy file lives under `shared/policy/`)

If you want to clone only what’s needed:

```bash
git clone --no-checkout <REPO_URL> mediclaimai
cd mediclaimai
git sparse-checkout init --cone
git sparse-checkout set backend shared
git checkout main
```

Run (example):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Set production `.env` for free-tier disk safety (no persistent traces/log files; aggressive retention):

```env
APP_ENV=production
APP_DEBUG=false

CLEANUP_ENABLED=true
SESSION_RETENTION_HOURS=1
DELETE_UPLOADS_AFTER_ADJUDICATION=true

TRACE_ENABLED=false
LOG_TO_FILE=false
```

## Frontend on Render

- Root directory: `frontend`
- Build command: `npm ci && npm run build`
- Start command: `npm run start -- -p $PORT`
- Env var: `NEXT_PUBLIC_API_BASE_URL=https://<your-backend-domain>/api/v1`
