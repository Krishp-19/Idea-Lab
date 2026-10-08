# Build Brief: AI-Assisted Illegal Parking Detection System for Two-Wheelers

## Reference repositories (use as architectural starting points, not to be copied verbatim)
- Backend + dashboard + case-review pattern: `reference-stvis/` (original: RavenS404/STVIS)
- Detection + tracking + live-dashboard pattern: `reference-multicam/` (original: SSG-YERRAMSETTI/multi-camera-tracking)

## Where to build the real project
Build the actual project in the top-level folders already scaffolded here: `backend/`, `ml/`, `frontend/`, `data/`, `docker/`. Do not edit inside `reference-stvis/` or `reference-multicam/` — read them for patterns only.

## Goal
Build a **complete, working, end-to-end system** — not a mockup, not a prototype with placeholder logic, not stubbed API responses. Every stage must run on real images/video I provide and produce real output. If a stage cannot be fully implemented without data I haven't provided yet (e.g. a trained model), implement the full training pipeline so I can run it myself the moment I supply images, rather than hardcoding fake results.

## What the system must do
1. Accept CCTV footage or images of a two-wheeler parking area as input (I will supply my own images/video into `data/raw_images/` and `data/raw_video/` — do not rely on any pre-existing public dataset for the final model; use a public dataset like COCO or a two-wheeler dataset only for initial pretrained weights/transfer learning).
2. Detect two-wheelers only (motorcycles/scooters) — filter out cars, buses, people, and other classes.
3. Track each detected vehicle across frames with a persistent ID (ByteTrack or DeepSORT), and distinguish a **parked** vehicle from a **passing** vehicle using dwell-time filtering (a vehicle stationary beyond a configurable time threshold counts as "parked").
4. For each parked vehicle, compute features that describe its parking behavior:
   - Position relative to the designated bay/zone (inside/outside boundary)
   - Orientation angle relative to the bay's expected angle
   - Spacing/distance to neighboring parked vehicles
   - Parking sequence (whether it was parked in the expected order relative to other bays/slots, e.g. skipping empty bays to park elsewhere)
   - Whether it obstructs a marked walkway/fire-lane zone
5. Feed these engineered features into classical ML classifiers — train and compare **Logistic Regression, Decision Tree, and Random Forest** — to classify each parked vehicle as **Safe / Risk / Violation**. Report accuracy, precision, recall, F1-score, and confusion matrix for each model, and pick the best-performing one as default.
6. Store every detection, track, feature set, and classification result in **PostgreSQL** (design a real schema: vehicles, tracks, frames/evidence, violations, zones).
7. Expose all of this through a **FastAPI** backend with REST endpoints for: live/batch video processing, violation listing, evidence image/snapshot retrieval, zone configuration (so I can define bay boundaries and expected angles per site), and trend/heatmap data.
8. Build a **React dashboard** (the "authority-facing dashboard") that shows: live or processed-feed view with bounding boxes and violation flags, a violations list with evidence snapshots and timestamps, trend charts and a violation heatmap by zone, and a way for a human reviewer to confirm/dismiss a flagged violation (final verification stays human — do not auto-escalate to enforcement).
9. Package the whole thing with **Docker / docker-compose** so the FastAPI backend, PostgreSQL, and React frontend all run with one command.

## Training pipeline (must be fully functional, not just described)
- Provide an annotation-ready folder structure (`data/annotations/`) and instructions compatible with **LabelImg or CVAT** output (see `ml/annotation/README.md`), and a script to convert those annotations into YOLO training format.
- `ml/detection/train_yolo.py` must fine-tune YOLOv8 (or current YOLO-family) on my annotated images in `data/annotations/`, producing a custom two-wheeler detection model saved to `data/trained_models/`.
- `ml/zone_config/zone_drawer.py` must be an interactive tool (polygon/line drawer) where I mark each bay's boundary and correct orientation on a sample frame from my own footage, saved to a config file the pipeline reads at runtime.
- `ml/classification/train_classifiers.py` must train the Safe/Risk/Violation classifiers on labeled feature data. Document exactly what a labeled row should look like so I can build the label set from flagged frames.

## Explicit constraints
- No hardcoded "demo" detections, no dummy JSON standing in for the ML output — every dashboard number must come from the real pipeline.
- Every model (detector and classifiers) must be retrainable by me on my own data, with clear commands for retraining.
- Keep configuration (zone definitions, thresholds, DB credentials) out of code and in config files / environment variables so I can adapt it to a different parking lot without touching source code.
- Document, in `README.md`, exactly which commands to run in order: (1) annotate data, (2) train detector, (3) define zones, (4) run pipeline to generate features, (5) label and train classifiers, (6) launch full stack with Docker.

## Build order (do not skip ahead)
1. Scaffold + confirm project structure
2. Detection pipeline (`ml/detection/`)
3. Tracking + dwell-time filtering (`ml/tracking/`)
4. Zone config tool (`ml/zone_config/`)
5. Feature engineering (`ml/feature_engineering/`)
6. Classifier training + inference (`ml/classification/`)
7. Backend + PostgreSQL schema (`backend/`)
8. React dashboard (`frontend/`)
9. Docker packaging (`docker/`)

## Deliverables checklist (must all be present and runnable)
- [ ] Detection + tracking pipeline (Python)
- [ ] Zone/angle configuration tool
- [ ] Feature engineering module
- [ ] ML classification training + inference (Logistic Regression, Decision Tree, Random Forest, with comparison metrics)
- [ ] FastAPI backend with PostgreSQL
- [ ] React dashboard
- [ ] Docker/docker-compose setup
- [ ] README with exact run order and retraining instructions
