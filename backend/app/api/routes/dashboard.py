from typing import List
from fastapi import APIRouter, Query
from app.api.deps import DbSession
from app.schemas.dashboard import DailyTrendItem, DashboardStats, ZoneHeatmapItem
from app.services.dashboard_service import get_dashboard_stats, get_heatmap_data, get_trend_data

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(db: DbSession) -> DashboardStats:
    return get_dashboard_stats(db)


@router.get("/trend", response_model=List[DailyTrendItem])
def dashboard_trend(
    db: DbSession,
    days: int = Query(30, ge=1, le=365),
) -> List[DailyTrendItem]:
    return get_trend_data(db, days=days)


@router.get("/heatmap", response_model=List[ZoneHeatmapItem])
def dashboard_heatmap(db: DbSession) -> List[ZoneHeatmapItem]:
    return get_heatmap_data(db)
