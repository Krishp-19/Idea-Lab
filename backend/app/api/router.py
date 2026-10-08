from fastapi import APIRouter
from app.api.routes import auth, cameras, dashboard, evidence, health, processing, violations, zones

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(cameras.router, prefix="/cameras", tags=["Cameras"])
api_router.include_router(zones.router, prefix="/zones", tags=["Zones"])
api_router.include_router(violations.router, prefix="/violations", tags=["Violations"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(processing.router, prefix="/processing", tags=["Processing"])
api_router.include_router(evidence.router, prefix="/evidence", tags=["Evidence"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])
