"""
geometry.py — Spatial Geometry Utilities for Parking Feature Extraction
=======================================================================
All geometry operations needed for feature engineering:
  - Point-in-polygon tests
  - Polygon boundary distances
  - Bbox orientation angle (via PCA on corners)
  - IoU and bbox overlap fraction
  - Nearest-neighbor distance
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np

try:
    from shapely.geometry import Point, Polygon as SPolygon, box as sbox
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False


Polygon = List[Tuple[float, float]]   # type alias


# ── Point-in-polygon ───────────────────────────────────────────────────────────

def point_in_polygon(point: Tuple[float, float], polygon: Polygon) -> bool:
    """
    Test if a 2-D point lies inside a polygon.
    Uses shapely if available; falls back to ray-casting.
    """
    if len(polygon) < 3:
        return False

    if SHAPELY_AVAILABLE:
        try:
            return SPolygon(polygon).contains(Point(point))
        except Exception:
            pass

    # Ray-casting fallback
    x, y = point
    n = len(polygon)
    inside = False
    px, py = polygon[-1]
    for qx, qy in polygon:
        if ((py > y) != (qy > y)) and (x < (qx - px) * (y - py) / (qy - py + 1e-12) + px):
            inside = not inside
        px, py = qx, qy
    return inside


# ── Polygon distance ───────────────────────────────────────────────────────────

def polygon_distance(point: Tuple[float, float], polygon: Polygon,
                     px_per_meter: float = 1.0) -> float:
    """
    Distance from a point to the nearest polygon edge, converted to metres.
    Returns 0.0 if the point is inside the polygon.
    """
    if len(polygon) < 3:
        return float("inf")

    if point_in_polygon(point, polygon):
        return 0.0

    if SHAPELY_AVAILABLE:
        try:
            dist_px = SPolygon(polygon).exterior.distance(Point(point))
            return dist_px / px_per_meter
        except Exception:
            pass

    # Fallback: minimum distance to any edge
    x0, y0 = point
    min_dist = float("inf")
    n = len(polygon)
    for i in range(n):
        ax, ay = polygon[i]
        bx, by = polygon[(i + 1) % n]
        # Distance from (x0, y0) to segment (a, b)
        dx, dy = bx - ax, by - ay
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq < 1e-12:
            d = math.hypot(x0 - ax, y0 - ay)
        else:
            t = max(0.0, min(1.0, ((x0 - ax) * dx + (y0 - ay) * dy) / seg_len_sq))
            cx_, cy_ = ax + t * dx, ay + t * dy
            d = math.hypot(x0 - cx_, y0 - cy_)
        min_dist = min(min_dist, d)

    return min_dist / px_per_meter


# ── Bbox orientation ───────────────────────────────────────────────────────────

def bbox_orientation_angle(bbox: Tuple[float, float, float, float]) -> float:
    """
    Estimate the orientation angle (degrees) of a bounding box.

    For a vehicle standing upright in a bay:
      - Landscape (wider than tall) → angle ≈ 0°
      - Portrait (taller than wide) → angle ≈ 90°

    This uses the aspect-ratio convention:
      angle = arctan(height / width) * (180 / pi)

    For two-wheelers, when parked perpendicular to the road,
    the bounding box is tall (portrait), giving angle ≈ 90°.
    """
    x1, y1, x2, y2 = bbox
    w = abs(x2 - x1)
    h = abs(y2 - y1)
    if w < 1e-6:
        return 90.0
    return math.degrees(math.atan2(h, w))


# ── Bbox overlap ───────────────────────────────────────────────────────────────

def compute_iou(boxA: Tuple, boxB: Tuple) -> float:
    """Standard IoU between two (x1, y1, x2, y2) boxes."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    inter = max(0.0, xB - xA) * max(0.0, yB - yA)
    if inter == 0:
        return 0.0
    areaA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    areaB = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    return inter / (areaA + areaB - inter + 1e-9)


def bbox_overlap_fraction(bbox1: Tuple, bbox2: Tuple) -> float:
    """
    Fraction of bbox1 that overlaps with bbox2.
    Returns 0–1, where 1 means bbox1 is entirely inside bbox2.
    """
    xA = max(bbox1[0], bbox2[0])
    yA = max(bbox1[1], bbox2[1])
    xB = min(bbox1[2], bbox2[2])
    yB = min(bbox1[3], bbox2[3])
    inter = max(0.0, xB - xA) * max(0.0, yB - yA)
    area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
    if area1 < 1e-6:
        return 0.0
    return inter / area1


def bbox_overlaps_polygon(bbox: Tuple, polygon: Polygon,
                           threshold: float = 0.05) -> bool:
    """
    True if at least `threshold` fraction of bbox overlaps the polygon.
    Uses shapely if available; falls back to centroid-in-polygon.
    """
    if SHAPELY_AVAILABLE:
        try:
            x1, y1, x2, y2 = bbox
            b = sbox(x1, y1, x2, y2)
            poly = SPolygon(polygon)
            inter = b.intersection(poly).area
            frac = inter / b.area if b.area > 0 else 0
            return frac >= threshold
        except Exception:
            pass
    # Fallback: centroid test
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    return point_in_polygon((cx, cy), polygon)


# ── Centroid helpers ───────────────────────────────────────────────────────────

def centroid_of_bbox(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def nearest_neighbor_distance(
    point: Tuple[float, float],
    other_points: List[Tuple[float, float]],
) -> float:
    """Euclidean distance to the nearest point in the list. Returns inf if empty."""
    if not other_points:
        return float("inf")
    dists = [math.hypot(point[0] - p[0], point[1] - p[1]) for p in other_points]
    return min(dists)
