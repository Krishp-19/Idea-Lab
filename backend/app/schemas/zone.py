from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel


class ZoneBase(BaseModel):
    zone_id: str
    name: str
    boundary_polygon: List[Any]
    expected_angle_degrees: float = 90.0
    zone_type: str = "parking_bay"  # parking_bay | fire_lane | walkway
    camera_id: Optional[str] = None


class ZoneCreate(ZoneBase):
    pass


class ZoneUpdate(BaseModel):
    name: Optional[str] = None
    boundary_polygon: Optional[List[Any]] = None
    expected_angle_degrees: Optional[float] = None
    zone_type: Optional[str] = None
    camera_id: Optional[str] = None


class ZoneOut(ZoneBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True
