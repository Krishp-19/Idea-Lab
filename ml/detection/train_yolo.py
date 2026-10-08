"""
train_yolo.py — Fine-tune YOLOv8 on custom two-wheeler dataset
==============================================================
Reads annotated data from data/annotations/ and fine-tunes a YOLOv8 model.
Best weights are saved to data/trained_models/two_wheeler_detector.pt

Usage:
    python ml/detection/train_yolo.py
    python ml/detection/train_yolo.py --base-model yolov8s.pt --epochs 100
    python ml/detection/train_yolo.py --data-yaml data/annotations/data.yaml --device cuda
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


def _find_project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "config" / "pipeline.yaml").exists():
            return parent
    return here.parents[2]


PROJECT_ROOT = _find_project_root()


def _validate_data_yaml(data_yaml_path: Path) -> dict:
    """Load and validate data.yaml, printing helpful errors."""
    try:
        import yaml
    except ImportError:
        print("ERROR: PyYAML not installed. Run: pip install PyYAML")
        sys.exit(1)

    if not data_yaml_path.exists():
        print(f"\nERROR: data.yaml not found at: {data_yaml_path}")
        print("\nTo create it, follow these steps:")
        print("  1. Annotate images with LabelImg or CVAT")
        print("     See: ml/annotation/README.md")
        print("  2. Run the converter:")
        print("     python ml/annotation/convert_annotations.py \\")
        print("       --input-dir data/annotations/raw \\")
        print("       --output-dir data/annotations \\")
        print("       --format labelimg \\")
        print("       --classes motorcycle,bicycle")
        sys.exit(1)

    with open(data_yaml_path) as f:
        cfg = yaml.safe_load(f)

    required = {"train", "val", "nc", "names"}
    missing = required - set(cfg.keys())
    if missing:
        print(f"ERROR: data.yaml is missing required keys: {missing}")
        print(f"  Found keys: {list(cfg.keys())}")
        sys.exit(1)

    print(f"  Classes ({cfg['nc']}): {cfg['names']}")

    # Validate train/val paths exist
    for split in ("train", "val"):
        split_path = Path(cfg[split])
        if not split_path.is_absolute():
            split_path = data_yaml_path.parent / split_path
        if not split_path.exists():
            print(f"  WARNING: {split} path does not exist: {split_path}")
        else:
            n_images = len(list(split_path.glob("*.jpg")) + list(split_path.glob("*.png")))
            print(f"  {split}: {n_images} images at {split_path}")

    return cfg


def train(
    base_model: str,
    data_yaml: str,
    epochs: int,
    img_size: int,
    batch: int,
    device: str,
    output_dir: Path,
) -> None:
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ERROR: ultralytics not installed. Run: pip install ultralytics")
        sys.exit(1)

    data_yaml_path = Path(data_yaml)
    if not data_yaml_path.is_absolute():
        data_yaml_path = PROJECT_ROOT / data_yaml_path

    print("\n" + "=" * 60)
    print("Two-Wheeler Detector — YOLOv8 Fine-tuning")
    print("=" * 60)
    print(f"  Base model:  {base_model}")
    print(f"  Data:        {data_yaml_path}")
    print(f"  Epochs:      {epochs}")
    print(f"  Image size:  {img_size}")
    print(f"  Batch:       {batch}")
    print(f"  Device:      {device}")
    print(f"  Output:      {output_dir}")
    print()

    print("Validating data.yaml...")
    cfg = _validate_data_yaml(data_yaml_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    run_name = f"two_wheeler_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print(f"\nLoading base model: {base_model}")
    model = YOLO(base_model)

    print(f"Starting training ({epochs} epochs)...\n")
    results = model.train(
        data=str(data_yaml_path.resolve()),
        epochs=epochs,
        imgsz=img_size,
        batch=batch,
        device=device,
        project=str(output_dir / "runs"),
        name=run_name,
        exist_ok=True,
        patience=15,          # early stopping
        save=True,
        save_period=-1,       # save only best
        plots=True,
        verbose=True,
    )

    # Copy best weights to standard location
    best_weights = Path(results.save_dir) / "weights" / "best.pt"
    dest = output_dir / "two_wheeler_detector.pt"

    if best_weights.exists():
        shutil.copy2(best_weights, dest)
        print(f"\n✓ Best weights saved to: {dest}")
    else:
        print(f"\nWARNING: Best weights not found at {best_weights}")

    # Print metrics
    print("\n" + "=" * 60)
    print("Training complete — Metrics:")
    print("=" * 60)
    metrics = results.results_dict
    for key in ("metrics/mAP50(B)", "metrics/mAP50-95(B)", "metrics/precision(B)", "metrics/recall(B)"):
        if key in metrics:
            short = key.split("/")[1].split("(")[0]
            print(f"  {short:25s}: {metrics[key]:.4f}")

    # Save training metadata
    meta = {
        "base_model": base_model,
        "epochs_trained": epochs,
        "img_size": img_size,
        "classes": cfg["names"],
        "nc": cfg["nc"],
        "weights_path": str(dest),
        "trained_at": datetime.now().isoformat(),
        "metrics": {k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))},
    }
    meta_path = output_dir / "two_wheeler_detector_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  Metadata saved to: {meta_path}")

    print("\nRetraining command for future runs:")
    print(f"  python ml/detection/train_yolo.py \\")
    print(f"    --base-model {dest} \\")
    print(f"    --epochs {epochs} \\")
    print(f"    --data-yaml {data_yaml}")


def main() -> None:
    import yaml  # noqa: F401 — checked above

    parser = argparse.ArgumentParser(
        description="Fine-tune YOLOv8 on two-wheeler dataset",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--base-model",
        default=os.environ.get("YOLO_MODEL", "yolov8n.pt"),
        help="Base YOLO weights (e.g. yolov8n.pt, yolov8s.pt, or path to custom .pt)",
    )
    parser.add_argument(
        "--data-yaml",
        default="data/annotations/data.yaml",
        help="Path to data.yaml (relative to project root)",
    )
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--img-size", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument(
        "--device",
        default=os.environ.get("DEVICE", "cpu"),
        help="Inference device: cpu | cuda | cuda:0 | mps",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "data" / "trained_models"),
        help="Directory to save best weights and metadata",
    )
    args = parser.parse_args()

    train(
        base_model=args.base_model,
        data_yaml=args.data_yaml,
        epochs=args.epochs,
        img_size=args.img_size,
        batch=args.batch,
        device=args.device,
        output_dir=Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
