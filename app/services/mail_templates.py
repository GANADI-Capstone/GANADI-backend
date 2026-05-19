"""메일 종류별 제목·본문 템플릿 + 발송 래퍼."""

from __future__ import annotations

from html import escape
from typing import Optional

from app.core.config import settings
from app.core.email import send_email

SUPPORT = "support@peteyeai.com"
BRAND = "PET EYE AI"


def _html_page(*, title: str, lead: str, body: str, cta_url: Optional[str] = None, cta_label: str = "앱에서 확인") -> str:
    cta = ""
    if cta_url:
        cta = (
            f'<p style="margin:24px 0">'
            f'<a href="{escape(cta_url)}" style="display:inline-block;padding:12px 20px;'
            f'background:#2563eb;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">'
            f"{escape(cta_label)}</a></p>"
        )
    return f"""<!DOCTYPE html>
<html lang="ko">
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;padding:24px">
  <div style="max-width:560px;margin:0 auto;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:28px">
    <p style="margin:0 0 8px;font-size:12px;color:#64748b;font-weight:600">{escape(BRAND)}</p>
    <h1 style="margin:0 0 12px;font-size:20px;color:#0f172a">{escape(title)}</h1>
    <p style="margin:0 0 16px;color:#475569;line-height:1.6">{escape(lead)}</p>
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;color:#334155;
                white-space:pre-wrap;line-height:1.6">{body}</div>
    {cta}
    <p style="margin:24px 0 0;font-size:12px;color:#94a3b8">문의: {escape(SUPPORT)}</p>
  </div>
</body>
</html>"""


def _text_footer() -> str:
    return f"\n\n— {BRAND}\n문의: {SUPPORT}"


# ── 비밀번호 재설정 ──────────────────────────────────────────
def send_password_reset_email(*, to_email: str, reset_url: str, account_label: str) -> bool:
    minutes = settings.PASSWORD_RESET_EXPIRE_MINUTES
    subject = f"[{BRAND}] {account_label} 비밀번호 재설정"
    text = (
        f"{account_label} 계정 비밀번호 재설정을 요청하셨습니다.\n\n"
        f"아래 링크에서 새 비밀번호를 설정해 주세요 (유효 {minutes}분):\n"
        f"{reset_url}\n\n"
        "본인이 요청하지 않았다면 이 메일을 무시해 주세요."
        + _text_footer()
    )
    html = _html_page(
        title="비밀번호 재설정",
        lead=f"{account_label} 계정의 새 비밀번호를 설정해 주세요. 링크는 {minutes}분간 유효합니다.",
        body="본인이 요청하지 않았다면 이 메일을 무시해 주세요.",
        cta_url=reset_url,
        cta_label="새 비밀번호 설정",
    )
    return send_email(to_email=to_email, subject=subject, text_body=text, html_body=html)


# ── 신고 접수 (신고자) ─────────────────────────────────────
def send_report_submitted_to_reporter(
    *,
    to_email: str,
    report_id: int,
    target_label: str,
    detail_url: str,
) -> bool:
    subject = f"[{BRAND}] 신고 #{report_id} 접수 완료"
    text = (
        f"신고가 정상적으로 접수되었습니다. (신고 #{report_id})\n\n"
        f"신고 대상: {target_label}\n\n"
        "관리자 검토 후 앱 내 대화 공간과 이메일로 추가 안내를 드립니다.\n"
        "필요하면 앱에서 답글을 남겨 주세요.\n\n"
        f"내 신고 확인: {detail_url}"
        + _text_footer()
    )
    html = _html_page(
        title=f"신고 #{report_id} 접수 완료",
        lead="관리자 검토 후 이 메일과 앱 알림으로 추가 안내를 드립니다.",
        body=f"신고 대상: {target_label}\n\n필요하면 앱에서 관리자에게 답글을 남길 수 있습니다.",
        cta_url=detail_url,
        cta_label="내 신고 · 대화 보기",
    )
    return send_email(to_email=to_email, subject=subject, text_body=text, html_body=html)


