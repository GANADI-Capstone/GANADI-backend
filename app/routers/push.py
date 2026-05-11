"""Web Push 구독 관리 API.

엔드포인트:
  GET    /api/push/public-key         — VAPID 공개키 (인증 불필요)
  POST   /api/push/subscribe          — 현재 사용자 푸시 구독 등록/갱신
  DELETE /api/push/subscribe          — 구독 해제 (endpoint 기준)
  POST   /api/push/test               — 본인에게 테스트 푸시 전송 (개발용)

설계 노트:
- 보호자(User) 와 수의사(Vet) 둘 다 구독할 수 있어 `get_current_user_or_vet`
  통합 의존성을 사용한다. 한 row 는 둘 중 한쪽만 채워진다.
- 같은 endpoint 가 다시 들어오면 keys 만 update (브라우저가 갱신할 수 있음).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.push import public_key, send_web_push
from app.database import get_db
from app.models import PushSubscription, User, Vet
from app.routers.dependencies import get_current_user_or_vet


router = APIRouter(prefix="/push", tags=["push"])


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(..., min_length=1)
    auth: str = Field(..., min_length=1)


class SubscriptionPayload(BaseModel):
    endpoint: str = Field(..., min_length=1)
    keys: SubscriptionKeys
    user_agent: Optional[str] = None


class PublicKeyResponse(BaseModel):
    public_key: str


@router.get("/public-key", response_model=PublicKeyResponse)
def get_public_key():
    """프론트엔드가 PushManager.subscribe(applicationServerKey) 에 넘길 키."""
    return PublicKeyResponse(public_key=public_key())


def _actor_to_filters(actor) -> dict:
    return (
        {"vet_id": actor.id} if isinstance(actor, Vet) else {"user_id": actor.id}
    )


@router.post("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
def subscribe(
    payload: SubscriptionPayload,
    request: Request,
    db: Session = Depends(get_db),
    actor=Depends(get_current_user_or_vet),
):
    """현재 사용자/수의사의 푸시 구독을 저장 (endpoint 기준 upsert)."""

    filters = _actor_to_filters(actor)
    existing = (
        db.query(PushSubscription)
        .filter_by(**filters)
        .filter(PushSubscription.endpoint == payload.endpoint)
        .first()
    )

    user_agent = payload.user_agent or request.headers.get("user-agent")

    if existing:
        existing.p256dh = payload.keys.p256dh
        existing.auth_secret = payload.keys.auth
        existing.user_agent = user_agent
    else:
        sub = PushSubscription(
            user_id=filters.get("user_id"),
            vet_id=filters.get("vet_id"),
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth_secret=payload.keys.auth,
            user_agent=user_agent,
        )
        db.add(sub)

    db.commit()


class UnsubscribePayload(BaseModel):
    endpoint: str = Field(..., min_length=1)


@router.delete("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(
    payload: UnsubscribePayload,
    db: Session = Depends(get_db),
    actor=Depends(get_current_user_or_vet),
):
    filters = _actor_to_filters(actor)
    deleted = (
        db.query(PushSubscription)
        .filter_by(**filters)
        .filter(PushSubscription.endpoint == payload.endpoint)
        .delete(synchronize_session=False)
    )
    db.commit()
    if deleted == 0:
        # 멱등성을 위해 404 대신 무응답
        return


@router.post("/test", status_code=status.HTTP_200_OK)
def send_test_push(
    db: Session = Depends(get_db),
    actor=Depends(get_current_user_or_vet),
):
    """본인의 모든 구독에 테스트 알림 발송. 디버그용."""

    filters = _actor_to_filters(actor)
    subs = db.query(PushSubscription).filter_by(**filters).all()
    if not subs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="등록된 푸시 구독이 없습니다.",
        )

    sent = 0
    expired = []
    for s in subs:
        info = {
            "endpoint": s.endpoint,
            "keys": {"p256dh": s.p256dh, "auth": s.auth_secret},
        }
        err = send_web_push(
            info,
            {
                "title": "GANADI 테스트 알림",
                "body": "푸시 알림이 정상적으로 동작합니다.",
                "url": "/dashboard",
                "tag": "test-push",
            },
        )
        if err is None:
            sent += 1
        else:
            status_code = getattr(getattr(err, "response", None), "status_code", None)
            if status_code in (404, 410):
                expired.append(s.id)

    if expired:
        db.query(PushSubscription).filter(PushSubscription.id.in_(expired)).delete(
            synchronize_session=False
        )
        db.commit()

    return {"sent": sent, "expired": len(expired)}
