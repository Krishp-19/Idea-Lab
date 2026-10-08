import json
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from app.api.deps import DbSession
from app.core.config import get_settings
from app.db.seed import sync_zones_from_config
from app.models.zone import Zone
from app.schemas.common import MessageResponse
from app.schemas.zone import ZoneCreate, ZoneOut, ZoneUpdate

router = APIRouter()
settings = get_settings()


def _save_zones_to_json(db: DbSession) -> None:
    zones = db.scalars(select(Zone)).all()
    payload = {
        "zones": [
            {
                "zone_id": z.zone_id,
                "name": z.name,
                "boundary_polygon": z.boundary_polygon,
                "expected_angle_degrees": z.expected_angle_degrees,
                "zone_type": z.zone_type,
            }
            for z in zones
        ]
    }
    cfg_path = Path(settings.zone_config_path)
    if not cfg_path.is_absolute():
        cfg_path = Path(__file__).resolve().parents[4] / cfg_path
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_path, "w") as f:
        json.dump(payload, f, indent=2)


@router.get("", response_model=List[ZoneOut])
def list_zones(db: DbSession) -> List[ZoneOut]:
    zones = db.scalars(select(Zone).order_by(Zone.created_at.asc())).all()
    return [ZoneOut.model_validate(z) for z in zones]


@router.post("", response_model=ZoneOut, status_code=status.HTTP_201_CREATED)
def create_or_update_zone(payload: ZoneCreate, db: DbSession) -> ZoneOut:
    existing = db.scalar(select(Zone).where(Zone.zone_id == payload.zone_id))
    if existing:
        for k, v in payload.model_dump().items():
            setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        _save_zones_to_json(db)
        return ZoneOut.model_validate(existing)

    zone = Zone(**payload.model_dump())
    db.add(zone)
    db.commit()
    db.refresh(zone)
    _save_zones_to_json(db)
    return ZoneOut.model_validate(zone)


@router.delete("/{zone_id}", response_model=MessageResponse)
def delete_zone(zone_id: str, db: DbSession) -> MessageResponse:
    zone = db.scalar(select(Zone).where(Zone.zone_id == zone_id))
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    db.delete(zone)
    db.commit()
    _save_zones_to_json(db)
    return MessageResponse(message=f"Zone {zone_id} deleted successfully")


@router.post("/sync", response_model=MessageResponse)
def sync_zones(db: DbSession) -> MessageResponse:
    sync_zones_from_config(db)
    return MessageResponse(message="Zones synchronized from config file")
