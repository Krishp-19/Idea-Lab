from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.parking_event import ParkingEvent
from app.models.violation import Violation
from app.models.zone import Zone
from app.schemas.dashboard import DashboardStats, DailyTrendItem, ZoneHeatmapItem


def get_dashboard_stats(db: Session) -> DashboardStats:
    total_violations = db.scalar(
        select(func.count(Violation.id)).where(Violation.label == "violation")
    ) or 0

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_violations = db.scalar(
        select(func.count(Violation.id)).where(
            Violation.label == "violation",
            Violation.created_at >= today_start,
        )
    ) or 0

    pending_review = db.scalar(
        select(func.count(Violation.id)).where(Violation.review_status == "pending")
    ) or 0

    confirmed = db.scalar(
        select(func.count(Violation.id)).where(Violation.review_status == "confirmed")
    ) or 0

    dismissed = db.scalar(
        select(func.count(Violation.id)).where(Violation.review_status == "dismissed")
    ) or 0

    # Count by label
    label_counts = db.execute(
        select(Violation.label, func.count(Violation.id)).group_by(Violation.label)
    ).all()
    by_label = {"safe": 0, "risk": 0, "violation": 0}
    for lbl, cnt in label_counts:
        by_label[lbl] = cnt

    return DashboardStats(
        total_violations=total_violations,
        today_violations=today_violations,
        pending_review=pending_review,
        confirmed=confirmed,
        dismissed=dismissed,
        by_label=by_label,
    )


def get_trend_data(db: Session, days: int = 30) -> List[DailyTrendItem]:
    start_date = datetime.now(timezone.utc).date() - timedelta(days=days - 1)
    
    # Query aggregated daily counts
    rows = db.execute(
        select(
            func.date(Violation.created_at).label("day"),
            Violation.label,
            func.count(Violation.id),
        )
        .where(func.date(Violation.created_at) >= start_date)
        .group_by(func.date(Violation.created_at), Violation.label)
    ).all()

    day_map: Dict[str, Dict[str, int]] = {}
    for i in range(days):
        d_str = (start_date + timedelta(days=i)).isoformat()
        day_map[d_str] = {"safe": 0, "risk": 0, "violation": 0, "total": 0}

    for day_val, lbl, cnt in rows:
        d_str = str(day_val)
        if d_str in day_map:
            day_map[d_str][lbl] = cnt
            day_map[d_str]["total"] += cnt

    result = []
    for d_str in sorted(day_map.keys()):
        m = day_map[d_str]
        result.append(
            DailyTrendItem(
                date=d_str,
                safe=m["safe"],
                risk=m["risk"],
                violation=m["violation"],
                total=m["total"],
            )
        )
    return result


def get_heatmap_data(db: Session) -> List[ZoneHeatmapItem]:
    zones = db.scalars(select(Zone)).all()
    result = []

    for z in zones:
        # Count violations, risks, safes linked to this zone via parking_events
        counts = db.execute(
            select(Violation.label, func.count(Violation.id))
            .join(ParkingEvent, Violation.parking_event_id == ParkingEvent.id)
            .where(ParkingEvent.zone_id == z.id)
            .group_by(Violation.label)
        ).all()

        v_count = 0
        r_count = 0
        s_count = 0
        for lbl, cnt in counts:
            if lbl == "violation":
                v_count = cnt
            elif lbl == "risk":
                r_count = cnt
            elif lbl == "safe":
                s_count = cnt

        result.append(
            ZoneHeatmapItem(
                zone_id=z.zone_id,
                zone_name=z.name,
                zone_type=z.zone_type,
                violation_count=v_count,
                risk_count=r_count,
                safe_count=s_count,
                total_count=v_count + r_count + s_count,
                boundary_polygon=z.boundary_polygon or [],
            )
        )

    return result
