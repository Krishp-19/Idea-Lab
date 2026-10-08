from datetime import datetime
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.deps import DbSession, get_current_user
from app.models.user import User
from app.schemas.common import MessageResponse, PageMeta, PaginatedResponse
from app.schemas.violation import ViolationDetail, ViolationReviewRequest
from app.services.violation_service import get_violation_detail, list_violations, review_violation

router = APIRouter()


@router.get("", response_model=PaginatedResponse[ViolationDetail])
def get_violations(
    db: DbSession,
    status: Optional[str] = Query(None, description="pending | confirmed | dismissed"),
    label: Optional[str] = Query(None, description="safe | risk | violation"),
    zone_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ViolationDetail]:
    items, total = list_violations(
        db=db,
        status=status,
        label=label,
        zone_id=zone_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=items,
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/{violation_id}", response_model=ViolationDetail)
def get_violation(violation_id: str, db: DbSession) -> ViolationDetail:
    item = get_violation_detail(db, violation_id=violation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Violation record not found")
    return item


@router.patch("/{violation_id}/review", response_model=MessageResponse)
def review_violation_route(
    violation_id: str,
    payload: ViolationReviewRequest,
    db: DbSession,
    current_user: Annotated[Optional[User], Depends(get_current_user)] = None,
) -> MessageResponse:
    user_id = current_user.id if current_user else None
    v = review_violation(
        db=db,
        violation_id=violation_id,
        action=payload.action.lower(),
        user_id=user_id,
        notes=payload.notes,
    )
    if not v:
        raise HTTPException(status_code=404, detail="Violation record not found")
    return MessageResponse(message=f"Violation status updated to {v.review_status}")
