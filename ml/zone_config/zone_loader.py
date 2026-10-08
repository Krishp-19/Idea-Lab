"""
zone_loader.py — Zone Configuration Loader
==========================================
Reads/writes config/zones.json and provides utilities for
spatial queries (point-in-polygon, shapely polygon objects).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class ZoneConfig:
    """A single parking zone / restricted area."""
    zone_id: str
    name: str
    boundary_polygon: List[Tuple[float, float]]
    expected_angle_degrees: float
    zone_type: str  # parking_bay | fire_lane | walkway

    def to_dict(self) -> dict:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "boundary_polygon": [list(p) for p in self.boundary_polygon],
            "expected_angle_degrees": self.expected_angle_degrees,
            "zone_type": self.zone_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ZoneConfig":
        return cls(
            zone_id=d["zone_id"],
            name=d.get("name", d["zone_id"]),
            boundary_polygon=[(float(p[0]), float(p[1])) for p in d.get("boundary_polygon", [])],
            expected_angle_degrees=float(d.get("expected_angle_degrees", 90.0)),
            zone_type=d.get("zone_type", "parking_bay"),
        )


class ZoneLoader:
    """Loads, saves, and queries zone configuration."""

    @staticmethod
    def load(config_path: str) -> List[ZoneConfig]:
        """Read zones.json and return a list of ZoneConfig objects."""
        p = Path(config_path)
        if not p.exists():
            return []
        try:
            with open(p) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

        return [ZoneConfig.from_dict(z) for z in data.get("zones", [])]

    @staticmethod
    def save(zones: List[ZoneConfig], config_path: str) -> None:
        """Write zones to zones.json."""
        p = Path(config_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump({"zones": [z.to_dict() for z in zones]}, f, indent=2)

    @staticmethod
    def to_shapely_polygons(zones: List[ZoneConfig]) -> Dict[str, object]:
        """Return dict of zone_id → shapely.Polygon. Requires shapely."""
        try:
            from shapely.geometry import Polygon
        except ImportError:
            return {}
        result = {}
        for z in zones:
            if len(z.boundary_polygon) >= 3:
                result[z.zone_id] = Polygon(z.boundary_polygon)
        return result
