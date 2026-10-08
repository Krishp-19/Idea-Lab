from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.models.parking_event import ParkingEvent
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.violation import Violation
from app.models.zone import Zone
from app.schemas.vehicle import VehicleOut
from app.schemas.violation import ParkingEventOut, ViolationDetail


def list_violations(
    db: Session,
    status: Optional[str] = None,
    label: Optional[str] = None,
    zone_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[ViolationDetail], int]:
    stmt = (
        select(Violation)
        .join(ParkingEvent, Violation.parking_event_id == ParkingEvent.id)
        .options(
            joinedload(Violation.parking_event).joinedload(ParkingEvent.vehicle),
            joinedload(Violation.parking_event).joinedload(ParkingEvent.zone),
        )
    )

    if status:
        stmt = stmt.where(Violation.review_status == status)
    if label:
        stmt = stmt.where(Violation.label == label)
    if zone_id:
        stmt = stmt.where(ParkingEvent.zone_id == zone_id)
    if date_from:
        stmt = stmt.where(Violation.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Violation.created_at <= date_to)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # Sort newest first & paginate
    stmt = stmt.order_by(Violation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    violations = db.scalars(stmt).all()

    items = []
    for v in violations:
        pe = v.parking_event
        veh = pe.vehicle if pe else None
        zone = pe.zone if pe else None

        items.append(
            ViolationDetail(
                id=v.id,
                parking_event_id=v.parking_event_id,
                label=v.label,
                review_status=v.review_status,
                confirmed_by_id=v.confirmed_by_id,
                confirmed_at=v.confirmed_at,
                dismissed_by_id=v.dismissed_by_id,
                dismissed_at=v.dismissed_at,
                reviewer_notes=v.reviewer_notes,
                created_at=v.created_at,
                updated_at=v.updated_at,
                parking_event=ParkingEventOut.model_validate(pe) if pe else None,
                vehicle=VehicleOut.model_validate(veh) if veh else None,
                zone_name=zone.name if zone else None,
            )
        )

    return items, total


def get_violation_detail(db: Session, violation_id: str) -> Optional[ViolationDetail]:
    stmt = (
        select(Violation)
        .where(Violation.id == violation_id)
        .options(
            joinedload(Violation.parking_event).joinedload(ParkingEvent.vehicle),
            joinedload(Violation.parking_event).joinedload(ParkingEvent.zone),
        )
    )
    v = db.scalar(stmt)
    if not v:
        return None

    pe = v.parking_event
    veh = pe.vehicle if pe else None
    zone = pe.zone if pe else None

    return ViolationDetail(
        id=v.id,
        parking_event_id=v.parking_event_id,
        label=v.label,
        review_status=v.review_status,
        confirmed_by_id=v.confirmed_by_id,
        confirmed_at=v.confirmed_at,
        dismissed_by_id=v.dismissed_by_id,
        dismissed_at=v.dismissed_at,
        reviewer_notes=v.reviewer_notes,
        created_at=v.created_at,
        updated_at=v.updated_at,
        parking_event=ParkingEventOut.model_validate(pe) if pe else None,
        vehicle=VehicleOut.model_validate(veh) if veh else None,
        zone_name=zone.name if zone else None,
    )


def review_violation(
    db: Session,
    violation_id: str,
    action: str,  # confirm | dismiss
    user_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[Violation]:
    v = db.scalar(select(Violation).where(Violation.id == violation_id))
    if not v:
        return None

    now = datetime.now(timezone.utc)
    if action == "confirm":
        v.review_status = "confirmed"
        v.confirmed_by_id = user_id
        v.confirmed_at = now
        v.dismissed_by_id = None
        v.dismissed_at = None
    elif action == "dismiss":
        v.review_status = "dismissed"
        v.dismissed_by_id = user_id
        v.dismissed_at = now
        v.confirmed_by_id = None
        v.confirmed_at = None
    else:
        v.review_status = "pending"

    if notes is not None:
        v.reviewer_notes = notes

    db.commit()
    db.refresh(v)
    return v
