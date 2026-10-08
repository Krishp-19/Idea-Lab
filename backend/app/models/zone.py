from typing import Any, List, Optional
from sqlalchemy import Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Zone(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "zones"

    camera_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("cameras.id"), nullable=True)
    zone_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    boundary_polygon: Mapped[List[Any]] = mapped_column(JSON, nullable=False, default=list)
    expected_angle_degrees: Mapped[float] = mapped_column(Float, default=90.0, nullable=False)
    zone_type: Mapped[str] = mapped_column(String(50), default="parking_bay", nullable=False)  # parking_bay | fire_lane | walkway

    camera = relationship("Camera", back_populates="zones")
    parking_events = relationship("ParkingEvent", back_populates="zone")
