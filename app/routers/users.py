from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.dependencies import get_current_user
from app.core.security import verify_password, get_password_hash
from app.core.storage import save_image

router = APIRouter(prefix="/users", tags=["users"])


class UserMeResponse(BaseModel):
    id: int
    email: str
    nickname: str
    phone: Optional[str] = None


class UserMeUpdate(BaseModel):
    nickname: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


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


@router.put("/me/password", status_code=status.HTTP_200_OK)
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """현재 사용자의 비밀번호 변경"""
    
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="현재 비밀번호가 올바르지 않습니다."
        )
    
    current_user.password_hash = get_password_hash(payload.new_password)
    db.commit()
    
    return {"message": "비밀번호가 성공적으로 변경되었습니다."}


@router.post("/me/profile-image")
async def upload_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """현재 사용자의 프로필 사진 업로드"""
    
    # 파일 형식 검증
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미지 파일만 업로드 가능합니다."
        )
    
    # 파일 크기 검증 (5MB 제한)
    file_bytes = await file.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파일 크기는 5MB 이하여야 합니다."
        )
    
    # 이미지 저장 (S3 또는 로컬)
    try:
        image_url = await save_image(file_bytes, file.filename or "profile.jpg")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"이미지 업로드 실패: {str(e)}"
        )
    
    # User 모델의 profile_image_url 업데이트
    current_user.profile_image_url = image_url
    db.commit()
    db.refresh(current_user)
    
    return {"profile_image_url": image_url}
