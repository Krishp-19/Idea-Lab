"""
detector.py — Two-Wheeler YOLOv8 Detector
==========================================
Thread-safe singleton that runs YOLOv8 inference and filters results
to only motorcycle and bicycle classes.

Usage:
    detector = TwoWheelerDetector.get_instance()
    detections = detector.detect_frame(frame)   # BGR numpy array
    detections = detector.detect_image("path/to/image.jpg")

CLI test:
    python ml/detection/detector.py path/to/image.jpg
"""

from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# ── Lazy imports (not required at import time) ─────────────────────────────────
try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    YOLO = None  # type: ignore

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None  # type: ignore

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# ── Locate project root ────────────────────────────────────────────────────────

def _find_project_root() -> Path:
    """Walk up from this file until we find config/pipeline.yaml."""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "config" / "pipeline.yaml").exists():
            return parent
    # Fallback: three levels up (ml/detection/detector.py → project root)
    return here.parents[2]


PROJECT_ROOT = _find_project_root()


# ── Config loader ──────────────────────────────────────────────────────────────

def _load_pipeline_config() -> dict:
    """Load config/pipeline.yaml; fall back to sensible defaults."""
    config_path_env = os.environ.get("PIPELINE_CONFIG_PATH", "")
    candidates = [
        Path(config_path_env) if config_path_env else None,
        PROJECT_ROOT / "config" / "pipeline.yaml",
        Path("config/pipeline.yaml"),
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            if YAML_AVAILABLE:
                with open(candidate) as f:
                    return yaml.safe_load(f) or {}
    return {}


# ── Detection dataclass ────────────────────────────────────────────────────────

@dataclass
class Detection:
    """A single two-wheeler detection from YOLO inference."""
    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2 (absolute pixels)
    confidence: float
    class_id: int
    class_name: str

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]

    @property
    def center(self) -> Tuple[float, float]:
        return (
            (self.bbox[0] + self.bbox[2]) / 2,
            (self.bbox[1] + self.bbox[3]) / 2,
        )

    def to_tlwh(self) -> Tuple[float, float, float, float]:
        """Convert to (top, left, width, height) — used by DeepSORT."""
        x1, y1, x2, y2 = self.bbox
        return (x1, y1, x2 - x1, y2 - y1)

    def to_xywh(self) -> List[float]:
        """[x_center, y_center, width, height] in absolute pixels."""
        cx, cy = self.center
        return [cx, cy, self.width, self.height]

    def to_dict(self) -> dict:
        return {
            "bbox": list(self.bbox),
            "confidence": round(self.confidence, 4),
            "class_id": self.class_id,
            "class_name": self.class_name,
            "center": list(self.center),
        }


# ── Detector ───────────────────────────────────────────────────────────────────

# COCO class names for two-wheelers
TWO_WHEELER_CLASSES = {"motorcycle", "bicycle"}


