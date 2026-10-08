from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel


class ProcessingJobResponse(BaseModel):
    job_id: str
    status: str  # queued | processing | completed | failed
    message: str
    filename: str
    camera_id: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    result_summary: Optional[Dict[str, Any]] = None
