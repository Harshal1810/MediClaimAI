from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.core.logging import setup_logging
from app.api.routes.health import router as health_router
from app.api.routes.claims import router as claims_router
from app.api.routes.documents import router as documents_router
from app.api.routes.adjudication import router as adjudication_router
from app.api.routes.policy import router as policy_router
from app.services.retention_service import start_retention_worker

app = FastAPI(title=settings.APP_NAME, debug=settings.APP_DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(claims_router, prefix=settings.API_V1_PREFIX)
app.include_router(documents_router, prefix=settings.API_V1_PREFIX)
app.include_router(adjudication_router, prefix=settings.API_V1_PREFIX)
app.include_router(policy_router, prefix=settings.API_V1_PREFIX)


@app.on_event("startup")
def _startup():
    setup_logging()
    # Ensure tables exist for local/dev SQLite usage.
    if settings.DATABASE_URL.startswith("sqlite"):
        init_db()
    start_retention_worker()


@app.get("/")
def root():
    return {"message": "Claims Adjudication API is running"}
