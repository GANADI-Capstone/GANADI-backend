from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Notification, User
from app.schemas import NotificationResponse
from app.routers.dependencies import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


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
