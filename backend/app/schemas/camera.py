from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CameraBase(BaseModel):
    name: str
    location: Optional[str] = None
    stream_url: Optional[str] = None
    is_active: bool = True


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    stream_url: Optional[str] = None
    is_active: Optional[bool] = None


class CameraOut(CameraBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True
