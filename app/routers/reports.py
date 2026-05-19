"""보호자 신고 접수 → 관리자가 /api/admin/reports 에서 처리"""

from typing import Optional, List
from datetime import datetime

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


class MyReportResponse(BaseModel):
    id: int
    target_type: str
    target_label: str
    reason: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.get("/my", response_model=List[MyReportResponse])
def get_my_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """현재 로그인한 사용자가 접수한 신고 목록 조회"""
    
    reports = db.query(AdminReport).filter(
        AdminReport.reporter_user_id == current_user.id
    ).order_by(AdminReport.created_at.desc()).all()
    
    return reports


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
