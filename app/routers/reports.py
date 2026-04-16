"""보호자 신고 접수 → 관리자가 /api/admin/reports 에서 처리"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AdminReport, User
from app.routers.dependencies import get_current_user

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportCreate(BaseModel):
    target_type: str = Field(..., pattern="^(vet|user|review|other)$")
    target_label: str = Field(..., min_length=1, max_length=255)
    reason: str = Field(..., min_length=1, max_length=5000)


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = AdminReport(
        reporter_user_id=current_user.id,
        reporter_email=current_user.email,
        target_type=payload.target_type,
        target_label=payload.target_label,
        reason=payload.reason,
        status="pending",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"id": r.id, "status": r.status}
