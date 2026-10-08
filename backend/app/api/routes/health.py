import sys
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter
from sqlalchemy import text
from app.api.deps import DbSession

router = APIRouter()


@router.get("")
def health_check(db: DbSession) -> Dict[str, Any]:
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"

    classifier_status = "not_loaded"
    try:
        project_root = Path(__file__).resolve().parents[4]
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from ml.classification.classifier import ParkingClassifier
        clf = ParkingClassifier.get_instance()
        classifier_status = "ready" if clf.is_ready else "heuristic_fallback"
    except Exception:
        pass

    return {
        "status": "ok",
        "database": db_status,
        "classifier": classifier_status,
    }
