import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import User
from app.models.zone import Zone

settings = get_settings()


def run_seed(db: Session) -> None:
    # 1. Seed initial admin user if no users exist
    admin_user = db.scalar(select(User).where(User.username == settings.default_admin_username))
    if not admin_user:
        admin = User(
            username=settings.default_admin_username,
            hashed_password=hash_password(settings.default_admin_password),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"[Seed] Created default admin user: {settings.default_admin_username}")

    # 2. Sync zones from config/zones.json if present
    sync_zones_from_config(db)


def sync_zones_from_config(db: Session) -> None:
    cfg_path = Path(settings.zone_config_path)
    if not cfg_path.is_absolute():
        cfg_path = Path(__file__).resolve().parents[3] / cfg_path

    if not cfg_path.exists():
        return

    try:
        with open(cfg_path, "r") as f:
            data = json.load(f)
        zones_data = data.get("zones", [])
        for z in zones_data:
            zone_id = z.get("zone_id")
            if not zone_id:
                continue
            existing = db.scalar(select(Zone).where(Zone.zone_id == zone_id))
            if existing:
                existing.name = z.get("name", existing.name)
                existing.boundary_polygon = z.get("boundary_polygon", existing.boundary_polygon)
                existing.expected_angle_degrees = float(z.get("expected_angle_degrees", existing.expected_angle_degrees))
                existing.zone_type = z.get("zone_type", existing.zone_type)
            else:
                new_zone = Zone(
                    zone_id=zone_id,
                    name=z.get("name", zone_id),
                    boundary_polygon=z.get("boundary_polygon", []),
                    expected_angle_degrees=float(z.get("expected_angle_degrees", 90.0)),
                    zone_type=z.get("zone_type", "parking_bay"),
                )
                db.add(new_zone)
        db.commit()
    except Exception as e:
        print(f"[Seed] Warning: Failed to sync zones from config: {e}")
