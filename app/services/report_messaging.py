"""신고 건 메시지·이메일·알림 헬퍼."""

from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AdminReport, ReportMessage, User, Vet
from app.routers.notifications import create_notification
from app.services import mail_templates as mail

AUDIENCE_REPORTER = "reporter"
AUDIENCE_SUBJECT = "subject"
AUDIENCE_INTERNAL = "internal"


def _report_detail_url(report_id: int, *, for_vet: bool = False) -> str:
    base = (settings.FRONTEND_ORIGIN or "").rstrip("/")
    if for_vet:
        return f"{base}/vet/report-messages/{report_id}"
    return f"{base}/report/history/{report_id}"


def resolve_subject_email(db: Session, report: AdminReport) -> Optional[str]:
    if report.target_type == "vet" and report.target_vet_id:
        vet = db.query(Vet).filter(Vet.id == report.target_vet_id).first()
        return vet.email if vet else None
    if report.target_type == "user" and report.target_user_id:
        user = db.query(User).filter(User.id == report.target_user_id).first()
        return user.email if user else None
    return None


def resolve_subject_name(db: Session, report: AdminReport) -> Optional[str]:
    if report.target_type == "vet" and report.target_vet_id:
        vet = db.query(Vet).filter(Vet.id == report.target_vet_id).first()
        return vet.name if vet else report.target_label
    if report.target_type == "user" and report.target_user_id:
        user = db.query(User).filter(User.id == report.target_user_id).first()
        return user.name if user else report.target_label
    return report.target_label


def message_visible_to_reporter(msg: ReportMessage) -> bool:
    if msg.audience == AUDIENCE_INTERNAL:
        return False
    if msg.audience == AUDIENCE_SUBJECT and msg.sender_role not in ("user",):
        return False
    return msg.audience == AUDIENCE_REPORTER or msg.sender_role == "user"


def message_visible_to_subject(msg: ReportMessage) -> bool:
    if msg.audience == AUDIENCE_INTERNAL:
        return False
    return msg.audience == AUDIENCE_SUBJECT or msg.sender_role == "vet"


def filter_messages_for_reporter(messages: Iterable[ReportMessage]) -> List[ReportMessage]:
    return [m for m in messages if message_visible_to_reporter(m)]


def filter_messages_for_subject(messages: Iterable[ReportMessage]) -> List[ReportMessage]:
    return [m for m in messages if message_visible_to_subject(m)]


def _notify_admin_reporter_reply(report: AdminReport, body: str) -> None:
    if settings.ADMIN_NOTIFY_EMAIL:
        mail.send_report_reporter_reply_to_admin(
            to_email=settings.ADMIN_NOTIFY_EMAIL,
            report_id=report.id,
            reporter_email=report.reporter_email or "—",
            message_body=body,
        )


def add_report_message(
    db: Session,
    *,
    report: AdminReport,
    sender_role: str,
    audience: str,
    body: str,
    sender_user_id: Optional[int] = None,
    sender_vet_id: Optional[int] = None,
    send_email_flag: bool = False,
) -> Tuple[ReportMessage, bool]:
    msg = ReportMessage(
        report_id=report.id,
        sender_role=sender_role,
        sender_user_id=sender_user_id,
        sender_vet_id=sender_vet_id,
        audience=audience,
        body=body.strip(),
        email_sent=False,
    )
    db.add(msg)
    db.flush()

    emailed = False
    if send_email_flag and audience != AUDIENCE_INTERNAL:
        emailed = _dispatch_message_email(db, report, msg)
        msg.email_sent = emailed
    elif sender_role == "user" and audience == AUDIENCE_REPORTER:
        _notify_admin_reporter_reply(report, msg.body)

    _dispatch_in_app_notification(db, report, msg)
    return msg, emailed


def _dispatch_in_app_notification(db: Session, report: AdminReport, msg: ReportMessage) -> None:
    if msg.audience == AUDIENCE_INTERNAL:
        return

    preview = msg.body[:120] + ("…" if len(msg.body) > 120 else "")
    url = _report_detail_url(report.id)

    if msg.audience == AUDIENCE_REPORTER and report.reporter_user_id:
        create_notification(
            db,
            user_id=report.reporter_user_id,
            message=f"[신고 #{report.id}] {preview}",
            type="report_message",
            url=url,
        )
    elif msg.audience == AUDIENCE_SUBJECT:
        if report.target_type == "user" and report.target_user_id:
            create_notification(
                db,
                user_id=report.target_user_id,
                message=f"[관리자 안내] {preview}",
                type="admin_notice",
                url=url,
            )


def _dispatch_message_email(db: Session, report: AdminReport, msg: ReportMessage) -> bool:
    if msg.audience == AUDIENCE_REPORTER:
        if not report.reporter_email:
            return False
        return mail.send_report_message_to_reporter(
            to_email=report.reporter_email,
            report_id=report.id,
            target_label=report.target_label,
            message_body=msg.body,
            detail_url=_report_detail_url(report.id),
            from_admin=(msg.sender_role == "admin"),
        )

    if msg.audience == AUDIENCE_SUBJECT:
        to_email = resolve_subject_email(db, report)
        if not to_email:
            return False
        name = resolve_subject_name(db, report) or report.target_label
        if report.target_type == "vet":
            return mail.send_report_message_to_vet(
                to_email=to_email,
                vet_name=name,
                report_id=report.id,
                message_body=msg.body,
                detail_url=_report_detail_url(report.id, for_vet=True),
            )
        if report.target_type == "user":
            return mail.send_report_message_to_user(
                to_email=to_email,
                user_name=name,
                report_id=report.id,
                message_body=msg.body,
                detail_url=_report_detail_url(report.id),
            )

    return False


def create_initial_report_thread(db: Session, report: AdminReport) -> None:
    detail_url = _report_detail_url(report.id)

    if report.reporter_email:
        mail.send_report_submitted_to_reporter(
            to_email=report.reporter_email,
            report_id=report.id,
            target_label=report.target_label,
            detail_url=detail_url,
        )

    add_report_message(
        db,
        report=report,
        sender_role="system",
        audience=AUDIENCE_REPORTER,
        body=(
            "신고가 접수되었습니다. 관리자 검토 후 이 공간에서 추가 안내를 드립니다. "
            "필요하면 아래에 답글을 남겨 주세요."
        ),
        send_email_flag=False,
    )

    if settings.ADMIN_NOTIFY_EMAIL:
        mail.send_report_submitted_to_admin(
            to_email=settings.ADMIN_NOTIFY_EMAIL,
            report_id=report.id,
            target_type=report.target_type,
            target_label=report.target_label,
            reporter_email=report.reporter_email or "—",
            reason=report.reason,
        )
