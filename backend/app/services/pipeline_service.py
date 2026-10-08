import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.camera import Camera
from app.models.parking_event import ParkingEvent
from app.models.vehicle import Vehicle
from app.models.violation import Violation
from app.models.zone import Zone
from app.schemas.processing import ProcessingJobResponse

settings = get_settings()

# In-memory jobs dictionary
JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def get_job(job_id: str) -> Optional[ProcessingJobResponse]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return None
        return ProcessingJobResponse(**job)


def list_jobs() -> list:
    with JOBS_LOCK:
        return [ProcessingJobResponse(**job) for job in reversed(list(JOBS.values()))]


def enqueue_processing_job(
    file_path: str,
    original_filename: str,
    camera_id: Optional[str] = None,
) -> ProcessingJobResponse:
    job_id = str(uuid.uuid4())
    job_data = {
        "job_id": job_id,
        "status": "queued",
        "message": "Processing job is queued",
        "filename": original_filename,
        "camera_id": camera_id,
        "created_at": datetime.now(timezone.utc),
        "completed_at": None,
        "result_summary": None,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job_data

    thread = threading.Thread(
        target=_run_job_worker,
        args=(job_id, file_path, camera_id),
        daemon=True,
    )
    thread.start()

    return ProcessingJobResponse(**job_data)


def _run_job_worker(job_id: str, file_path: str, camera_id: Optional[str]) -> None:
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id]["status"] = "processing"
            JOBS[job_id]["message"] = "Analyzing footage and tracking two-wheelers..."

    db: Session = SessionLocal()
    try:
        root = get_project_root()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        from ml.tracking.pipeline import VideoProcessor

        def db_callback(track, feat_row, snapshot_path: Optional[str], label_result: Dict[str, Any]):
            # Runs whenever a parking event is triggered
            _record_parking_event(db, track, feat_row, snapshot_path, label_result, camera_id)

        processor = VideoProcessor(db_callback=db_callback)
        summary = processor.process(source=file_path)

        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["status"] = "completed"
                JOBS[job_id]["message"] = f"Finished. Found {summary.get('parking_events', 0)} parking events."
                JOBS[job_id]["completed_at"] = datetime.now(timezone.utc)
                JOBS[job_id]["result_summary"] = summary

    except Exception as e:
        print(f"[PipelineService] Job {job_id} error: {e}")
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["status"] = "failed"
                JOBS[job_id]["message"] = f"Error during processing: {str(e)}"
                JOBS[job_id]["completed_at"] = datetime.now(timezone.utc)
    finally:
        db.close()


def _record_parking_event(
    db: Session,
    track,
    feat_row,
    snapshot_path: Optional[str],
    label_result: Dict[str, Any],
    camera_id: Optional[str],
) -> None:
    try:
        now = datetime.now(timezone.utc)

        # 1. Upsert Vehicle
        track_id = int(track.track_id)
        stmt = select(Vehicle).where(Vehicle.track_id == track_id)
        if camera_id:
            stmt = stmt.where(Vehicle.camera_id == camera_id)
        veh = db.scalar(stmt)

        if not veh:
            veh = Vehicle(
                track_id=track_id,
                camera_id=camera_id,
                class_name=track.class_name,
                thumbnail_path=snapshot_path,
                first_seen=now,
                last_seen=now,
            )
            db.add(veh)
            db.flush()
        else:
            veh.last_seen = now
            if snapshot_path and not veh.thumbnail_path:
                veh.thumbnail_path = snapshot_path

        # 2. Resolve matching Zone record
        zone_db_id = None
        if feat_row.zone_id and feat_row.zone_id != "none":
            z = db.scalar(select(Zone).where(Zone.zone_id == feat_row.zone_id))
            if z:
                zone_db_id = z.id

        # 3. Create ParkingEvent
        ml_label = label_result.get("label", "pending")
        ml_conf = label_result.get("confidence", 0.0)
        ml_probs = label_result.get("probabilities", {})

        pe = ParkingEvent(
            vehicle_id=veh.id,
            zone_id=zone_db_id,
            started_at=now,
            dwell_seconds=float(getattr(track, "dwell_seconds", 0.0)),
            features=feat_row.to_dict(),
            ml_label=ml_label,
            ml_confidence=ml_conf,
            ml_probabilities=ml_probs,
            snapshot_path=snapshot_path,
        )
        db.add(pe)
        db.flush()

        # 4. Create Violation record (safe, risk, or violation are all logged for audit & human review)
        v = Violation(
            parking_event_id=pe.id,
            label=ml_label,
            review_status="pending",
        )
        db.add(v)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[PipelineService] DB recording error: {e}")
