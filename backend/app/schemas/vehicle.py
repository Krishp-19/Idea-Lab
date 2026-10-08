from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class VehicleOut(BaseModel):
    id: str
    track_id: int
    camera_id: Optional[str] = None
    class_name: str
    thumbnail_path: Optional[str] = None
    first_seen: datetime
    last_seen: datetime

    class Config:
        from_attributes = True
