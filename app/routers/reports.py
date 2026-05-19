"""보호자 신고 접수 · 신고 스레드 조회/답장"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AdminReport, User, Vet
from app.routers.dependencies import get_current_user
from app.services.report_messaging import (
    AUDIENCE_REPORTER,
    add_report_message,
    create_initial_report_thread,
    filter_messages_for_reporter,
)

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportCreate(BaseModel):
    target_type: str = Field(..., pattern="^(vet|user|review|other)$")
    target_label: str = Field(..., min_length=1, max_length=255)
    reason: str = Field(..., min_length=1, max_length=5000)
    target_user_id: Optional[int] = Field(None, description="target_type=user 일 때")
    target_vet_id: Optional[int] = Field(None, description="target_type=vet 일 때")


class ReportMessageResponse(BaseModel):
    id: int
    sender_role: str
    audience: str
    body: str
    email_sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MyReportResponse(BaseModel):
    id: int
    target_type: str
    target_label: str
    reason: str
    status: str
    created_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class ReportDetailResponse(MyReportResponse):
    messages: List[ReportMessageResponse] = []


class ReportReplyCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)


def _get_reporter_report(db: Session, report_id: int, user_id: int) -> AdminReport:
    report = (
        db.query(AdminReport)
        .filter(AdminReport.id == report_id, AdminReport.reporter_user_id == user_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="신고를 찾을 수 없습니다.")
    return report


@router.get("/my", response_model=List[MyReportResponse])
def get_my_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reports = (
        db.query(AdminReport)
        .filter(AdminReport.reporter_user_id == current_user.id)
        .order_by(AdminReport.created_at.desc())
        .all()
    )
    out: List[MyReportResponse] = []
    for r in reports:
        visible = filter_messages_for_reporter(r.messages or [])
        out.append(
            MyReportResponse(
                id=r.id,
                target_type=r.target_type,
                target_label=r.target_label,
                reason=r.reason,
                status=r.status,
                created_at=r.created_at,
                message_count=len(visible),
            )
        )
    return out


@router.get("/{report_id}", response_model=ReportDetailResponse)
def get_report_detail(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_reporter_report(db, report_id, current_user.id)
    visible = filter_messages_for_reporter(report.messages or [])
    return ReportDetailResponse(
        id=report.id,
        target_type=report.target_type,
        target_label=report.target_label,
        reason=report.reason,
        status=report.status,
        created_at=report.created_at,
        message_count=len(visible),
        messages=visible,
    )


@router.get("/{report_id}/messages", response_model=List[ReportMessageResponse])
def get_report_messages(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_reporter_report(db, report_id, current_user.id)
    return filter_messages_for_reporter(report.messages or [])


@router.post("/{report_id}/messages", response_model=ReportMessageResponse, status_code=status.HTTP_201_CREATED)
def reply_to_report(
    report_id: int,
    payload: ReportReplyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_reporter_report(db, report_id, current_user.id)
    if report.status == "dismissed":
        raise HTTPException(status_code=400, detail="기각된 신고에는 답글을 남길 수 없습니다.")

    msg, _ = add_report_message(
        db,
        report=report,
        sender_role="user",
        audience=AUDIENCE_REPORTER,
        body=payload.body,
        sender_user_id=current_user.id,
        send_email_flag=False,
    )
    if report.status == "pending":
        report.status = "processing"
    db.commit()
    db.refresh(msg)
    return msg


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target_user_id = payload.target_user_id if payload.target_type == "user" else None
    target_vet_id = payload.target_vet_id if payload.target_type == "vet" else None

    if target_user_id is not None:
        if not db.query(User.id).filter(User.id == target_user_id).first():
            raise HTTPException(status_code=400, detail="신고 대상 사용자를 찾을 수 없습니다.")
    if target_vet_id is not None:
        if not db.query(Vet.id).filter(Vet.id == target_vet_id).first():
            raise HTTPException(status_code=400, detail="신고 대상 수의사를 찾을 수 없습니다.")

    r = AdminReport(
        reporter_user_id=current_user.id,
        reporter_email=current_user.email,
        target_type=payload.target_type,
        target_user_id=target_user_id,
        target_vet_id=target_vet_id,
        target_label=payload.target_label.strip(),
        reason=payload.reason.strip(),
        status="pending",
    )
    db.add(r)
    db.flush()
    create_initial_report_thread(db, r)
    db.commit()
    db.refresh(r)
    return {"id": r.id, "status": r.status}
