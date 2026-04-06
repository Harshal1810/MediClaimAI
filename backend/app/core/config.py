from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    APP_NAME: str = "Claims Adjudication API"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    # Use an absolute SQLite path by default to avoid CWD-dependent failures (common with reloaders/IDEs).
    _default_sqlite_path = (_REPO_ROOT / "backend" / "claims.db").resolve()
    DATABASE_URL: str = f"sqlite:///{str(_default_sqlite_path).replace('\\', '/')}"

    POLICY_FILE_PATH: str = str(_REPO_ROOT / "shared" / "policy" / "base_policy.json")
    DERIVED_RULES_FILE_PATH: str = str(_REPO_ROOT / "shared" / "policy" / "derived_rules.json")

    # Data retention / tracing (important for small disks like free-tier EC2)
    CLEANUP_ENABLED: bool = True
    CLEANUP_INTERVAL_MINUTES: int = 15
    SESSION_RETENTION_HOURS: int = 6
    DELETE_UPLOADS_AFTER_ADJUDICATION: bool = False

    # Tracing can write OCR text, extracted JSON, and LLM prompts to disk.
    # Keep it enabled for local debugging, but disable PHI persistence by default in production.
    TRACE_ENABLED: bool = True
    TRACE_BLOBS_ENABLED: bool = False
    TRACE_INCLUDE_CONTENT: bool = False

    # Backend logger file output (app.log). Prefer stdout-only in production/free-tier.
    LOG_TO_FILE: bool = True

    # Load `backend/.env` regardless of the current working directory.
    model_config = SettingsConfigDict(
        env_file=str((_REPO_ROOT / "backend" / ".env").resolve()),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Reasonable defaults by environment (can be overridden by env vars)
if settings.APP_ENV.lower() in {"prod", "production"}:
    settings.APP_DEBUG = False
    settings.LOG_TO_FILE = False
    settings.TRACE_ENABLED = False
    settings.TRACE_BLOBS_ENABLED = False
    settings.TRACE_INCLUDE_CONTENT = False
    settings.DELETE_UPLOADS_AFTER_ADJUDICATION = True
