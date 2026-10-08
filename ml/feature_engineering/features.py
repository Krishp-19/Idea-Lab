"""
features.py — Parking Feature Extractor
========================================
Computes a rich feature vector for each parked two-wheeler,
describing its spatial relationship to parking zones.

Features produced:
  - zone_id / zone_name / zone_type         which zone (if any)
  - inside_zone                             centroid inside a parking bay?
  - distance_to_nearest_zone_m              metres to nearest bay boundary
  - orientation_delta_deg                   |vehicle angle - expected angle|
  - nearest_neighbor_dist_px                pixels to nearest other parked vehicle
  - obstructs_walkway / obstructs_fire_lane bbox overlaps restricted areas?
  - bay_sequence_violation                  skipped an empty bay?
  - dwell_seconds / confidence              from tracker / detector
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from ml.feature_engineering.geometry import (
    bbox_orientation_angle,
    bbox_overlaps_polygon,
    centroid_of_bbox,
    nearest_neighbor_distance,
    point_in_polygon,
    polygon_distance,
)
from ml.zone_config.zone_loader import ZoneConfig, ZoneLoader


# ── Feature row ────────────────────────────────────────────────────────────────

@dataclass
class ParkingFeatureRow:
    """One row in the parking features CSV — one per parking event."""
    # Identity
    track_id: int = 0
    timestamp: str = ""

    # Zone context
    zone_id: str = "none"
    zone_name: str = "none"
    zone_type: str = "none"

    # Spatial features
    inside_zone: bool = False
    distance_to_nearest_zone_m: float = 0.0
    orientation_delta_deg: float = 0.0
    nearest_neighbor_dist_px: float = 0.0

    # Obstruction flags
    obstructs_walkway: bool = False
    obstructs_fire_lane: bool = False

    # Sequence feature
    bay_sequence_violation: bool = False

    # Temporal / detection
    dwell_seconds: float = 0.0
    confidence: float = 0.0

    # Bounding box (for record-keeping, not used as features in classifiers)
    bbox_x1: float = 0.0
    bbox_y1: float = 0.0
    bbox_x2: float = 0.0
    bbox_y2: float = 0.0

    # Label (filled in manually for classifier training)
    label: str = ""

    # ── Helpers ────────────────────────────────────────────────────────────────

    @classmethod
    def csv_header(cls) -> List[str]:
        return [f.name for f in fields(cls)]

    def to_dict(self) -> dict:
        return {
            f.name: (1 if isinstance(getattr(self, f.name), bool) and getattr(self, f.name)
                     else 0 if isinstance(getattr(self, f.name), bool)
                     else getattr(self, f.name))
            for f in fields(self)
        }

    def feature_vector(self) -> dict:
        """
        Only the numeric features used by classifiers (no IDs, no bbox, no label).
        Booleans are converted to int.
        """
        numeric_fields = {
            "inside_zone", "distance_to_nearest_zone_m", "orientation_delta_deg",
            "nearest_neighbor_dist_px", "obstructs_walkway", "obstructs_fire_lane",
            "bay_sequence_violation", "dwell_seconds", "confidence",
        }
        result = {}
        for f in fields(self):
            if f.name not in numeric_fields:
                continue
            v = getattr(self, f.name)
            result[f.name] = int(v) if isinstance(v, bool) else float(v)
        return result


# ── Feature extractor ──────────────────────────────────────────────────────────

class FeatureExtractor:
    """
    Computes a ParkingFeatureRow for each parked vehicle.

    Parameters
    ----------
    zone_config_path : str
        Path to config/zones.json
    config : dict
        Loaded pipeline.yaml config dict
    """

    def __init__(self, zone_config_path: str, config: dict) -> None:
        self._zone_config_path = zone_config_path
        self._zones: List[ZoneConfig] = ZoneLoader.load(zone_config_path)
        fe_cfg = config.get("feature_engineering", {})
        self._px_per_meter: float = float(
            os.environ.get("PX_PER_METER", fe_cfg.get("px_per_meter", 50.0))
        )
        self._walkway_overlap_threshold: float = float(
            fe_cfg.get("walkway_overlap_threshold", 0.05)
        )

        # Split zones by type for efficient lookup
        self._parking_bays   = [z for z in self._zones if z.zone_type == "parking_bay"]
        self._fire_lanes     = [z for z in self._zones if z.zone_type == "fire_lane"]
        self._walkways       = [z for z in self._zones if z.zone_type == "walkway"]

    def reload_zones(self) -> None:
        """Reload zones from disk (call after zone_drawer updates the config)."""
        self._zones    = ZoneLoader.load(self._zone_config_path)
        self._parking_bays = [z for z in self._zones if z.zone_type == "parking_bay"]
        self._fire_lanes   = [z for z in self._zones if z.zone_type == "fire_lane"]
        self._walkways     = [z for z in self._zones if z.zone_type == "walkway"]

    def extract(
        self,
        tracked_vehicle,   # TrackedVehicle
        frame,             # np.ndarray (unused for geometry, kept for future expansion)
        all_parked_vehicles: list,  # List[TrackedVehicle]
    ) -> ParkingFeatureRow:
        """
        Extract all features for a parked vehicle.

        Parameters
        ----------
        tracked_vehicle : TrackedVehicle
            The parked vehicle to extract features for.
        frame : np.ndarray
            Current video frame (not used in geometry; reserved for future use).
        all_parked_vehicles : List[TrackedVehicle]
            All currently-parked vehicles EXCEPT tracked_vehicle (for neighbor distance).
        """
        bbox      = tracked_vehicle.bbox
        centroid  = centroid_of_bbox(bbox)
        timestamp = datetime.now(timezone.utc).isoformat()

        row = ParkingFeatureRow(
            track_id=tracked_vehicle.track_id,
            timestamp=timestamp,
            dwell_seconds=float(getattr(tracked_vehicle, "dwell_seconds", 0.0)),
            confidence=float(getattr(tracked_vehicle, "confidence", 0.0)),
            bbox_x1=float(bbox[0]),
            bbox_y1=float(bbox[1]),
            bbox_x2=float(bbox[2]),
            bbox_y2=float(bbox[3]),
        )

        # ── Zone membership ────────────────────────────────────────────────────
        matched_zone: Optional[ZoneConfig] = None
        for zone in self._parking_bays:
            if point_in_polygon(centroid, zone.boundary_polygon):
                matched_zone = zone
                break

        row.inside_zone = matched_zone is not None

        if matched_zone:
            row.zone_id   = matched_zone.zone_id
            row.zone_name = matched_zone.name
            row.zone_type = matched_zone.zone_type
            row.distance_to_nearest_zone_m = 0.0
        else:
            # Find nearest parking bay
            min_dist = float("inf")
            nearest: Optional[ZoneConfig] = None
            for zone in self._parking_bays:
                d = polygon_distance(centroid, zone.boundary_polygon, self._px_per_meter)
                if d < min_dist:
                    min_dist = d
                    nearest = zone
            if nearest:
                row.zone_id   = nearest.zone_id
                row.zone_name = nearest.name
                row.zone_type = nearest.zone_type
                row.distance_to_nearest_zone_m = round(min_dist, 3)

        # ── Orientation delta ──────────────────────────────────────────────────
        vehicle_angle = bbox_orientation_angle(bbox)
        expected_angle = 90.0  # default: perpendicular
        if matched_zone:
            expected_angle = matched_zone.expected_angle_degrees
        elif row.zone_id != "none":
            # Look up the zone we matched by ID for expected angle
            for z in self._zones:
                if z.zone_id == row.zone_id:
                    expected_angle = z.expected_angle_degrees
                    break
        row.orientation_delta_deg = round(abs(vehicle_angle - expected_angle), 2)

        # ── Nearest neighbor ───────────────────────────────────────────────────
        other_centroids = [
            centroid_of_bbox(v.bbox)
            for v in all_parked_vehicles
            if v.track_id != tracked_vehicle.track_id
        ]
        row.nearest_neighbor_dist_px = round(
            nearest_neighbor_distance(centroid, other_centroids), 2
        )

        # ── Obstruction checks ─────────────────────────────────────────────────
        for wz in self._walkways:
            if bbox_overlaps_polygon(bbox, wz.boundary_polygon, self._walkway_overlap_threshold):
                row.obstructs_walkway = True
                break

        for fl in self._fire_lanes:
            if bbox_overlaps_polygon(bbox, fl.boundary_polygon, self._walkway_overlap_threshold):
                row.obstructs_fire_lane = True
                break

        # ── Bay sequence violation ─────────────────────────────────────────────
        # True if the vehicle is inside a bay but there was an earlier empty bay
        # of the same type whose polygon has no other parked vehicle's centroid.
        if row.inside_zone and matched_zone:
            parked_centroids = {centroid_of_bbox(v.bbox) for v in all_parked_vehicles}
            for zone in self._parking_bays:
                if zone.zone_id == matched_zone.zone_id:
                    break  # only check bays that come "before" in list order
                # Is this bay empty?
                bay_occupied = any(
                    point_in_polygon(c, zone.boundary_polygon)
                    for c in parked_centroids
                )
                if not bay_occupied:
                    row.bay_sequence_violation = True
                    break

        return row

    # ── CSV writer ─────────────────────────────────────────────────────────────

    @staticmethod
    def append_to_csv(row: ParkingFeatureRow, csv_path: str) -> None:
        """Append a single feature row to the CSV. Creates the file with header if new."""
        p = Path(csv_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        write_header = not p.exists() or p.stat().st_size == 0
        with open(p, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=ParkingFeatureRow.csv_header())
            if write_header:
                writer.writeheader()
            # Write raw row (booleans as True/False strings for readability)
            raw_row = {}
            for fld in fields(row):
                v = getattr(row, fld.name)
                raw_row[fld.name] = v
            writer.writerow(raw_row)
