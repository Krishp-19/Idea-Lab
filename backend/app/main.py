from pathlib import Path
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.seed import run_seed
from app.db.session import SessionLocal, engine

settings = get_settings()
configure_logging(settings.debug)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    req_id = str(uuid.uuid4())
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = req_id
    return response


@app.on_event("startup")
def on_startup() -> None:
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    # Run seed (admin user & zones sync)
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()

    # Ensure evidence directory exists & mount static
    project_root = Path(__file__).resolve().parents[2]
    evidence_path = project_root / settings.evidence_dir
    evidence_path.mkdir(parents=True, exist_ok=True)
    app.mount("/static/evidence", StaticFiles(directory=str(evidence_path)), name="static_evidence")


# Mount API v1 router
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "docs": "/docs",
        "api_v1": settings.api_v1_prefix,
    }
