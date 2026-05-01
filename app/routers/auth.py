from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta
from pydantic import BaseModel
import httpx
import secrets
import logging

from app.database import get_db
from app.models import User, Vet
from app.schemas import (
    UserCreate, UserLogin, UserResponse,
    VetCreate, VetLogin, VetResponse,
    Token
)
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


# ==================== User Auth ====================
@router.post("/user/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """일반 사용자 회원가입"""
    
    # 이메일 중복 체크
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 등록된 이메일입니다."
        )
    
    # 사용자 생성
    db_user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        name=user_data.name,
        phone=user_data.phone
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


@router.post("/user/login", response_model=Token)
def login_user(user_data: UserLogin, db: Session = Depends(get_db)):
    """일반 사용자 로그인"""
    
    user = db.query(User).filter(User.email == user_data.email).first()
    
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다."
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "type": "user"},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "name": user.name,
        "role": user.role or "user",
    }


# ==================== Vet Auth ====================
@router.post("/vet/register", response_model=VetResponse, status_code=status.HTTP_201_CREATED)
def register_vet(vet_data: VetCreate, db: Session = Depends(get_db)):
    """수의사 회원가입"""
    
    # 이메일 중복 체크
    existing_vet = db.query(Vet).filter(Vet.email == vet_data.email).first()
    if existing_vet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 등록된 이메일입니다."
        )
    
    # 수의사 생성
    db_vet = Vet(
        email=vet_data.email,
        password_hash=get_password_hash(vet_data.password),
        name=vet_data.name,
        hospital_name=vet_data.hospital_name
    )
    db.add(db_vet)
    db.commit()
    db.refresh(db_vet)
    
    return db_vet


@router.post("/vet/login", response_model=Token)
def login_vet(vet_data: VetLogin, db: Session = Depends(get_db)):
    """수의사 로그인"""
    
    vet = db.query(Vet).filter(Vet.email == vet_data.email).first()
    
    if not vet or not verify_password(vet_data.password, vet.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다."
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(vet.id), "type": "vet"},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "name": vet.name,
        "role": "vet"
    }


# ==================== Kakao OAuth ====================
class KakaoCallbackRequest(BaseModel):
    code: str


@router.get("/kakao")
async def kakao_login():
    """카카오 로그인 페이지로 리다이렉트"""
    kakao_auth_url = (
        f"https://kauth.kakao.com/oauth/authorize"
        f"?client_id={settings.KAKAO_CLIENT_ID}"
        f"&redirect_uri={settings.KAKAO_REDIRECT_URI}"
        f"&response_type=code"
    )
    return RedirectResponse(url=kakao_auth_url)


@router.post("/kakao/callback", response_model=Token)
async def kakao_callback(
    callback_data: KakaoCallbackRequest,
    db: Session = Depends(get_db)
):
    """
    카카오 OAuth 콜백 처리
    
    1. 인가 코드로 액세스 토큰 발급
    2. 액세스 토큰으로 사용자 정보 조회
    3. kakao_id로 기존 유저 확인
    4. 없으면 자동 회원가입, 있으면 로그인
    5. JWT 토큰 반환
    """
    
    # 1. 카카오 액세스 토큰 발급
    token_url = "https://kauth.kakao.com/oauth/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": settings.KAKAO_CLIENT_ID,
        "redirect_uri": settings.KAKAO_REDIRECT_URI,
        "code": callback_data.code
    }
    
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                token_url,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            token_response.raise_for_status()
            token_json = token_response.json()
            access_token = token_json.get("access_token")
            
            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="카카오 액세스 토큰을 받지 못했습니다."
                )
            
            # 2. 카카오 사용자 정보 조회
            user_info_url = "https://kapi.kakao.com/v2/user/me"
            headers = {"Authorization": f"Bearer {access_token}"}
            
            user_info_response = await client.get(user_info_url, headers=headers)
            user_info_response.raise_for_status()
            user_info = user_info_response.json()
            
            kakao_id = str(user_info.get("id"))
            kakao_account = user_info.get("kakao_account", {})
            profile = kakao_account.get("profile", {})
            
            email = kakao_account.get("email")
            nickname = profile.get("nickname", "카카오 사용자")
            
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"카카오 API 호출 실패: {str(e)}"
        )
    
    # 3. kakao_id로 기존 유저 확인
    user = db.query(User).filter(User.kakao_id == kakao_id).first()
    
    # 4. 없으면 자동 회원가입
    if not user:
        # 이메일이 없는 경우 임시 이메일 생성
        if not email:
            email = f"kakao_{kakao_id}@ganadi.app"
        
        # 이메일 중복 체크 (다른 일반 회원이 이미 사용 중인 경우)
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            # 기존 유저의 kakao_id를 업데이트 (계정 연동)
            existing_user.kakao_id = kakao_id
            db.commit()
            db.refresh(existing_user)
            user = existing_user
        else:
            # 새 유저 생성
            user = User(
                email=email,
                password_hash=get_password_hash(secrets.token_urlsafe(32)),  # 랜덤 비밀번호
                name=nickname,
                kakao_id=kakao_id,
                role="user"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
    
    # 5. JWT 토큰 생성 및 반환
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jwt_token = create_access_token(
        data={"sub": str(user.id), "type": "user"},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "name": user.name,
        "role": user.role or "user"
    }
