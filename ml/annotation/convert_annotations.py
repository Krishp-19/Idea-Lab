"""
convert_annotations.py — Convert LabelImg/CVAT annotations to YOLO format
=========================================================================
Converts Pascal VOC XML (LabelImg) or CVAT XML to YOLO label format,
splits into train/val, and generates data.yaml.

Usage:
    # From LabelImg (Pascal VOC XML, one file per image):
    python ml/annotation/convert_annotations.py \\
      --input-dir data/annotations/raw \\
      --output-dir data/annotations \\
      --format labelimg \\
      --classes motorcycle,bicycle

    # From CVAT (single XML export file):
    python ml/annotation/convert_annotations.py \\
      --input-dir data/annotations/cvat_export.xml \\
      --output-dir data/annotations \\
      --format cvat \\
      --classes motorcycle,bicycle
"""

from __future__ import annotations

import argparse
import os
import random
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ── Utility ────────────────────────────────────────────────────────────────────

def _bbox_to_yolo(
    x_min: float, y_min: float, x_max: float, y_max: float,
    img_w: float, img_h: float,
) -> Tuple[float, float, float, float]:
    """Convert absolute bbox to YOLO normalized (x_center, y_center, w, h)."""
    x_center = ((x_min + x_max) / 2) / img_w
    y_center = ((y_min + y_max) / 2) / img_h
    width = (x_max - x_min) / img_w
    height = (y_max - y_min) / img_h
    return (
        max(0.0, min(1.0, x_center)),
        max(0.0, min(1.0, y_center)),
        max(0.0, min(1.0, width)),
        max(0.0, min(1.0, height)),
    )


def _find_image(name_stem: str, search_dirs: List[Path]) -> Optional[Path]:
    """Find an image file by stem (without extension) in multiple dirs."""
    for ext in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
        for d in search_dirs:
            candidate = d / (name_stem + ext)
            if candidate.exists():
                return candidate
    return None


# ── LabelImg (Pascal VOC XML) parser ──────────────────────────────────────────

