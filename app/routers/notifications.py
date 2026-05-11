import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.push import send_web_push
from app.database import get_db
from app.models import Notification, PushSubscription, User
from app.routers.dependencies import get_current_user
from app.schemas import NotificationResponse


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])


# ==================== 알림 생성 + 푸시 헬퍼 ====================
def create_notification(
    db: Session,
    *,
    user_id: int,
    message: str,
    type: str,
    url: Optional[str] = None,
) -> Notification:
    """알림 DB row 를 만들고 등록된 모든 Web Push 구독에도 동일 메시지를 발송.

    - 커밋은 호출자가 트랜잭션 단위로 직접 처리한다.
    - push 전송 실패는 무시하고 만료 (404/410) 구독만 즉시 정리.
    """

    notification = Notification(user_id=user_id, message=message, type=type)
    db.add(notification)
    db.flush()

    subs = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == user_id)
        .all()
    )
    expired_ids: list[int] = []
    payload = {
        "title": "GANADI 알림",
        "body": message,
        "url": url or "/notifications",
        "tag": f"notif-{notification.id}",
        "type": type,
    }
    for s in subs:
        info = {
            "endpoint": s.endpoint,
            "keys": {"p256dh": s.p256dh, "auth": s.auth_secret},
        }
        err = send_web_push(info, payload)
        if err is not None:
            status_code = getattr(getattr(err, "response", None), "status_code", None)
            if status_code in (404, 410):
                expired_ids.append(s.id)

    if expired_ids:
        db.query(PushSubscription).filter(PushSubscription.id.in_(expired_ids)).delete(
            synchronize_session=False
        )

    return notification


@router.get("", response_model=List[NotificationResponse])
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """내 알림 목록 조회 (최신순)"""

    notifications = db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).all()

    return notifications


# NOTE: /read-all 은 /{notification_id} 보다 먼저 선언해야 한다.
# FastAPI 는 선언 순서대로 라우트를 매칭하므로, 순서가 바뀌면 "read-all" 문자열이
# {notification_id: int} 로 파싱되어 422 가 발생한다.
@router.patch("/read-all", status_code=status.HTTP_200_OK)
def mark_all_notifications_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """전체 알림 읽음 처리"""

    updated_count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True})

    db.commit()

    return {
        "message": "모든 알림을 읽음 처리했습니다.",
        "updated_count": updated_count
    }


@router.patch("/{notification_id}", response_model=NotificationResponse)
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """특정 알림 읽음 처리"""

    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="알림을 찾을 수 없습니다."
        )

    notification.is_read = True
    db.commit()
    db.refresh(notification)

    return notification
