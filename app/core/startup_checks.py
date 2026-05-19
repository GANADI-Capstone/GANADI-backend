"""프로덕션 기동 전 필수 설정 검증."""

from __future__ import annotations

import logging
import sys

from app.core.config import settings

logger = logging.getLogger(__name__)

_INSECURE_SECRET_MARKERS = (
    "your-secret-key",
    "change-this",
    "change-in-production",
    "dev-secret",
)


def _is_weak_secret(key: str) -> bool:
    normalized = (key or "").strip().lower()
    if len(normalized) < 32:
        return True
    return any(marker in normalized for marker in _INSECURE_SECRET_MARKERS)


def validate_production_settings(*, strict: bool = True) -> list[str]:
    """프로덕션 필수값 누락·약한 시크릿을 검사. strict=True 이면 치명적 항목에서 종료."""
    errors: list[str] = []
    warnings: list[str] = []

    if _is_weak_secret(settings.SECRET_KEY):
        errors.append("SECRET_KEY 가 비어 있거나 기본값·32자 미만입니다.")

    db_url = (settings.DATABASE_URL or "").lower()
    if "sqlite" in db_url:
        errors.append("DATABASE_URL 이 SQLite 입니다. 프로덕션은 MySQL(RDS)을 사용하세요.")
    elif settings.is_production and ("localhost" in db_url or "127.0.0.1" in db_url):
        warnings.append("DATABASE_URL 이 localhost 를 가리킵니다. RDS 엔드포인트를 확인하세요.")

    if not settings.KAKAO_CLIENT_ID:
        errors.append("KAKAO_CLIENT_ID 가 설정되지 않았습니다.")

    if settings.KAKAO_REDIRECT_USE_REFERER:
        warnings.append("KAKAO_REDIRECT_USE_REFERER=true — 프로덕션에서는 false 권장.")

    if settings.should_expose_dev_reset_link:
        errors.append(
            "EMAIL_DEV_EXPOSE_LINK=true 이고 SMTP 미설정 — 재설정 링크가 API 에 노출됩니다."
        )

    if not settings.smtp_configured:
        warnings.append("SMTP 미설정 — 비밀번호 재설정·신고 메일이 발송되지 않습니다.")

    if settings.toss_payments_configured and not settings.TOSS_WEBHOOK_SECURITY_KEY:
        warnings.append("토스 결제는 활성화됐으나 TOSS_WEBHOOK_SECURITY_KEY 가 없습니다.")

    if not settings.VAPID_PUBLIC_KEY or not settings.VAPID_PRIVATE_KEY:
        warnings.append("VAPID 키 미설정 — 컨테이너 재시작마다 푸시 구독이 무효화될 수 있습니다.")

    cors = settings.cors_origins_list
    if any("localhost" in o or "127.0.0.1" in o for o in cors):
        warnings.append("CORS_ORIGINS 에 localhost 가 포함되어 있습니다.")

    for msg in warnings:
        logger.warning("[startup] %s", msg)

    if errors:
        for msg in errors:
            logger.error("[startup] %s", msg)
        if strict:
            sys.exit(1)

    return errors + warnings
