#!/usr/bin/env python3
"""SMTP 연결 테스트 — backend 디렉터리에서: python scripts/test_smtp.py [수신이메일]"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.services.mail_templates import send_password_reset_email


def main() -> int:
    to = (sys.argv[1] if len(sys.argv) > 1 else settings.SMTP_USER or "").strip()
    if not to:
        print("사용법: python scripts/test_smtp.py 수신@email.com")
        return 1

    print(f"SMTP_HOST={settings.SMTP_HOST} configured={settings.smtp_configured}")
    if not settings.smtp_configured:
        print("SMTP 미설정 — backend/.env 에 SMTP_PASSWORD 등을 확인하세요.")
        return 1

    ok = send_password_reset_email(
        to_email=to,
        reset_url=f"{settings.password_reset_url_base}?token=test&account=user",
        account_label="테스트",
    )
    print("발송 성공" if ok else "발송 실패 — 터미널 로그 확인")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
