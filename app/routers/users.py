from typing import Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.dependencies import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


class UserMeResponse(BaseModel):
    id: int
    email: str
    nickname: str
    phone: Optional[str] = None


class UserMeUpdate(BaseModel):
    nickname: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)


@router.get("/me", response_model=UserMeResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        nickname=current_user.name,
        phone=current_user.phone,
    )


@router.put("/me", response_model=UserMeResponse)
def update_me(
    payload: UserMeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.nickname is not None:
        current_user.name = payload.nickname.strip()
    if payload.phone is not None:
        current_user.phone = payload.phone
    db.commit()
    db.refresh(current_user)
    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        nickname=current_user.name,
        phone=current_user.phone,
    )
