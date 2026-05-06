from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta
from pydantic import BaseModel, EmailStr
from typing import Optional
from urllib.parse import urlparse
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
from app.core.storage import save_vet_document

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
    
    if user.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="정지된 계정입니다. 관리자에게 문의하세요."
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
    """수의사 회원가입 (JSON; 자격증 사본 미첨부 가능 — 호환용).

    파일 첨부 가입은 `/vet/register-with-docs` (multipart/form-data) 사용을 권장.
    """
    existing_vet = db.query(Vet).filter(Vet.email == vet_data.email).first()
    if existing_vet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 등록된 이메일입니다."
        )

    db_vet = Vet(
        email=vet_data.email,
        password_hash=get_password_hash(vet_data.password),
        name=vet_data.name,
        hospital_name=vet_data.hospital_name,
        license_number=vet_data.license_number,
        approval_status="pending",
    )
    db.add(db_vet)
    db.commit()
    db.refresh(db_vet)

    return db_vet


@router.post(
    "/vet/register-with-docs",
    response_model=VetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_vet_with_docs(
    email: EmailStr = Form(...),
    password: str = Form(..., min_length=8),
    name: str = Form(..., min_length=2, max_length=100),
    hospital_name: str = Form(..., min_length=1, max_length=255),
    license_number: str = Form(..., min_length=1, max_length=50),
    license_image: UploadFile = File(..., description="수의사 면허증 사본 (이미지/PDF)"),
    employment_doc: Optional[UploadFile] = File(
        None, description="재직/개업 증명서 (선택)"
    ),
    db: Session = Depends(get_db),
):
    """수의사 회원가입 + 자격증 첨부 (multipart/form-data).

    - 면허번호 + 면허증 사본은 필수
    - 재직증명서는 선택
    - 가입 직후 approval_status="pending" 으로 저장되어 관리자 승인 대기 상태가 된다
    """
    existing = db.query(Vet).filter(Vet.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 등록된 이메일입니다.",
        )

    # 면허증 저장 (필수)
    try:
        license_bytes = await license_image.read()
        license_url = await save_vet_document(
            license_bytes, license_image.filename or "license", "license"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"면허증 업로드 실패: {e}",
        )

    # 재직증명서 저장 (선택)
    employment_url = None
    if employment_doc is not None and employment_doc.filename:
        try:
            employment_bytes = await employment_doc.read()
            if employment_bytes:
                employment_url = await save_vet_document(
                    employment_bytes,
                    employment_doc.filename or "employment",
                    "employment",
                )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"재직증명서 업로드 실패: {e}",
            )

    db_vet = Vet(
        email=email,
        password_hash=get_password_hash(password),
        name=name,
        hospital_name=hospital_name,
        license_number=license_number,
        license_image_url=license_url,
        employment_doc_url=employment_url,
        approval_status="pending",
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
    # 휴대폰 LAN 접속 등 origin 이 변할 때 frontend 가 명시적으로 알려주도록.
    # 비어 있으면 settings.KAKAO_REDIRECT_URI fallback.
    redirect_uri: Optional[str] = None


def _resolve_redirect_uri(request: Request, explicit: Optional[str] = None) -> str:
    """카카오 OAuth redirect_uri 결정.

    우선순위:
      1) 호출 측이 명시한 explicit (POST body 의 redirect_uri)
      2) Referer 헤더의 origin + /auth/kakao/callback
      3) settings.KAKAO_REDIRECT_URI (.env fallback)
    카카오 콘솔에는 사용 가능한 모든 redirect_uri 가 사전 등록되어 있어야 한다.
    """
    if explicit:
        return explicit

    referer = request.headers.get("referer", "")
    if referer:
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/auth/kakao/callback"
    return settings.KAKAO_REDIRECT_URI


@router.get("/kakao")
async def kakao_login(request: Request):
    """카카오 로그인 페이지로 리다이렉트.

    redirect_uri 는 Referer 기반으로 동적으로 결정 — PC(localhost) / 휴대폰(LAN IP)
    동일 코드로 동작하게 하기 위함.
    """
    redirect_uri = _resolve_redirect_uri(request)
    print(f"[KAKAO] /kakao login start, redirect_uri={redirect_uri}", flush=True)
    kakao_auth_url = (
        f"https://kauth.kakao.com/oauth/authorize"
        f"?client_id={settings.KAKAO_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
    )
    return RedirectResponse(url=kakao_auth_url)


@router.post("/kakao/callback", response_model=Token)
async def kakao_callback(
    callback_data: KakaoCallbackRequest,
    request: Request,
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
    redirect_uri = _resolve_redirect_uri(request, callback_data.redirect_uri)
    token_url = "https://kauth.kakao.com/oauth/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": settings.KAKAO_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "code": callback_data.code,
    }
    if settings.KAKAO_CLIENT_SECRET:
        token_data["client_secret"] = settings.KAKAO_CLIENT_SECRET

    print(f"[KAKAO] redirect_uri={redirect_uri}", flush=True)
    print(f"[KAKAO] client_id={settings.KAKAO_CLIENT_ID}", flush=True)
    print(f"[KAKAO] client_secret={'(set)' if settings.KAKAO_CLIENT_SECRET else '(empty)'}", flush=True)
    print(f"[KAKAO] code={callback_data.code[:10]}...", flush=True)

    try:
        async with httpx.AsyncClient(trust_env=False, timeout=10.0) as client:
            token_response = await client.post(
                token_url,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            print(f"[KAKAO] token response: status={token_response.status_code}, body={token_response.text}", flush=True)
            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"카카오 토큰 발급 실패: {token_response.text}"
                )
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
            print(f"[KAKAO] user_info response: status={user_info_response.status_code}", flush=True)
            if user_info_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"카카오 사용자 정보 조회 실패: {user_info_response.text}"
                )
            user_info = user_info_response.json()


            kakao_id = str(user_info.get("id"))
            kakao_account = user_info.get("kakao_account", {})
            profile = kakao_account.get("profile", {})
            
            email = kakao_account.get("email")
            nickname = profile.get("nickname", "카카오 사용자")
            
    except httpx.HTTPError as e:
        import traceback
        print(f"[KAKAO] httpx error: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
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