# ── 신고 접수 (관리자 알림) ─────────────────────────────────
def send_report_submitted_to_admin(
    *,
    to_email: str,
    report_id: int,
    target_type: str,
    target_label: str,
    reporter_email: str,
    reason: str,
) -> bool:
    subject = f"[{BRAND}] [관리자] 신규 신고 #{report_id}"
    text = (
        f"신규 신고가 접수되었습니다.\n\n"
        f"신고 번호: #{report_id}\n"
        f"유형: {target_type}\n"
        f"대상: {target_label}\n"
        f"신고자: {reporter_email}\n\n"
        f"사유:\n{reason}"
        + _text_footer()
    )
    html = _html_page(
        title=f"신규 신고 #{report_id}",
        lead="관리자 대시보드 → 신고 탭에서 확인·답변해 주세요.",
        body=(
            f"유형: {target_type}\n"
            f"대상: {target_label}\n"
            f"신고자: {reporter_email}\n\n"
            f"사유:\n{escape(reason)}"
        ),
    )
    return send_email(to_email=to_email, subject=subject, text_body=text, html_body=html)


# ── 신고 스레드 — 신고자에게 ───────────────────────────────
def send_report_message_to_reporter(
    *,
    to_email: str,
    report_id: int,
    target_label: str,
    message_body: str,
    detail_url: str,
    from_admin: bool = True,
) -> bool:
    who = "관리자" if from_admin else "시스템"
    subject = f"[{BRAND}] 신고 #{report_id} — {who} 답변"
    text = (
        f"신고 #{report_id} ({target_label}) 관련 {who} 메시지입니다.\n\n"
        f"{message_body}\n\n"
        f"앱에서 답글: {detail_url}"
        + _text_footer()
    )
    html = _html_page(
        title=f"신고 #{report_id} — {who} 메시지",
        lead=f"신고 대상: {target_label}",
        body=escape(message_body),
        cta_url=detail_url,
        cta_label="답글 남기기",
    )
    return send_email(to_email=to_email, subject=subject, text_body=text, html_body=html)


# ── 신고 스레드 — 피신고 수의사 ───────────────────────────
def send_report_message_to_vet(
    *,
    to_email: str,
    vet_name: str,
    report_id: int,
    message_body: str,
    detail_url: str,
) -> bool:
    subject = f"[{BRAND}] [수의사 안내] 신고 #{report_id} 관련"
    text = (
        f"{vet_name} 수의사님, 안녕하세요.\n\n"
        f"PET EYE AI 운영팀입니다. 신고 #{report_id} 건과 관련하여 안내드립니다.\n\n"
        f"{message_body}\n\n"
        f"앱에서 확인·답변: {detail_url}\n\n"
        "본 메일은 서비스 이용 관련 공식 안내입니다."
        + _text_footer()
    )
    html = _html_page(
        title="운영팀 안내",
        lead=f"{vet_name} 수의사님, 신고 #{report_id} 건과 관련된 안내입니다.",
        body=escape(message_body),
        cta_url=detail_url,
        cta_label="관리자 안내 확인",
    )
    return send_email(to_email=to_email, subject=subject, text_body=text, html_body=html)


# ── 신고 스레드 — 피신고 보호자 ───────────────────────────
def send_report_message_to_user(
    *,
    to_email: str,
    user_name: str,
    report_id: int,
    message_body: str,
    detail_url: str,
) -> bool:
    subject = f"[{BRAND}] [운영 안내] 신고 #{report_id} 관련"
    text = (
        f"{user_name}님, 안녕하세요.\n\n"
        f"PET EYE AI 운영팀입니다.\n\n"
        f"{message_body}\n\n"
        f"앱에서 확인: {detail_url}"
        + _text_footer()
    )
    html = _html_page(
        title="운영팀 안내",
        lead=f"{user_name}님, 서비스 이용과 관련하여 안내드립니다.",
        body=escape(message_body),
        cta_url=detail_url,
        cta_label="앱에서 확인",
    )
    return send_email(to_email=to_email, subject=subject, text_body=text, html_body=html)


# ── 신고자 답글 → 관리자 알림 ─────────────────────────────
def send_report_reporter_reply_to_admin(
    *,
    to_email: str,
    report_id: int,
    reporter_email: str,
    message_body: str,
) -> bool:
    subject = f"[{BRAND}] [관리자] 신고 #{report_id} — 신고자 답글"
    text = (
        f"신고 #{report_id}에 신고자({reporter_email}) 답글이 도착했습니다.\n\n"
        f"{message_body}"
        + _text_footer()
    )
    html = _html_page(
        title=f"신고 #{report_id} — 신고자 답글",
        lead=f"신고자: {reporter_email}",
        body=escape(message_body),
    )
    return send_email(to_email=to_email, subject=subject, text_body=text, html_body=html)
