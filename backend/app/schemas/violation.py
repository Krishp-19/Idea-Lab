from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel
from app.schemas.vehicle import VehicleOut


class ParkingEventOut(BaseModel):
    id: str
    vehicle_id: str
    zone_id: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    dwell_seconds: float
    features: Dict[str, Any]
    ml_label: Optional[str] = None
    ml_confidence: Optional[float] = None
    ml_probabilities: Optional[Dict[str, Any]] = None
    snapshot_path: Optional[str] = None

    class Config:
        from_attributes = True


class ViolationDetail(BaseModel):
    id: str
    parking_event_id: str
    label: str  # safe | risk | violation
    review_status: str  # pending | confirmed | dismissed
    confirmed_by_id: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    dismissed_by_id: Optional[str] = None
    dismissed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    parking_event: Optional[ParkingEventOut] = None
    vehicle: Optional[VehicleOut] = None
    zone_name: Optional[str] = None

    class Config:
        from_attributes = True


class ViolationReviewRequest(BaseModel):
    action: str  # confirm | dismiss
    notes: Optional[str] = None
