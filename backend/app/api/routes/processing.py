import shutil
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from app.core.config import get_settings
from app.schemas.processing import ProcessingJobResponse
from app.services.pipeline_service import enqueue_processing_job, get_job, list_jobs

router = APIRouter()
settings = get_settings()


@router.post("/upload", response_model=ProcessingJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_footage(
    file: UploadFile = File(...),
    camera_id: Optional[str] = Form(None),
) -> ProcessingJobResponse:
    ext = Path(file.filename).suffix.lower()
    is_video = ext in {".mp4", ".avi", ".mov", ".mkv"}
    is_image = ext in {".jpg", ".jpeg", ".png", ".webp"}

    if not (is_video or is_image):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Upload video (.mp4, .avi) or image (.jpg, .png).",
        )

    project_root = Path(__file__).resolve().parents[4]
    dest_dir = project_root / ("data/raw_video" if is_video else "data/raw_images")
    dest_dir.mkdir(parents=True, exist_ok=True)

    saved_filename = f"{uuid.uuid4()}{ext}"
    saved_path = dest_dir / saved_filename

    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    job_res = enqueue_processing_job(
        file_path=str(saved_path),
        original_filename=file.filename,
        camera_id=camera_id,
    )
    return job_res


@router.get("/jobs", response_model=List[ProcessingJobResponse])
def get_jobs_list() -> List[ProcessingJobResponse]:
    return list_jobs()


@router.get("/jobs/{job_id}", response_model=ProcessingJobResponse)
def get_job_status(job_id: str) -> ProcessingJobResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
