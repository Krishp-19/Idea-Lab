"""
tracker.py — IoU-based Multi-Object Tracker with Dwell-Time Filtering
======================================================================
Tracks two-wheelers across video frames using an IoU-based Hungarian
algorithm matcher (no extra model files required). Optionally uses
deep-sort-realtime for better re-identification.

Classifies each track as "parked" when:
  - Centroid has moved < stationary_px_threshold pixels on average
    over the last `stationary_frames` frames (i.e. it's stationary)
  - AND it has been stationary for >= dwell_time_seconds seconds
"""

from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    from scipy.optimize import linear_sum_assignment
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("[ParkingTracker] WARNING: scipy not installed — using greedy IoU matching.")

try:
    from deep_sort_realtime.deepsort_tracker import DeepSort
    DEEPSORT_AVAILABLE = True
except ImportError:
    DEEPSORT_AVAILABLE = False

from ml.detection.detector import Detection


# ── TrackedVehicle dataclass ───────────────────────────────────────────────────

@dataclass
class TrackedVehicle:
    """Rich track object combining spatial state and dwell-time logic."""
    track_id: int
    bbox: Tuple[float, float, float, float]   # x1, y1, x2, y2
    class_name: str
    confidence: float
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    centroid_history: deque = field(default_factory=lambda: deque(maxlen=60))
    # Stationarity window (last N frames)
    _stationary_history: deque = field(default_factory=lambda: deque(maxlen=30))
    # Tracks when the vehicle first became "stationary"
    _became_stationary_at: Optional[datetime] = field(default=None)
    is_parked: bool = False
    dwell_seconds: float = 0.0

    def __post_init__(self):
        cx, cy = self._centroid(self.bbox)
        self.centroid_history.append((cx, cy))

    @staticmethod
    def _centroid(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
        return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)

    @property
    def center(self) -> Tuple[float, float]:
        if self.centroid_history:
            return self.centroid_history[-1]
        return self._centroid(self.bbox)

    @property
    def velocity(self) -> Optional[Tuple[float, float]]:
        """Approximate velocity from last two centroids (pixels/frame)."""
        if len(self.centroid_history) < 2:
            return None
        p1, p2 = self.centroid_history[-2], self.centroid_history[-1]
        return (p2[0] - p1[0], p2[1] - p1[1])

    def update(self, bbox: Tuple, class_name: str, confidence: float,
               stationary_px_threshold: float) -> None:
        """Update track with a new detection."""
        prev_center = self.center
        self.bbox = bbox
        self.class_name = class_name
        self.confidence = confidence
        self.last_seen = datetime.now(timezone.utc)

        new_center = self._centroid(bbox)
        self.centroid_history.append(new_center)

        # Track pixel movement for stationarity
        movement = _distance(prev_center, new_center)
        self._stationary_history.append(movement)

    def check_dwell(self, stationary_px_threshold: float, dwell_threshold_seconds: float) -> None:
        """Update is_parked and dwell_seconds based on movement history."""
        if len(self._stationary_history) == 0:
            return

        avg_movement = float(np.mean(list(self._stationary_history)))
        currently_stationary = avg_movement < stationary_px_threshold

        if currently_stationary:
            if self._became_stationary_at is None:
                self._became_stationary_at = datetime.now(timezone.utc)
            elapsed = (datetime.now(timezone.utc) - self._became_stationary_at).total_seconds()
            self.dwell_seconds = elapsed
            self.is_parked = elapsed >= dwell_threshold_seconds
        else:
            # Vehicle is moving — reset stationarity clock
            self._became_stationary_at = None
            self.dwell_seconds = 0.0
            self.is_parked = False

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "bbox": list(self.bbox),
            "class_name": self.class_name,
            "confidence": round(self.confidence, 3),
            "center": list(self.center),
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "dwell_seconds": round(self.dwell_seconds, 1),
            "is_parked": self.is_parked,
        }


# ── IoU helpers ────────────────────────────────────────────────────────────────

