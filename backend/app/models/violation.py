from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Violation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "violations"

    parking_event_id: Mapped[str] = mapped_column(String(36), ForeignKey("parking_events.id"), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False)  # safe | risk | violation
    review_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending | confirmed | dismissed

    confirmed_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    dismissed_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    parking_event = relationship("ParkingEvent", back_populates="violation")
    confirmed_by = relationship("User", foreign_keys=[confirmed_by_id])
    dismissed_by = relationship("User", foreign_keys=[dismissed_by_id])
