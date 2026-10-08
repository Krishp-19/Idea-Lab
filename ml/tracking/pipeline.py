"""
pipeline.py — End-to-End Video Processing Pipeline
===================================================
Reads video (file / webcam / single image), runs detection + tracking,
detects parking events, extracts features, and writes results to:
  - data/evidence/<timestamp>_track<id>.jpg  (annotated snapshots)
  - data/features/features.csv               (one row per parking event)

If a `db_callback` is provided (from the FastAPI backend), parking events
are also written to the database.

Usage:
    python ml/tracking/pipeline.py --source data/raw_video/myvideo.mp4
    python ml/tracking/pipeline.py --source 0 --show
    python ml/tracking/pipeline.py --source data/raw_images/frame.jpg
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[Pipeline] ERROR: opencv-python-headless not installed. Run: pip install opencv-python-headless")
    cv2 = None  # type: ignore

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# ── Project root detection ─────────────────────────────────────────────────────

def _find_project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "config" / "pipeline.yaml").exists():
            return parent
    return here.parents[2]


PROJECT_ROOT = _find_project_root()


def _load_config(config_path: Optional[str] = None) -> dict:
    candidates = [
        Path(config_path) if config_path else None,
        PROJECT_ROOT / "config" / "pipeline.yaml",
        Path("config/pipeline.yaml"),
    ]
    for c in candidates:
        if c and c.exists() and YAML_AVAILABLE:
            with open(c) as f:
                return yaml.safe_load(f) or {}
    return {}


# ── Drawing helpers ────────────────────────────────────────────────────────────

COLORS = {
    "moving":    (0, 200, 0),    # green
    "parked":    (0, 0, 220),    # red
    "risk":      (0, 140, 255),  # orange
    "violation": (0, 0, 220),    # red
    "safe":      (0, 200, 0),    # green
}


def _draw_track(frame: np.ndarray, track, label: str = "") -> None:
    """Draw bounding box + label on frame."""
    if not CV2_AVAILABLE:
        return
    x1, y1, x2, y2 = [int(v) for v in track.bbox]
    color = COLORS["parked"] if track.is_parked else COLORS["moving"]

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    parts = [f"#{track.track_id} {track.class_name}"]
    if track.is_parked:
        parts.append(f"PARKED {track.dwell_seconds:.0f}s")
    if label:
        parts.append(label.upper())
        color = COLORS.get(label, color)

    text = " | ".join(parts)
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
    cv2.putText(frame, text, (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)


def _save_evidence(frame: np.ndarray, track, evidence_dir: Path) -> Optional[str]:
    """Save annotated snapshot for a parking event. Returns relative path."""
    if not CV2_AVAILABLE:
        return None
    evidence_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{ts}_track{track.track_id}.jpg"
    fpath = evidence_dir / fname
    annotated = frame.copy()
    _draw_track(annotated, track)
    cv2.imwrite(str(fpath), annotated)
    return str(fpath.relative_to(PROJECT_ROOT)) if fpath.is_relative_to(PROJECT_ROOT) else str(fpath)


# ── VideoProcessor ─────────────────────────────────────────────────────────────

class VideoProcessor:
    """
    End-to-end video / image processor.

    Parameters
    ----------
    config : dict
        Loaded pipeline.yaml config.
    db_callback : callable, optional
        Called with (track, features, snapshot_path) for each new parking event.
        Used by the FastAPI backend to write to the database.
    """

    def __init__(
        self,
        config: Optional[dict] = None,
        db_callback: Optional[Callable] = None,
    ) -> None:
        self._config = config or _load_config()
        self._db_callback = db_callback
        self._paths_cfg = self._config.get("paths", {})
        self._output_cfg = self._config.get("output", {})

        self._evidence_dir = PROJECT_ROOT / self._paths_cfg.get("evidence_dir", "data/evidence")
        self._features_csv = PROJECT_ROOT / self._paths_cfg.get("features_csv", "data/features/features.csv")

    def process(
        self,
        source: str,
        output_video: Optional[str] = None,
        show: bool = False,
        camera_id: Optional[str] = None,
    ) -> Dict:
        """
        Process a video file, camera index, or single image.

        Returns a summary dict with counts.
        """
        # Import here to avoid circular issues
        from ml.detection.detector import TwoWheelerDetector
        from ml.tracking.tracker import ParkingTracker
        from ml.feature_engineering.features import FeatureExtractor
        from ml.classification.classifier import ParkingClassifier

        detector  = TwoWheelerDetector.get_instance()
        tracker   = ParkingTracker(self._config)
        extractor = FeatureExtractor(
            zone_config_path=str(PROJECT_ROOT / self._config.get("paths", {}).get("zone_config", "config/zones.json")),
            config=self._config,
        )
        classifier = ParkingClassifier.get_instance()

        # Detect if source is a single image
        source_path = Path(source) if not source.isdigit() else None
        is_image = source_path and source_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

        if is_image:
            return self._process_image(source, detector, extractor, classifier)

        return self._process_video(source, output_video, show, detector, tracker, extractor, classifier)

    # ── Image processing ───────────────────────────────────────────────────────

    def _process_image(self, image_path: str, detector, extractor, classifier) -> Dict:
        if not CV2_AVAILABLE:
            raise RuntimeError("cv2 required for image processing")

        frame = cv2.imread(image_path)
        if frame is None:
            raise FileNotFoundError(f"Cannot read image: {image_path}")

        detections = detector.detect_frame(frame)
        print(f"[Pipeline] Image: {len(detections)} two-wheeler(s) detected")

        results = {"source": image_path, "detections": len(detections), "parking_events": 0}

        # For images, every detection is treated as a potential parked vehicle
        from ml.tracking.tracker import TrackedVehicle
        from datetime import timezone

        for i, det in enumerate(detections):
            # Synthetic track for feature extraction
            tv = TrackedVehicle(
                track_id=i,
                bbox=det.bbox,
                class_name=det.class_name,
                confidence=det.confidence,
                is_parked=True,
                dwell_seconds=0.0,
            )
            all_tracks = [TrackedVehicle(track_id=j, bbox=d.bbox,
                                          class_name=d.class_name, confidence=d.confidence)
                          for j, d in enumerate(detections) if j != i]
            feat_row = extractor.extract(tv, frame, all_tracks)
            label_result = classifier.predict(feat_row.to_dict())
            feat_row.label = label_result.get("label", "pending")
            extractor.append_to_csv(feat_row, str(self._features_csv))

            snapshot = _save_evidence(frame, tv, self._evidence_dir)
            if self._db_callback:
                self._db_callback(tv, feat_row, snapshot, label_result)
            results["parking_events"] += 1

        return results

    # ── Video processing ───────────────────────────────────────────────────────

    def _process_video(
        self, source: str, output_video: Optional[str], show: bool,
        detector, tracker, extractor, classifier
    ) -> Dict:
        if not CV2_AVAILABLE:
            raise RuntimeError("cv2 required for video processing")

        # Open source
        cap_source = int(source) if source.isdigit() else source
        cap = cv2.VideoCapture(cap_source)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {source}")

        fps    = cap.get(cv2.CAP_PROP_FPS) or 25
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"[Pipeline] Source: {source}")
        print(f"[Pipeline] Resolution: {width}x{height} @ {fps:.1f} fps  ({total} frames)")

        # Optional output writer
        writer = None
        if output_video:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

        # State
        frames_processed   = 0
        total_detections   = 0
        parking_events     = 0
        parked_track_ids_seen: Set[int] = set()   # IDs already saved as evidence

        t_start = time.time()

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # ── Detect + Track ─────────────────────────────────────────────
                detections = detector.detect_frame(frame)
                active_tracks = tracker.update(frame, detections)
                total_detections += len(detections)
                frames_processed += 1

                # ── Process newly-parked vehicles ──────────────────────────────
                parked_tracks = [t for t in active_tracks if t.is_parked]
                for track in parked_tracks:
                    if track.track_id not in parked_track_ids_seen:
                        parked_track_ids_seen.add(track.track_id)

                        # Feature extraction
                        other_parked = [t for t in parked_tracks if t.track_id != track.track_id]
                        feat_row = extractor.extract(track, frame, other_parked)

                        # Classification
                        label_result = classifier.predict(feat_row.to_dict())
                        feat_row.label = label_result.get("label", "pending")

                        # Save evidence snapshot
                        if self._output_cfg.get("save_evidence_snapshots", True):
                            snapshot_path = _save_evidence(frame, track, self._evidence_dir)
                        else:
                            snapshot_path = None

                        # Write feature row to CSV
                        extractor.append_to_csv(feat_row, str(self._features_csv))
                        parking_events += 1

                        # Callback for DB (used by FastAPI backend)
                        if self._db_callback:
                            self._db_callback(track, feat_row, snapshot_path, label_result)

                        print(
                            f"[Pipeline] Parking event: track={track.track_id}"
                            f"  dwell={track.dwell_seconds:.0f}s"
                            f"  label={feat_row.label}"
                            f"  zone={feat_row.zone_id}"
                        )

                # ── Draw overlays ──────────────────────────────────────────────
                if show or writer:
                    annotated = frame.copy()
                    for track in active_tracks:
                        label = ""
                        # Show classification label if this track has been processed
                        if track.track_id in parked_track_ids_seen:
                            # Re-classify from saved CSV would be expensive; just show "parked"
                            label = "parked"
                        _draw_track(annotated, track, label)

                    # Stats overlay
                    cv2.putText(annotated,
                                f"Frame {frames_processed}  Detected: {len(detections)}  Parked events: {parking_events}",
                                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                    if writer:
                        writer.write(annotated)
                    if show:
                        cv2.imshow("Two-Wheeler Parking Detection", annotated)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            print("[Pipeline] Quit requested")
                            break

                # Progress report every 100 frames
                if frames_processed % 100 == 0:
                    elapsed = time.time() - t_start
                    speed = frames_processed / elapsed if elapsed > 0 else 0
                    pct = (frames_processed / total * 100) if total > 0 else 0
                    print(f"[Pipeline] {frames_processed}/{total} frames ({pct:.0f}%)  {speed:.1f} fps")

        except KeyboardInterrupt:
            print("[Pipeline] Interrupted")
        finally:
            cap.release()
            if writer:
                writer.release()
            if show and CV2_AVAILABLE:
                cv2.destroyAllWindows()

        elapsed = time.time() - t_start
        summary = {
            "source": source,
            "frames_processed": frames_processed,
            "total_detections": total_detections,
            "parking_events": parking_events,
            "elapsed_seconds": round(elapsed, 1),
            "avg_fps": round(frames_processed / elapsed, 1) if elapsed > 0 else 0,
            "features_csv": str(self._features_csv),
        }
        print("\n[Pipeline] Summary:")
        for k, v in summary.items():
            print(f"  {k}: {v}")
        return summary


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run two-wheeler parking detection pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Video file path, image file path, or camera index (e.g. 0)",
    )
    parser.add_argument("--output-video", default=None, help="Save annotated video to this path")
    parser.add_argument("--show", action="store_true", help="Display video window")
    parser.add_argument("--config", default=None, help="Path to pipeline.yaml")
    parser.add_argument("--device", default=None, help="Override inference device (cpu/cuda)")
    args = parser.parse_args()

    if args.device:
        os.environ["DEVICE"] = args.device

    config = _load_config(args.config)
    processor = VideoProcessor(config=config)
    processor.process(
        source=args.source,
        output_video=args.output_video,
        show=args.show,
    )


if __name__ == "__main__":
    main()
