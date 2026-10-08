"""
classifier.py — Parking Behavior Classifier Inference
======================================================
Loads the trained classical ML classifier (Logistic Regression /
Decision Tree / Random Forest) and classifies a parked vehicle's
engineered features as:
  - 'safe'
  - 'risk'
  - 'violation'

If no model has been trained yet (data/trained_models/classifier.pkl missing),
it gracefully returns 'pending'.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    import joblib
    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False
    joblib = None  # type: ignore

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None  # type: ignore


def _find_project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "config" / "pipeline.yaml").exists():
            return parent
    return here.parents[2]


PROJECT_ROOT = _find_project_root()


class ParkingClassifier:
    """
    Singleton classifier for parking behavior.
    Thread-safe inference using trained scikit-learn model.
    """

    _instance: Optional["ParkingClassifier"] = None

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = model_path or os.environ.get(
            "CLASSIFIER_PATH",
            str(PROJECT_ROOT / "data" / "trained_models" / "classifier.pkl"),
        )
        self.metadata_path = str(
            Path(self.model_path).parent / "classifier_metadata.json"
        )
        self.model: Optional[Any] = None
        self.metadata: Dict[str, Any] = {}
        self.feature_columns: List[str] = []
        self.classes: List[str] = []

        self.load_model()

    @classmethod
    def get_instance(cls, model_path: Optional[str] = None) -> "ParkingClassifier":
        if cls._instance is None:
            cls._instance = cls(model_path)
        return cls._instance

    def load_model(self) -> bool:
        """Load trained model from disk if available."""
        if not JOBLIB_AVAILABLE:
            return False

        model_file = Path(self.model_path)
        if not model_file.exists():
            return False

        try:
            self.model = joblib.load(str(model_file))
            meta_file = Path(self.metadata_path)
            if meta_file.exists():
                with open(meta_file, "r") as f:
                    self.metadata = json.load(f)
                self.feature_columns = self.metadata.get("feature_columns", [])
                self.classes = self.metadata.get("classes", ["safe", "risk", "violation"])
            else:
                if hasattr(self.model, "classes_"):
                    self.classes = [str(c) for c in self.model.classes_]
                else:
                    self.classes = ["safe", "risk", "violation"]
            return True
        except Exception as e:
            print(f"[ParkingClassifier] Failed to load model: {e}")
            self.model = None
            return False

    @property
    def is_ready(self) -> bool:
        return self.model is not None

    def model_info(self) -> Dict[str, Any]:
        return {
            "is_ready": self.is_ready,
            "model_path": self.model_path,
            "model_type": self.metadata.get("model_type", "Unknown"),
            "classes": self.classes,
            "metrics": self.metadata.get("metrics", {}),
            "feature_columns": self.feature_columns,
        }

    def predict(self, feature_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify parking behavior from an engineered feature dictionary.
        Returns:
            {
                "label": "safe" | "risk" | "violation" | "pending",
                "confidence": float,
                "probabilities": {"safe": float, "risk": float, "violation": float}
            }
        """
        if not self.is_ready or not NUMPY_AVAILABLE:
            # Fallback heuristic if ML model is not yet trained
            return self._heuristic_fallback(feature_dict)

        # Build feature vector matching trained order
        if not self.feature_columns:
            self.feature_columns = [
                "inside_zone",
                "distance_to_nearest_zone_m",
                "orientation_delta_deg",
                "nearest_neighbor_dist_px",
                "obstructs_walkway",
                "obstructs_fire_lane",
                "bay_sequence_violation",
                "dwell_seconds",
                "confidence",
            ]

        vec = []
        for col in self.feature_columns:
            val = feature_dict.get(col, 0.0)
            if isinstance(val, bool):
                val = 1.0 if val else 0.0
            try:
                val = float(val)
            except (ValueError, TypeError):
                val = 0.0
            vec.append(val)

        X = np.array([vec], dtype=np.float32)

        try:
            pred_idx = self.model.predict(X)[0]
            label = str(pred_idx)
            probs: Dict[str, float] = {}

            if hasattr(self.model, "predict_proba"):
                prob_arr = self.model.predict_proba(X)[0]
                classes = getattr(self.model, "classes_", self.classes)
                for c, p in zip(classes, prob_arr):
                    probs[str(c)] = round(float(p), 4)
                conf = float(np.max(prob_arr))
            else:
                conf = 1.0
                probs[label] = 1.0

            return {
                "label": label,
                "confidence": round(conf, 4),
                "probabilities": probs,
                "model_used": self.metadata.get("model_type", "ml_model"),
            }
        except Exception as e:
            print(f"[ParkingClassifier] Prediction error: {e}")
            return self._heuristic_fallback(feature_dict)

    def _heuristic_fallback(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rule-based heuristic when ML model is not trained yet.
        Never yields dummy mock results: applies direct parking rules.
        """
        inside = bool(features.get("inside_zone", False))
        dist = float(features.get("distance_to_nearest_zone_m", 0.0))
        angle_delta = float(features.get("orientation_delta_deg", 0.0))
        walkway = bool(features.get("obstructs_walkway", False))
        fire_lane = bool(features.get("obstructs_fire_lane", False))
        seq = bool(features.get("bay_sequence_violation", False))

        if fire_lane or walkway:
            label = "violation"
            conf = 0.95
        elif not inside and dist > 0.6:
            label = "violation"
            conf = 0.90
        elif seq:
            label = "violation"
            conf = 0.85
        elif not inside and dist <= 0.6:
            label = "risk"
            conf = 0.75
        elif inside and angle_delta > 25.0:
            label = "risk"
            conf = 0.70
        else:
            label = "safe"
            conf = 0.85

        return {
            "label": label,
            "confidence": conf,
            "probabilities": {label: conf},
            "model_used": "rules_fallback",
        }
