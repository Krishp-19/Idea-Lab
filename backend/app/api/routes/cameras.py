from typing import List
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from app.api.deps import DbSession
from app.models.camera import Camera
from app.schemas.camera import CameraCreate, CameraOut, CameraUpdate
from app.schemas.common import MessageResponse

router = APIRouter()


@router.get("", response_model=List[CameraOut])
def list_cameras(db: DbSession) -> List[CameraOut]:
    cams = db.scalars(select(Camera).order_by(Camera.created_at.desc())).all()
    return [CameraOut.model_validate(c) for c in cams]


@router.post("", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
def create_camera(payload: CameraCreate, db: DbSession) -> CameraOut:
    cam = Camera(**payload.model_dump())
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return CameraOut.model_validate(cam)


@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: str, payload: CameraUpdate, db: DbSession) -> CameraOut:
    cam = db.scalar(select(Camera).where(Camera.id == camera_id))
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cam, k, v)

    db.commit()
    db.refresh(cam)
    return CameraOut.model_validate(cam)
