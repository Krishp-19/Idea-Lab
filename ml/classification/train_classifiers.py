"""
train_classifiers.py — Train & Compare Parking Behavior Classifiers
===================================================================
Trains and compares:
  1. Logistic Regression
  2. Decision Tree
  3. Random Forest

Evaluates each on a held-out test split with:
  - Accuracy
  - Macro Precision, Recall, F1-Score
  - Confusion Matrix

Picks the best-performing model (highest macro F1), saves it to
data/trained_models/classifier.pkl, and saves confusion matrix plots.

Usage:
    # Train on real labeled features
    python ml/classification/train_classifiers.py --features data/features/labeled_features.csv

    # Run smoke test with synthetic data
    python ml/classification/train_classifiers.py --smoke-test
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any

FEATURE_COLUMNS = [
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

TARGET_CLASSES = ["safe", "risk", "violation"]


def _find_project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "config" / "pipeline.yaml").exists():
            return parent
    return here.parents[2]


PROJECT_ROOT = _find_project_root()


def generate_synthetic_data(n_samples: int = 300) -> Tuple[Any, Any]:
    """Generate realistic synthetic feature data for smoke-testing the pipeline."""
    import numpy as np

    np.random.seed(42)
    rows = []
    labels = []

    samples_per_class = n_samples // 3

    # 1. Safe samples: inside zone, low distance, small orientation delta, no obstructions
    for _ in range(samples_per_class):
        inside = 1.0
        dist = 0.0
        angle = float(np.random.uniform(0, 15))
        nn_dist = float(np.random.uniform(40, 150))
        walkway = 0.0
        fire_lane = 0.0
        seq = 0.0
        dwell = float(np.random.uniform(30, 600))
        conf = float(np.random.uniform(0.70, 0.99))
        rows.append([inside, dist, angle, nn_dist, walkway, fire_lane, seq, dwell, conf])
        labels.append("safe")

    # 2. Risk samples: inside zone but misaligned (>20 deg) OR close to bay line (<0.5m)
    for _ in range(samples_per_class):
        mode = np.random.choice(["misaligned", "straddling"])
        if mode == "misaligned":
            inside = 1.0
            dist = 0.0
            angle = float(np.random.uniform(25, 60))
            nn_dist = float(np.random.uniform(20, 60))
        else:
            inside = 0.0
            dist = float(np.random.uniform(0.05, 0.45))
            angle = float(np.random.uniform(0, 30))
            nn_dist = float(np.random.uniform(20, 100))

        walkway = 0.0
        fire_lane = 0.0
        seq = 0.0
        dwell = float(np.random.uniform(30, 400))
        conf = float(np.random.uniform(0.60, 0.95))
        rows.append([inside, dist, angle, nn_dist, walkway, fire_lane, seq, dwell, conf])
        labels.append("risk")

    # 3. Violation samples: fire lane/walkway obstruction OR far outside bay (>0.6m) OR sequence violation
    for _ in range(samples_per_class):
        mode = np.random.choice(["walkway", "fire_lane", "far_outside", "sequence"])
        if mode == "walkway":
            inside = 0.0
            dist = float(np.random.uniform(0.5, 4.0))
            walkway = 1.0
            fire_lane = 0.0
            seq = 0.0
        elif mode == "fire_lane":
            inside = 0.0
            dist = float(np.random.uniform(0.5, 4.0))
            walkway = 0.0
            fire_lane = 1.0
            seq = 0.0
        elif mode == "sequence":
            inside = 1.0
            dist = 0.0
            walkway = 0.0
            fire_lane = 0.0
            seq = 1.0
        else:
            inside = 0.0
            dist = float(np.random.uniform(0.8, 5.0))
            walkway = 0.0
            fire_lane = 0.0
            seq = 0.0

        angle = float(np.random.uniform(0, 90))
        nn_dist = float(np.random.uniform(10, 200))
        dwell = float(np.random.uniform(30, 800))
        conf = float(np.random.uniform(0.60, 0.99))
        rows.append([inside, dist, angle, nn_dist, walkway, fire_lane, seq, dwell, conf])
        labels.append("violation")

    return np.array(rows, dtype=np.float32), np.array(labels)


def load_dataset(csv_path: str) -> Tuple[Any, Any]:
    """Load labeled dataset from CSV."""
    import pandas as pd
    import numpy as np

    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(f"Feature CSV not found: {csv_path}")

    df = pd.read_csv(p)
    if "label" not in df.columns:
        raise ValueError(f"CSV {csv_path} does not contain 'label' column.")

    # Filter unlabelled rows
    df = df[df["label"].notna()]
    df = df[df["label"].str.strip() != ""]
    df["label"] = df["label"].str.strip().str.lower()

    valid_labels = set(TARGET_CLASSES)
    df = df[df["label"].isin(valid_labels)]

    if len(df) < 10:
        raise ValueError(
            f"Not enough labeled rows in {csv_path} (found {len(df)}). "
            "Please label at least 15-30 examples across classes."
        )

    # Convert columns to float
    X_list = []
    for _, row in df.iterrows():
        vec = []
        for col in FEATURE_COLUMNS:
            val = row.get(col, 0.0)
            if isinstance(val, (bool, np.bool_)):
                val = 1.0 if val else 0.0
            elif isinstance(val, str):
                val = 1.0 if val.lower() in ("true", "1", "yes") else 0.0
            vec.append(float(val))
        X_list.append(vec)

    X = np.array(X_list, dtype=np.float32)
    y = df["label"].values
    return X, y


def train_and_compare(
    X: Any,
    y: Any,
    output_dir: Path,
    test_size: float = 0.2,
) -> Dict[str, Any]:
    """Train Logistic Regression, Decision Tree, and Random Forest."""
    import numpy as np
    import joblib
    from sklearn.model_selection import train_test_split
    from sklearn.linear_model import LogisticRegression
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import (
        accuracy_score,
        precision_score,
        recall_score,
        f1_score,
        confusion_matrix,
        classification_report,
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )

    models = {
        "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42),
        "Decision Tree": DecisionTreeClassifier(max_depth=5, random_state=42),
        "Random Forest": RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42),
    }

    results = {}
    best_model_name = ""
    best_f1 = -1.0
    best_model = None

    print("\n" + "=" * 65)
    print("Classical ML Models Evaluation (Safe / Risk / Violation)")
    print("=" * 65)
    print(f"Total samples: {len(X)} | Train: {len(X_train)} | Test: {len(X_test)}")

    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        acc = float(accuracy_score(y_test, y_pred))
        prec = float(precision_score(y_test, y_pred, average="macro", zero_division=0))
        rec = float(recall_score(y_test, y_pred, average="macro", zero_division=0))
        f1 = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
        cm = confusion_matrix(y_test, y_pred, labels=TARGET_CLASSES).tolist()

        results[name] = {
            "accuracy": round(acc, 4),
            "precision_macro": round(prec, 4),
            "recall_macro": round(rec, 4),
            "f1_macro": round(f1, 4),
            "confusion_matrix": cm,
            "classes": TARGET_CLASSES,
        }

        print(f"\n--- {name} ---")
        print(f"  Accuracy:         {acc:.4f}")
        print(f"  Precision (macro): {prec:.4f}")
        print(f"  Recall (macro):    {rec:.4f}")
        print(f"  F1-Score (macro):  {f1:.4f}")
        print("  Confusion Matrix:")
        print(f"      Rows = Actual, Cols = Predicted: {TARGET_CLASSES}")
        for r, cls_name in zip(cm, TARGET_CLASSES):
            print(f"      {cls_name:10s}: {r}")

        # Try to save confusion matrix image
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(5, 4))
            im = ax.imshow(cm, interpolation="nearest", cmap="Blues")
            ax.figure.colorbar(im, ax=ax)
            ax.set(
                xticks=np.arange(len(TARGET_CLASSES)),
                yticks=np.arange(len(TARGET_CLASSES)),
                xticklabels=TARGET_CLASSES,
                yticklabels=TARGET_CLASSES,
                ylabel="True label",
                xlabel="Predicted label",
                title=f"{name} Confusion Matrix",
            )
            for i in range(len(TARGET_CLASSES)):
                for j in range(len(TARGET_CLASSES)):
                    ax.text(
                        j, i, format(cm[i][j], "d"),
                        ha="center", va="center",
                        color="white" if cm[i][j] > (np.max(cm) / 2.0) else "black",
                    )
            fig.tight_layout()
            cm_path = output_dir / f"confusion_matrix_{name.lower().replace(' ', '_')}.png"
            plt.savefig(str(cm_path), dpi=150)
            plt.close()
        except Exception as e:
            pass

        if f1 > best_f1:
            best_f1 = f1
            best_model_name = name
            best_model = model

    print("\n" + "=" * 65)
    print(f"BEST PERFORMER: {best_model_name} (Macro F1 = {best_f1:.4f})")
    print("=" * 65)

    # Save best model and metadata
    classifier_path = output_dir / "classifier.pkl"
    joblib.dump(best_model, str(classifier_path))
    print(f"✓ Saved best model to: {classifier_path}")

    metadata = {
        "model_type": best_model_name,
        "feature_columns": FEATURE_COLUMNS,
        "classes": TARGET_CLASSES,
        "best_macro_f1": best_f1,
        "trained_at": datetime.now().isoformat(),
        "n_samples": len(X),
        "metrics_all_models": results,
    }

    meta_path = output_dir / "classifier_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"✓ Saved metadata to:   {meta_path}")

    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train & compare classical ML models for parking behavior classification",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--features",
        default=str(PROJECT_ROOT / "data" / "features" / "labeled_features.csv"),
        help="Path to labeled feature CSV",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "data" / "trained_models"),
        help="Directory to save classifier.pkl and metrics",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Validation split size",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Generate synthetic training data to verify the pipeline",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)

    if args.smoke_test:
        print("[train_classifiers] Running SMOKE TEST with synthetic dataset...")
        X, y = generate_synthetic_data(n_samples=300)
    else:
        print(f"[train_classifiers] Loading dataset from: {args.features}")
        try:
            X, y = load_dataset(args.features)
        except Exception as e:
            print(f"\nERROR loading dataset: {e}")
            print("\nHint: You can test the training pipeline anytime with:")
            print("  python ml/classification/train_classifiers.py --smoke-test\n")
            sys.exit(1)

    train_and_compare(X, y, out_dir, test_size=args.test_size)


if __name__ == "__main__":
    main()
