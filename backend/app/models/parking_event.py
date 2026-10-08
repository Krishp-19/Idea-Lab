from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ParkingEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "parking_events"

    vehicle_id: Mapped[str] = mapped_column(String(36), ForeignKey("vehicles.id"), nullable=False, index=True)
    zone_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("zones.id"), nullable=True, index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dwell_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    features: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ml_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # safe | risk | violation | pending
    ml_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ml_probabilities: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    snapshot_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    vehicle = relationship("Vehicle", back_populates="parking_events")
    zone = relationship("Zone", back_populates="parking_events")
    violation: Mapped[Optional["Violation"]] = relationship("Violation", back_populates="parking_event", uselist=False, cascade="all, delete-orphan")
