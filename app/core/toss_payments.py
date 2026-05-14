"""토스페이먼츠 결제 API 호출 및 웹훅 서명 검증."""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any, Dict, Mapping, Optional, Tuple

import httpx

TOSS_API_BASE = "https://api.tosspayments.com/v1"


def _basic_auth_header(secret_key: str) -> str:
    token = base64.b64encode(f"{secret_key}:".encode()).decode()
    return f"Basic {token}"


def confirm_payment(secret_key: str, payment_key: str, order_id: str, amount: int) -> Tuple[bool, int, Dict[str, Any]]:
    """POST /payments/confirm → (ok, status_code, body)."""
    url = f"{TOSS_API_BASE}/payments/confirm"
    payload = {"paymentKey": payment_key, "orderId": order_id, "amount": amount}
    headers = {
        "Authorization": _basic_auth_header(secret_key),
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, json=payload, headers=headers)
    try:
        data = r.json()
    except Exception:
        data = {"message": r.text}
    return r.status_code == 200, r.status_code, data


def get_payment(secret_key: str, payment_key: str) -> Tuple[bool, int, Dict[str, Any]]:
    """GET /payments/{paymentKey}"""
    url = f"{TOSS_API_BASE}/payments/{payment_key}"
    headers = {"Authorization": _basic_auth_header(secret_key)}
    with httpx.Client(timeout=30.0) as client:
        r = client.get(url, headers=headers)
    try:
        data = r.json()
    except Exception:
        data = {"message": r.text}
    return r.status_code == 200, r.status_code, data


def verify_toss_webhook_signature(
    raw_body: bytes,
    headers: Mapping[str, str],
    security_key: str,
) -> bool:
    """일부 웹훅만 서명 헤더 제공. 헤더가 없으면 True (PAYMENT_STATUS_CHANGED 등)."""
    if not security_key:
        return True
    sig_header = headers.get("tosspayments-webhook-signature") or headers.get("Tosspayments-Webhook-Signature")
    transmission_time = headers.get("tosspayments-webhook-transmission-time") or headers.get(
        "Tosspayments-Webhook-Transmission-Time"
    )
    if not sig_header or not transmission_time:
        return True

    message = raw_body.decode("utf-8") + ":" + transmission_time
    expected_mac = hmac.new(security_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()

    for part in sig_header.split(","):
        part = part.strip()
        if not part.startswith("v1:"):
            continue
        b64 = part[3:]
        try:
            decoded = base64.b64decode(b64)
            if hmac.compare_digest(expected_mac, decoded):
                return True
        except Exception:
            continue
    return False
