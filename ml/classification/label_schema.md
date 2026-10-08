# Parking Behavior Classification — Labeling Schema & Guide

This guide explains the feature vector produced by `ml/tracking/pipeline.py` and how to assign ground-truth labels to train the classical ML classifiers.

---

## 1. Feature Columns in `data/features/features.csv`

Every time a stationary two-wheeler satisfies the dwell-time threshold, the pipeline appends one row to `data/features/features.csv`.

| Column | Type | Range | Description | Example |
|---|---|---|---|---|
| `track_id` | Integer | $\ge 1$ | Unique ID assigned by the tracker | `4` |
| `timestamp` | String | ISO 8601 | Detection event timestamp | `2026-09-22T01:30:00Z` |
| `zone_id` | String | - | Nearest or containing zone identifier | `bay-1` |
| `zone_name` | String | - | Human-readable name of zone | `North Bay 1` |
| `zone_type` | String | enum | `parking_bay`, `fire_lane`, `walkway` | `parking_bay` |
| `inside_zone` | Boolean / Int | `0` or `1` | `1` if centroid is inside a designated bay polygon | `1` |
| `distance_to_nearest_zone_m`| Float | $\ge 0.0$ | Meters to closest bay edge (`0.0` if inside) | `0.12` |
| `orientation_delta_deg` | Float | $0.0 - 90.0$ | Difference between vehicle orientation and bay's expected angle | `8.5` |
| `nearest_neighbor_dist_px` | Float | $\ge 0.0$ | Euclidean distance in pixels to nearest parked two-wheeler | `85.4` |
| `obstructs_walkway` | Boolean / Int | `0` or `1` | `1` if bounding box overlaps a pedestrian walkway | `0` |
| `obstructs_fire_lane` | Boolean / Int | `0` or `1` | `1` if bounding box overlaps a marked emergency lane | `0` |
| `bay_sequence_violation` | Boolean / Int | `0` or `1` | `1` if vehicle skipped a closer available empty bay | `0` |
| `dwell_seconds` | Float | $\ge 0.0$ | Time duration vehicle was stationary | `45.0` |
| `confidence` | Float | $0.0 - 1.0$ | YOLO detection confidence | `0.92` |
| `bbox_x1, bbox_y1, bbox_x2, bbox_y2` | Float | Pixels | Absolute bounding box coordinates in camera frame | `450, 210, 520, 390` |
| `label` | String | enum | **Your label**: `safe`, `risk`, or `violation` | *(Fill this in)* |

---

## 2. Label Classes Definition

When labeling rows, use **lowercase** strings:

### 🟢 `safe`
- **Definition**: The vehicle is properly parked without causing inconvenience or danger.
- **Criteria**:
  - `inside_zone == 1`
  - `orientation_delta_deg <= 20.0` (aligned with bay lines)
  - `obstructs_walkway == 0` and `obstructs_fire_lane == 0`
  - Reasonable clearance from adjacent vehicles.

### 🟡 `risk`
- **Definition**: Borderline parking behavior that may become an issue or indicates poor discipline.
- **Criteria**:
  - Centroid is slightly outside the bay (`distance_to_nearest_zone_m <= 0.5m`) or straddling the line.
  - OR inside the bay but parked diagonally/crooked (`orientation_delta_deg > 20.0`).
  - OR squeezed uncomfortably close to another vehicle (`nearest_neighbor_dist_px` below threshold).
  - Does **not** block emergency exits or main pedestrian walkways.

### 🔴 `violation`
- **Definition**: Clear illegal or unauthorized parking requiring review and action.
- **Criteria**:
  - `obstructs_fire_lane == 1` OR `obstructs_walkway == 1`
  - OR completely outside designated parking bays (`distance_to_nearest_zone_m > 0.5m`)
  - OR `bay_sequence_violation == 1` (where designated orderly queuing applies)
  - OR blocking access ramps.

---

## 3. Labeling Workflow

1. Run the pipeline on your video:
   ```bash
   python ml/tracking/pipeline.py --source data/raw_video/sample.mp4
   ```
2. Open `data/features/features.csv` in your spreadsheet editor (e.g. Excel, Google Sheets, or VS Code).
3. Open the corresponding snapshot in `data/evidence/` by matching the timestamp and `track_id`.
4. In the `label` column, enter `safe`, `risk`, or `violation`.
5. Save as `data/features/labeled_features.csv`.

---

## 4. Training the Classifiers

Run the comparison script:
```bash
python ml/classification/train_classifiers.py --features data/features/labeled_features.csv
```

The script trains **Logistic Regression**, **Decision Tree**, and **Random Forest**, prints comparison metrics (Accuracy, Macro Precision, Recall, F1), and saves the best model to `data/trained_models/classifier.pkl`.
