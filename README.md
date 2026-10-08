# Two-Wheeler Illegal Parking Detection & Monitoring System

An end-to-end, production-grade AI system for detecting, tracking, and classifying illegal parking behavior for motorcycles and scooters in designated lots, fire lanes, and pedestrian walkways.

---

## 🏗️ System Architecture

```
                                    +--------------------+
                                    | CCTV Footage / RTSP|
                                    +---------+----------+
                                              |
                                              v
+-----------------------------------------------------------------------------------+
| ML Core Pipeline (ml/)                                                            |
|                                                                                   |
|  [Two-Wheeler Detector]  --->  [Parking Tracker]   ---> [Feature Extractor]       |
|    - YOLOv8 inference            - ByteTrack / IoU        - Inside zone (polygon) |
|    - motorcycle/bicycle only     - Dwell-time filter      - Angle misalignment    |
|                                                           - Walkway obstruction   |
|                                                           - Fire-lane hazard      |
|                                                           - Sequence violation    |
|                                                                      |            |
|  [Classical ML Classifiers] <----------------------------------------+            |
|    - Logistic Regression, Decision Tree, Random Forest                            |
|    - Classes: Safe / Risk / Violation                                             |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| Backend Service (backend/)                                                        |
|   - FastAPI REST API                                                              |
|   - PostgreSQL 16 + SQLAlchemy 2.0 (Alembic schema migrations)                    |
|   - Case review workflow (human confirmation / dismissal)                         |
|   - Spatial zone management & analytics aggregations                              |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| Authority Dashboard (frontend/)                                                   |
|   - React 18 + Vite + TailwindCSS                                                 |
|   - Live stream status & canvas bounding box overlays                             |
|   - Violations case review queue with evidence snapshots                          |
|   - Compliance trend charts (Recharts) & spatial heatmap                          |
+-----------------------------------------------------------------------------------+
```

---

## 🚀 Step-by-Step Run Order & Instructions

Follow this exact workflow from data preparation to production launch.

### Step 1: Annotate Data (LabelImg or CVAT)

Place your raw camera images in `data/raw_images/`.

1. Annotate two classes: **`motorcycle`** and **`bicycle`**.
2. If using **LabelImg**: Save as Pascal VOC XML in `data/annotations/raw/`.
3. Convert annotations into YOLO format and generate `data.yaml`:
   ```bash
   python ml/annotation/convert_annotations.py \
     --input-dir data/annotations/raw \
     --output-dir data/annotations \
     --format labelimg \
     --classes motorcycle,bicycle
   ```
   *(For full CVAT export instructions and options, see [`ml/annotation/README.md`](file:///Users/krish/Desktop/idealab/two-wheeler-parking-project/ml/annotation/README.md))*

---

### Step 2: Fine-Tune the Two-Wheeler Detector

Train a custom YOLOv8 model on your annotated images:
```bash
python ml/detection/train_yolo.py \
  --data-yaml data/annotations/data.yaml \
  --epochs 50 \
  --img-size 640 \
  --base-model yolov8n.pt \
  --device cpu   # or cuda if GPU is available
```
- Best weights are automatically saved to `data/trained_models/two_wheeler_detector.pt`.

---

### Step 3: Define Parking Bays and Restricted Zones

Mark designated parking bays, walkways, and emergency fire lanes on a sample frame from your site:
```bash
python ml/zone_config/zone_drawer.py --frame data/raw_images/sample.jpg
```

**Controls:**
- **LEFT CLICK**: Add polygon vertex
- **RIGHT CLICK**: Remove last vertex
- **ENTER**: Finish zone (prompts in terminal for name, expected angle, and zone type)
- **D**: Delete last finished zone
- **S**: Save to `config/zones.json` and exit
- **Q**: Quit without saving

---

### Step 4: Run Tracking Pipeline to Generate Feature Data

Process video footage to track stationary vehicles and compute spatial parking features:
```bash
python ml/tracking/pipeline.py \
  --source data/raw_video/parking_lot.mp4 \
  --output-video data/evidence/processed_output.mp4 \
  --show
```
- Every stationary vehicle exceeding the dwell-time threshold (default 30s) produces an evidence snapshot in `data/evidence/` and a feature row in `data/features/features.csv`.

---

### Step 5: Label Features & Train Classical Classifiers

1. Open `data/features/features.csv`.
2. Inspect corresponding snapshots in `data/evidence/` and set the `label` column to:
   - `safe`: Properly parked inside bay, aligned with expected angle ($\le 20^\circ$).
   - `risk`: Straddling bay line ($\le 0.5\text{m}$) or misaligned inside bay ($> 20^\circ$).
   - `violation`: Obstructing walkways/fire lanes, parked far outside bays ($> 0.5\text{m}$), or bay sequence violation.
3. Save as `data/features/labeled_features.csv`.
4. Train and compare all 3 models:
   ```bash
   python ml/classification/train_classifiers.py \
     --features data/features/labeled_features.csv
   ```
   *(To test the training pipeline immediately without manual labels, run the built-in smoke test: `python ml/classification/train_classifiers.py --smoke-test`)*

The script outputs comparison metrics:
- Accuracy, Macro Precision, Recall, and F1-Score
- Confusion matrix for **Logistic Regression**, **Decision Tree**, and **Random Forest**
- Saves the top-performing model to `data/trained_models/classifier.pkl`

---

### Step 6: Launch Full Stack with Docker

Start the entire system (PostgreSQL 16, FastAPI backend, and React dashboard) with a single command:

```bash
cd docker
docker compose up --build
```

Access the applications:
- **Authority Dashboard**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Check**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

**Default Admin Credentials:**
- **Username**: `admin`
- **Password**: `Admin@123456`

---

## ⚙️ Configuration & Environment Variables

All parameters are configured via `.env` or `config/pipeline.yaml`:

| Parameter | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://...` | PostgreSQL connection string (or SQLite for local dev) |
| `YOLO_MODEL` | `yolov8n.pt` | Path or weights identifier for detector |
| `DEVICE` | `cpu` | Inference hardware (`cpu`, `cuda`, `mps`) |
| `CONFIDENCE_THRESHOLD` | `0.40` | Minimum detector confidence |
| `DWELL_TIME_SECONDS` | `30` | Seconds stationary to be classified as parked |
| `STATIONARY_PX_THRESHOLD` | `15` | Max centroid drift to still count as stationary |
| `PX_PER_METER` | `50.0` | Pixel-to-meter scale for distance calculations |

---

## 🧪 Running Unit & API Tests

Run backend tests using SQLite in-memory mode:
```bash
cd backend
pytest tests/ -v
```