def _parse_labelimg_xml(
    xml_path: Path, class_map: Dict[str, int]
) -> Optional[Tuple[str, int, int, List[str]]]:
    """
    Parse a single Pascal VOC XML annotation file.
    Returns (image_filename, width, height, yolo_label_lines) or None on error.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as exc:
        print(f"  SKIP (parse error in {xml_path.name}): {exc}")
        return None

    filename_el = root.find("filename")
    size_el = root.find("size")
    if filename_el is None or size_el is None:
        print(f"  SKIP (missing filename/size in {xml_path.name})")
        return None

    filename = filename_el.text or xml_path.stem
    img_w = float(size_el.findtext("width", "0"))
    img_h = float(size_el.findtext("height", "0"))
    if img_w == 0 or img_h == 0:
        print(f"  SKIP (zero dimensions in {xml_path.name})")
        return None

    label_lines: List[str] = []
    for obj in root.findall("object"):
        name_el = obj.find("name")
        bndbox = obj.find("bndbox")
        if name_el is None or bndbox is None:
            continue

        cls_name = (name_el.text or "").strip().lower()
        if cls_name not in class_map:
            continue  # skip unlisted classes

        x_min = float(bndbox.findtext("xmin", "0"))
        y_min = float(bndbox.findtext("ymin", "0"))
        x_max = float(bndbox.findtext("xmax", "0"))
        y_max = float(bndbox.findtext("ymax", "0"))

        xc, yc, w, h = _bbox_to_yolo(x_min, y_min, x_max, y_max, img_w, img_h)
        label_lines.append(f"{class_map[cls_name]} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")

    return filename, int(img_w), int(img_h), label_lines


def convert_labelimg(
    input_dir: Path,
    output_dir: Path,
    class_map: Dict[str, int],
) -> List[Path]:
    """Convert LabelImg Pascal VOC XMLs to YOLO format. Returns list of image paths."""
    xml_files = list(input_dir.rglob("*.xml"))
    if not xml_files:
        print(f"ERROR: No XML files found in {input_dir}")
        sys.exit(1)
    print(f"Found {len(xml_files)} XML annotation files")

    images_dir = output_dir / "images"
    labels_dir = output_dir / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    image_search_dirs = [input_dir, input_dir / "images", input_dir.parent]
    converted_images: List[Path] = []
    skipped = 0

    for xml_path in xml_files:
        result = _parse_labelimg_xml(xml_path, class_map)
        if result is None:
            skipped += 1
            continue

        img_filename, _w, _h, label_lines = result
        if not label_lines:
            # No two-wheeler annotations in this file
            skipped += 1
            continue

        # Find the source image
        img_stem = Path(img_filename).stem
        src_image = _find_image(img_stem, image_search_dirs)
        if src_image is None:
            # Try finding by XML stem
            src_image = _find_image(xml_path.stem, image_search_dirs)
        if src_image is None:
            print(f"  SKIP (image not found for {xml_path.name})")
            skipped += 1
            continue

        # Copy image
        dest_image = images_dir / src_image.name
        shutil.copy2(src_image, dest_image)
        converted_images.append(dest_image)

        # Write label file
        label_path = labels_dir / (src_image.stem + ".txt")
        label_path.write_text("\n".join(label_lines))

    print(f"Converted: {len(converted_images)} | Skipped: {skipped}")
    return converted_images


# ── CVAT XML parser ────────────────────────────────────────────────────────────

def convert_cvat(
    xml_path: Path,
    input_dir: Path,
    output_dir: Path,
    class_map: Dict[str, int],
) -> List[Path]:
    """Convert CVAT XML export to YOLO format. Returns list of image paths."""
    if not xml_path.exists():
        print(f"ERROR: CVAT XML not found: {xml_path}")
        sys.exit(1)

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as exc:
        print(f"ERROR: Cannot parse CVAT XML: {exc}")
        sys.exit(1)

    root = tree.getroot()
    images_dir = output_dir / "images"
    labels_dir = output_dir / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    # CVAT format has <image id="..." name="..." width="..." height="..."> elements
    image_elements = root.findall(".//image")
    if not image_elements:
        print("ERROR: No <image> elements found in CVAT XML. Make sure you exported in CVAT XML format.")
        sys.exit(1)

    print(f"Found {len(image_elements)} annotated images in CVAT XML")

    image_search_dirs = [input_dir, input_dir / "images", input_dir / "data"]
    converted_images: List[Path] = []
    skipped = 0

    for img_el in image_elements:
        img_name = img_el.get("name", "")
        img_w = float(img_el.get("width", 0))
        img_h = float(img_el.get("height", 0))

        if not img_name or img_w == 0 or img_h == 0:
            skipped += 1
            continue

        label_lines: List[str] = []
        for box_el in img_el.findall("box"):
            cls_name = (box_el.get("label", "")).strip().lower()
            if cls_name not in class_map:
                continue
            x_min = float(box_el.get("xtl", 0))
            y_min = float(box_el.get("ytl", 0))
            x_max = float(box_el.get("xbr", 0))
            y_max = float(box_el.get("ybr", 0))
            xc, yc, w, h = _bbox_to_yolo(x_min, y_min, x_max, y_max, img_w, img_h)
            label_lines.append(f"{class_map[cls_name]} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")

        if not label_lines:
            skipped += 1
            continue

        # Find image file
        img_stem = Path(img_name).stem
        src_image = _find_image(img_stem, image_search_dirs)
        if src_image is None:
            print(f"  SKIP (image not found: {img_name})")
            skipped += 1
            continue

        dest_image = images_dir / src_image.name
        shutil.copy2(src_image, dest_image)
        converted_images.append(dest_image)

        label_path = labels_dir / (img_stem + ".txt")
        label_path.write_text("\n".join(label_lines))

    print(f"Converted: {len(converted_images)} | Skipped: {skipped}")
    return converted_images


# ── data.yaml generator ────────────────────────────────────────────────────────

def generate_data_yaml(
    output_dir: Path,
    classes: List[str],
    image_paths: List[Path],
    val_ratio: float = 0.2,
    seed: int = 42,
) -> Path:
    """Split images into train/val and write data.yaml."""
    try:
        import yaml
    except ImportError:
        print("ERROR: PyYAML not installed. Run: pip install PyYAML")
        sys.exit(1)

    # Create train/val split subdirs
    train_images = output_dir / "train" / "images"
    train_labels = output_dir / "train" / "labels"
    val_images   = output_dir / "val"   / "images"
    val_labels   = output_dir / "val"   / "labels"
    for d in (train_images, train_labels, val_images, val_labels):
        d.mkdir(parents=True, exist_ok=True)

    random.seed(seed)
    random.shuffle(image_paths)
    n_val = max(1, int(len(image_paths) * val_ratio))
    val_set   = set(p.name for p in image_paths[:n_val])

    moved = {"train": 0, "val": 0}
    for img_path in image_paths:
        split = "val" if img_path.name in val_set else "train"
        # Move image
        dest_img = (val_images if split == "val" else train_images) / img_path.name
        shutil.copy2(img_path, dest_img)
        # Move label
        src_label = img_path.parent.parent / "labels" / (img_path.stem + ".txt")
        if src_label.exists():
            dest_lbl = (val_labels if split == "val" else train_labels) / src_label.name
            shutil.copy2(src_label, dest_lbl)
        moved[split] += 1

    print(f"Split — train: {moved['train']} | val: {moved['val']}")

    data_yaml = {
        "path": str(output_dir.resolve()),
        "train": "train/images",
        "val":   "val/images",
        "nc":    len(classes),
        "names": classes,
    }
    yaml_path = output_dir / "data.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(data_yaml, f, default_flow_style=False)

    print(f"data.yaml written to: {yaml_path}")
    return yaml_path


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert LabelImg/CVAT annotations to YOLO format",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing XML annotation files (LabelImg) or path to CVAT XML file",
    )
    parser.add_argument(
        "--output-dir",
        default="data/annotations",
        help="Output directory for YOLO-format labels and data.yaml",
    )
    parser.add_argument(
        "--format",
        choices=["labelimg", "cvat"],
        default="labelimg",
        help="Annotation format",
    )
    parser.add_argument(
        "--classes",
        default="motorcycle,bicycle",
        help="Comma-separated class names in desired class-index order",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.2,
        help="Fraction of images for validation set (0–1)",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    classes = [c.strip().lower() for c in args.classes.split(",") if c.strip()]
    class_map = {name: idx for idx, name in enumerate(classes)}
    print(f"Class map: {class_map}")

    input_path = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nConverting {args.format} annotations...")
    if args.format == "labelimg":
        image_paths = convert_labelimg(input_path, output_dir, class_map)
    else:
        # For CVAT, input-dir can be the XML file or a directory containing it
        if input_path.is_file():
            xml_path = input_path
            search_dir = input_path.parent
        else:
            xml_files = list(input_path.glob("*.xml"))
            if not xml_files:
                print(f"ERROR: No XML file found in {input_path}")
                sys.exit(1)
            xml_path = xml_files[0]
            search_dir = input_path
        image_paths = convert_cvat(xml_path, search_dir, output_dir, class_map)

    if not image_paths:
        print("\nERROR: No annotations were converted. Check that:")
        print("  1. Your class names match the --classes argument")
        print("  2. Image files are in the input directory")
        sys.exit(1)

    print(f"\nGenerating train/val split (val_ratio={args.val_ratio})...")
    yaml_path = generate_data_yaml(output_dir, classes, image_paths, args.val_ratio, args.seed)

    print(f"\n✓ Conversion complete!")
    print(f"  Total images:  {len(image_paths)}")
    print(f"  Output dir:    {output_dir}")
    print(f"  data.yaml:     {yaml_path}")
    print(f"\nNext step — train the detector:")
    print(f"  python ml/detection/train_yolo.py --data-yaml {yaml_path}")


if __name__ == "__main__":
    main()