def _iou(boxA: Tuple, boxB: Tuple) -> float:
    """Compute IoU between two boxes (x1,y1,x2,y2)."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    if inter == 0:
        return 0.0
    areaA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    areaB = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    return inter / (areaA + areaB - inter + 1e-9)


def _distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return float(np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2))


# ── ParkingTracker ─────────────────────────────────────────────────────────────

class ParkingTracker:
    """
    Multi-object tracker with dwell-time-based parking classification.

    Primary: IoU-based Hungarian algorithm (no extra deps).
    Optional: deep-sort-realtime for appearance-based re-ID (pip install deep-sort-realtime).
    """

    def __init__(self, config: dict) -> None:
        tracking_cfg = config.get("tracking", {})
        dwell_cfg    = config.get("dwell_time", {})

        self._max_age: int           = int(tracking_cfg.get("max_age", 30))
        self._min_hits: int          = int(tracking_cfg.get("min_hits", 3))
        self._iou_threshold: float   = float(tracking_cfg.get("iou_threshold", 0.3))
        self._tracker_type: str      = tracking_cfg.get("tracker_type", "iou")

        self._dwell_threshold: float = float(
            os.environ.get("DWELL_TIME_SECONDS",
                           dwell_cfg.get("threshold_seconds", 30))
        )
        self._stationary_px: float  = float(
            os.environ.get("STATIONARY_PX_THRESHOLD",
                           dwell_cfg.get("stationary_px_threshold", 15))
        )
        self._stationary_frames: int = int(dwell_cfg.get("stationary_frames", 10))

        self._tracks: Dict[int, TrackedVehicle] = {}
        self._ages: Dict[int, int] = {}          # frames since last matched
        self._hit_counts: Dict[int, int] = {}    # total detections matched
        self._next_id: int = 1

        # Optional DeepSORT
        self._deepsort = None
        if DEEPSORT_AVAILABLE and self._tracker_type == "deepsort":
            try:
                self._deepsort = DeepSort(
                    max_age=self._max_age,
                    n_init=self._min_hits,
                    nms_max_overlap=1.0,
                    max_cosine_distance=0.4,
                    nn_budget=None,
                    bgr=True,
                )
                print("[ParkingTracker] Using deep-sort-realtime tracker")
            except Exception as exc:
                print(f"[ParkingTracker] DeepSORT init failed ({exc}), falling back to IoU tracker")
                self._deepsort = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def update(self, frame: np.ndarray, detections: List[Detection]) -> List[TrackedVehicle]:
        """
        Feed new detections, return all active confirmed tracks with dwell state.
        """
        if self._deepsort is not None:
            return self._update_deepsort(frame, detections)
        return self._update_iou(detections)

    def get_parked(self) -> List[TrackedVehicle]:
        """Return only tracks classified as parked."""
        return [t for t in self._tracks.values() if t.is_parked]

    def reset(self) -> None:
        self._tracks.clear()
        self._ages.clear()
        self._hit_counts.clear()
        self._next_id = 1

    # ── IoU tracker ────────────────────────────────────────────────────────────

    def _update_iou(self, detections: List[Detection]) -> List[TrackedVehicle]:
        """Hungarian IoU matching."""
        track_ids = list(self._tracks.keys())
        det_bboxes = [d.bbox for d in detections]

        # Age all tracks
        for tid in track_ids:
            self._ages[tid] = self._ages.get(tid, 0) + 1

        if track_ids and det_bboxes:
            # Build IoU cost matrix
            cost_matrix = np.zeros((len(track_ids), len(det_bboxes)), dtype=np.float64)
            for ti, tid in enumerate(track_ids):
                for di, det_bbox in enumerate(det_bboxes):
                    cost_matrix[ti, di] = 1.0 - _iou(self._tracks[tid].bbox, det_bbox)

            if SCIPY_AVAILABLE:
                row_ind, col_ind = linear_sum_assignment(cost_matrix)
                matches = [(row_ind[i], col_ind[i]) for i in range(len(row_ind))
                           if cost_matrix[row_ind[i], col_ind[i]] < (1 - self._iou_threshold)]
            else:
                # Greedy fallback
                matches = self._greedy_match(cost_matrix)

            matched_track_idxs = {m[0] for m in matches}
            matched_det_idxs   = {m[1] for m in matches}

            # Update matched tracks
            for ti, di in matches:
                tid = track_ids[ti]
                det = detections[di]
                self._tracks[tid].update(det.bbox, det.class_name, det.confidence,
                                         self._stationary_px)
                self._ages[tid] = 0
                self._hit_counts[tid] = self._hit_counts.get(tid, 0) + 1

            # Create new tracks for unmatched detections
            for di, det in enumerate(detections):
                if di not in matched_det_idxs:
                    self._create_track(det)

        elif det_bboxes:
            for det in detections:
                self._create_track(det)

        # Remove stale tracks
        for tid in list(self._tracks.keys()):
            if self._ages.get(tid, 0) > self._max_age:
                del self._tracks[tid]
                self._ages.pop(tid, None)
                self._hit_counts.pop(tid, None)

        # Update dwell-time for all tracks and return confirmed ones
        active: List[TrackedVehicle] = []
        for tid, track in self._tracks.items():
            track.check_dwell(self._stationary_px, self._dwell_threshold)
            if self._hit_counts.get(tid, 0) >= self._min_hits:
                active.append(track)

        return active

    def _create_track(self, det: Detection) -> None:
        tid = self._next_id
        self._next_id += 1
        self._tracks[tid] = TrackedVehicle(
            track_id=tid,
            bbox=det.bbox,
            class_name=det.class_name,
            confidence=det.confidence,
        )
        self._ages[tid] = 0
        self._hit_counts[tid] = 1

    @staticmethod
    def _greedy_match(cost_matrix: np.ndarray) -> List[Tuple[int, int]]:
        """Greedy IoU matching as fallback when scipy unavailable."""
        matches = []
        used_rows, used_cols = set(), set()
        flat_indices = np.argsort(cost_matrix.ravel())
        for idx in flat_indices:
            row, col = divmod(int(idx), cost_matrix.shape[1])
            if row in used_rows or col in used_cols:
                continue
            if cost_matrix[row, col] < 0.7:  # IoU > 0.3
                matches.append((row, col))
                used_rows.add(row)
                used_cols.add(col)
        return matches

    # ── DeepSORT tracker ───────────────────────────────────────────────────────

    def _update_deepsort(self, frame: np.ndarray, detections: List[Detection]) -> List[TrackedVehicle]:
        """Use deep-sort-realtime when available."""
        raw = [
            (list(det.to_tlwh()), det.confidence, det.class_name)
            for det in detections
        ]
        try:
            ds_tracks = self._deepsort.update_tracks(raw, frame=frame)
        except Exception as exc:
            print(f"[ParkingTracker] DeepSORT error ({exc}), falling back to IoU")
            return self._update_iou(detections)

        active: List[TrackedVehicle] = []
        seen_ids = set()
        for ds_track in ds_tracks:
            if not ds_track.is_confirmed():
                continue
            tid = ds_track.track_id
            seen_ids.add(tid)
            ltrb = ds_track.to_ltrb()
            bbox = (ltrb[0], ltrb[1], ltrb[2], ltrb[3])
            cls   = ds_track.get_det_class() or "motorcycle"
            conf  = ds_track.get_det_conf() or 0.5

            if tid not in self._tracks:
                self._tracks[tid] = TrackedVehicle(
                    track_id=tid, bbox=bbox, class_name=cls, confidence=conf
                )
                self._hit_counts[tid] = 1
            else:
                self._tracks[tid].update(bbox, cls, conf, self._stationary_px)
                self._hit_counts[tid] = self._hit_counts.get(tid, 0) + 1

            self._tracks[tid].check_dwell(self._stationary_px, self._dwell_threshold)
            active.append(self._tracks[tid])

        # Prune lost tracks
        for tid in list(self._tracks.keys()):
            if tid not in seen_ids:
                del self._tracks[tid]
                self._hit_counts.pop(tid, None)

        return active
