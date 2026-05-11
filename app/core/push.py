"""Web Push (VAPID) 인프라.

- 부팅 시점에 VAPID 키 쌍을 확보한다.
  · 환경변수(`VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY`) 가 있으면 그걸 사용
  · 없으면 `backend/vapid_keys.json` 에서 로드, 그것도 없으면 새로 생성해 저장
- 단일 전송 함수 `send_web_push(subscription_dict, payload_dict)` 를 제공한다.

브라우저 표준에 맞춰 공개키는 raw EC P-256 압축되지 않은 점(65바이트) 의
URL-safe base64 인코딩으로 노출한다. py_vapid 가 같은 형식으로 키를 만들어
준다.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any, Mapping, Optional

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid01
from pywebpush import WebPushException, webpush

from app.core.config import settings


logger = logging.getLogger(__name__)

VAPID_KEY_FILE = Path(__file__).resolve().parents[2] / "vapid_keys.json"


class _PushKeys:
    public_key: str = ""
    private_pem: str = ""
    subject: str = settings.VAPID_SUBJECT or "mailto:noreply@ganadi.dev"


keys = _PushKeys()


def _load_or_generate_keys() -> None:
    """우선순위: env 변수 → 파일 → 새로 생성."""

    if settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY:
        keys.public_key = settings.VAPID_PUBLIC_KEY
        keys.private_pem = settings.VAPID_PRIVATE_KEY
        return

    if VAPID_KEY_FILE.exists():
        try:
            data = json.loads(VAPID_KEY_FILE.read_text())
            keys.public_key = data["public_key"]
            keys.private_pem = data["private_pem"]
            return
        except Exception as e:  # noqa: BLE001
            logger.warning("VAPID key file invalid, regenerating: %s", e)

    # 새로 생성
    vapid = Vapid01()
    vapid.generate_keys()
    # 공개키 — uncompressed point (65 bytes) URL-safe base64 (padding 제거)
    raw = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    public_b64 = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    # 개인키 — PEM 문자열 (pywebpush 가 사용)
    private_pem = vapid.private_pem().decode("utf-8")

    keys.public_key = public_b64
    keys.private_pem = private_pem
    try:
        VAPID_KEY_FILE.write_text(
            json.dumps({"public_key": public_b64, "private_pem": private_pem}, indent=2)
        )
        logger.info("VAPID keys generated and saved: %s", VAPID_KEY_FILE)
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to persist VAPID keys: %s", e)


_load_or_generate_keys()


def public_key() -> str:
    """프론트에서 사용할 VAPID 공개키 (base64url)."""
    return keys.public_key


def send_web_push(
    subscription: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    ttl: int = 60 * 60 * 24,
) -> Optional[Exception]:
    """단일 푸시 전송. 실패하면 예외 객체를 반환하고, 성공이면 None.

    payload 는 SW 의 push 이벤트에서 `event.data.json()` 으로 파싱한다.
    호출 측은 None / 401 (구독 만료) 여부로 DB 정리를 결정.
    """

    try:
        webpush(
            subscription_info=dict(subscription),
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=keys.private_pem,
            vapid_claims={"sub": keys.subject},
            ttl=ttl,
        )
        return None
    except WebPushException as e:
        logger.warning(
            "Web push failed (status=%s): %s",
            e.response.status_code if e.response is not None else None,
            e,
        )
        return e
    except Exception as e:  # noqa: BLE001
        logger.warning("Web push unexpected error: %s", e)
        return e
