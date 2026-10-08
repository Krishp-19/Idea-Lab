# Annotation Guide for Two-Wheeler Parking Detection

This guide walks you through annotating your own CCTV images and converting them into the YOLO format needed for fine-tuning the detector.

---

## Prerequisites

Install the required tools:

```bash
# LabelImg (simple, recommended for beginners)
pip install labelImg

# CVAT runs in Docker (recommended for large datasets)
# See: https://github.com/opencv/cvat
```

Install the project ML dependencies:

```bash
pip install -r ml/requirements.txt
```

---

## What to annotate

Annotate **only** these two classes (exact names matter):
- `motorcycle` — all motorbikes, scooters
- `bicycle` — bicycles, e-bikes

**Do not annotate**: cars, buses, trucks, people, or background objects. If a two-wheeler is heavily occluded (>60% hidden), skip it.

Draw a tight bounding box around the full vehicle body (handlebars to rear wheel) when visible.

---

## Option A: LabelImg (Pascal VOC XML)

### 1. Launch LabelImg

```bash
labelImg
```

### 2. Set up directories

In LabelImg:
1. **Open Dir** → select `data/raw_images/`
2. **Change Save Dir** → select `data/annotations/raw/`
3. Format: Click **PascalVOC** (bottom left) — **NOT YOLO**

### 3. Add your class list

Create a file `data/annotations/raw/predefined_classes.txt`:
```
motorcycle
bicycle
```

In LabelImg menu: **View → Use Default Label → off** (let it use the classes file).

### 4. Annotate

- Press `W` to draw a bounding box
- Click and drag around the vehicle
- Select the class from the dropdown
- Press `Ctrl+S` to save
- Press `D` to go to the next image

### 5. Convert to YOLO format

```bash
python ml/annotation/convert_annotations.py \
  --input-dir data/annotations/raw \
  --output-dir data/annotations \
  --format labelimg \
  --classes motorcycle,bicycle
```

This creates:
```
data/annotations/
  train/
    images/   ← 80% of images
    labels/   ← YOLO .txt files
  val/
    images/   ← 20% of images
    labels/
  data.yaml   ← used by train_yolo.py
```

---

## Option B: CVAT (for larger datasets)

### 1. Start CVAT

```bash
# Install Docker first, then:
git clone https://github.com/opencv/cvat.git
cd cvat
docker compose up -d
# Open http://localhost:8080 in browser
```

### 2. Create a project

1. Create new project: **"Two-Wheeler Parking"**
2. Add labels: `motorcycle`, `bicycle`
3. Create a task and upload your images

### 3. Annotate

Use the **Draw Rectangle** tool (R key) in CVAT to annotate.

### 4. Export

1. Go to **Tasks** → your task → **Actions** → **Export annotations**
2. Format: **CVAT for images 1.1** (XML format)
3. Download the ZIP and extract it

### 5. Convert to YOLO format

```bash
python ml/annotation/convert_annotations.py \
  --input-dir path/to/cvat_export.xml \
  --output-dir data/annotations \
  --format cvat \
  --classes motorcycle,bicycle
```

---

## Verifying your annotations

After conversion, visually verify a few labels:

```python
import cv2, os
from pathlib import Path

img_dir   = Path("data/annotations/train/images")
label_dir = Path("data/annotations/train/labels")

for img_path in list(img_dir.glob("*.jpg"))[:5]:
    img = cv2.imread(str(img_path))
    h, w = img.shape[:2]
    label_path = label_dir / (img_path.stem + ".txt")
    if label_path.exists():
        for line in label_path.read_text().strip().splitlines():
            parts = line.split()
            cls_id = int(parts[0])
            xc, yc, bw, bh = map(float, parts[1:])
            x1 = int((xc - bw/2) * w)
            y1 = int((yc - bh/2) * h)
            x2 = int((xc + bw/2) * w)
            y2 = int((yc + bh/2) * h)
            color = (0,255,0) if cls_id == 0 else (255,0,0)
            cv2.rectangle(img, (x1,y1), (x2,y2), color, 2)
    cv2.imwrite(f"/tmp/check_{img_path.name}", img)
    print(f"Saved check to /tmp/check_{img_path.name}")
```

---

## What `data.yaml` looks like

```yaml
path: /absolute/path/to/data/annotations
train: train/images
val: val/images
nc: 2
names:
  - motorcycle
  - bicycle
```

**Class indices**: `0 = motorcycle`, `1 = bicycle`

---

## Minimum dataset size

| Use case | Min images | Recommended |
|---|---|---|
| Initial test | 50 | — |
| Basic training | 200 | 500 |
| Good accuracy | 500 | 1000+ |

Aim for diversity: different angles, lighting conditions, parking densities.

---

## Troubleshooting

**"No XML files found"**
→ Make sure you saved in **PascalVOC** format in LabelImg, not YOLO format.

**"Image not found for annotations/X.xml"**
→ Make sure your images are in the same folder as the XML files, or in a subfolder called `images/`.

**"0 annotations converted"**
→ Check that your class names exactly match `motorcycle` and `bicycle` (lowercase).

**LabelImg crashes on Apple Silicon**
→ Use: `pip install labelImg --pre` or try the CVAT option instead.

---

## Next steps

After conversion:

```bash
# 1. Train the detector
python ml/detection/train_yolo.py \
  --data-yaml data/annotations/data.yaml \
  --epochs 50

# 2. Define parking zones on a sample frame
python ml/zone_config/zone_drawer.py \
  --frame data/raw_images/your_frame.jpg
```
