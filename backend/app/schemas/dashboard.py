from typing import Any, Dict, List
from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_violations: int
    today_violations: int
    pending_review: int
    confirmed: int
    dismissed: int
    by_label: Dict[str, int]


class DailyTrendItem(BaseModel):
    date: str
    safe: int
    risk: int
    violation: int
    total: int


class ZoneHeatmapItem(BaseModel):
    zone_id: str
    zone_name: str
    zone_type: str
    violation_count: int
    risk_count: int
    safe_count: int
    total_count: int
    boundary_polygon: List[Any]
