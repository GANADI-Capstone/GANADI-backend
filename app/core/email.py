"""SMTP 이메일 발송 — 비밀번호 재설정·신고/관리자 안내 등."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
) -> bool:
    """이메일 발송. SMTP 미설정 시 로그만 남기고 False 반환."""
    to_email = (to_email or "").strip()
    if not to_email:
        return False

    if not settings.smtp_configured:
        logger.warning(
            "[email] SMTP 미설정 — 수신: %s | 제목: %s\n%s",
            to_email,
            subject,
            text_body,
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    from_name = (settings.EMAIL_FROM_NAME or "").strip()
    envelope_from = settings.smtp_envelope_from
    msg["From"] = (
        formataddr((from_name, envelope_from))
        if from_name
        else envelope_from
    )
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if settings.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.sendmail(envelope_from, [to_email], msg.as_string())
        elif settings.SMTP_USE_TLS:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.sendmail(envelope_from, [to_email], msg.as_string())
        else:
            # Mailpit(1025) 등 TLS/SSL 없는 로컬 SMTP
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
                smtp.ehlo()
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.sendmail(envelope_from, [to_email], msg.as_string())
        logger.info("[email] sent to %s subject=%s", to_email, subject)
        return True
    except Exception:
        logger.exception("[email] failed to=%s subject=%s", to_email, subject)
        return False