class TwoWheelerDetector:
    """
    Thread-safe YOLOv8 singleton for two-wheeler detection.

    Only motorcycle and bicycle detections are returned; all other
    YOLO classes are silently filtered out.
    """

    _instance: Optional["TwoWheelerDetector"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._model = None
        self._model_path: str = ""
        self._inference_lock = threading.Lock()
        self._config = _load_pipeline_config()
        self._det_cfg = self._config.get("detection", {})

        # Performance counters
        self._frame_count = 0
        self._total_inference_ms = 0.0
        self._fps_start = time.time()
        self._last_fps = 0.0

        self._load_model()

    @classmethod
    def get_instance(cls) -> "TwoWheelerDetector":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── Model loading ──────────────────────────────────────────────────────────

    def _resolve_model_path(self) -> str:
        """Resolve the model path from env > config > default."""
        # Priority: env var > config file > default pretrained
        env_model = os.environ.get("YOLO_MODEL", "")
        cfg_model = self._det_cfg.get("model_path", "")
        raw = env_model or cfg_model or "yolov8n.pt"

        p = Path(raw)
        if p.is_absolute() and p.exists():
            return str(p)
        # Check relative to project root
        candidate = PROJECT_ROOT / raw
        if candidate.exists():
            return str(candidate)
        # Return raw (ultralytics will auto-download pretrained names like yolov8n.pt)
        return raw

    def _load_model(self) -> None:
        if not ULTRALYTICS_AVAILABLE:
            print(
                "[TwoWheelerDetector] WARNING: ultralytics not installed. "
                "Install with: pip install ultralytics\n"
                "Detector will return no detections until installed."
            )
            return

        model_path = self._resolve_model_path()
        if model_path == self._model_path and self._model is not None:
            return  # Already loaded

        device = os.environ.get("DEVICE", self._det_cfg.get("device", "cpu"))
        print(f"[TwoWheelerDetector] Loading model: {model_path} on {device}")
        try:
            self._model = YOLO(model_path)
            if device != "cpu":
                self._model.to(device)
            self._model_path = model_path
            print(f"[TwoWheelerDetector] Model ready. Classes: {list(self._model.names.values())[:10]}...")
        except Exception as exc:
            print(f"[TwoWheelerDetector] ERROR loading model: {exc}")
            self._model = None

    def reload_model(self) -> None:
        """Hot-reload the model (e.g. after training a new checkpoint)."""
        with self._inference_lock:
            self._model_path = ""
            self._load_model()

    # ── Inference ──────────────────────────────────────────────────────────────

    def detect_frame(self, frame: np.ndarray) -> List[Detection]:
        """
        Run inference on a single BGR frame (OpenCV format).
        Returns only motorcycle and bicycle detections.
        """
        if self._model is None:
            return []

        conf = float(os.environ.get(
            "CONFIDENCE_THRESHOLD",
            self._det_cfg.get("confidence_threshold", 0.40)
        ))
        iou = float(self._det_cfg.get("iou_threshold", 0.45))

        t0 = time.perf_counter()
        with self._inference_lock:
            try:
                results = self._model(
                    frame,
                    conf=conf,
                    iou=iou,
                    verbose=False,
                )
            except Exception as exc:
                print(f"[TwoWheelerDetector] Inference error: {exc}")
                return []

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._update_perf(elapsed_ms)

        detections: List[Detection] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                class_id = int(box.cls[0])
                class_name = self._model.names.get(class_id, "")
                # Only keep two-wheeler classes
                if class_name.lower() not in TWO_WHEELER_CLASSES:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf_val = float(box.conf[0])
                detections.append(Detection(
                    bbox=(x1, y1, x2, y2),
                    confidence=conf_val,
                    class_id=class_id,
                    class_name=class_name,
                ))
        return detections

    def detect_image(self, image_path: str) -> List[Detection]:
        """Load image from disk and run detection."""
        if not CV2_AVAILABLE:
            raise RuntimeError("opencv-python-headless is required: pip install opencv-python-headless")
        frame = cv2.imread(str(image_path))
        if frame is None:
            raise FileNotFoundError(f"Cannot read image: {image_path}")
        return self.detect_frame(frame)

    # ── Performance tracking ───────────────────────────────────────────────────

    def _update_perf(self, elapsed_ms: float) -> None:
        self._frame_count += 1
        self._total_inference_ms += elapsed_ms
        elapsed_wall = time.time() - self._fps_start
        if elapsed_wall >= 2.0:
            self._last_fps = self._frame_count / elapsed_wall
            self._frame_count = 0
            self._total_inference_ms = 0.0
            self._fps_start = time.time()

    def get_stats(self) -> Dict[str, object]:
        avg_ms = (
            self._total_inference_ms / max(self._frame_count, 1)
            if self._frame_count else 0.0
        )
        return {
            "fps": round(self._last_fps, 1),
            "avg_inference_ms": round(avg_ms, 1),
            "model_path": self._model_path,
            "model_loaded": self._model is not None,
            "ultralytics_available": ULTRALYTICS_AVAILABLE,
        }

    @property
    def is_ready(self) -> bool:
        return self._model is not None


# ── CLI entry point ────────────────────────────────────────────────────────────

def _cli() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Two-wheeler detector test")
    parser.add_argument("image", help="Path to image file")
    parser.add_argument("--conf", type=float, default=0.4, help="Confidence threshold")
    args = parser.parse_args()

    os.environ.setdefault("CONFIDENCE_THRESHOLD", str(args.conf))

    print(f"Testing detector on: {args.image}")
    detector = TwoWheelerDetector.get_instance()

    if not detector.is_ready:
        print("ERROR: Model not loaded. Install ultralytics: pip install ultralytics")
        sys.exit(1)

    detections = detector.detect_image(args.image)
    print(f"\nFound {len(detections)} two-wheeler(s):")
    for i, det in enumerate(detections, 1):
        print(
            f"  [{i}] {det.class_name:12s}  conf={det.confidence:.2f}  "
            f"bbox=({det.bbox[0]:.0f},{det.bbox[1]:.0f},{det.bbox[2]:.0f},{det.bbox[3]:.0f})"
        )

    if CV2_AVAILABLE and detections:
        frame = cv2.imread(args.image)
        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det.bbox]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{det.class_name} {det.confidence:.2f}"
            cv2.putText(frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        out_path = Path(args.image).with_stem(Path(args.image).stem + "_detected")
        cv2.imwrite(str(out_path), frame)
        print(f"\nAnnotated image saved to: {out_path}")

    print(f"\nStats: {detector.get_stats()}")


if __name__ == "__main__":
    _cli()
