from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

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
    
    return {"access_token": access_token, "token_type": "bearer"}


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
    
    return {"access_token": access_token, "token_type": "bearer"}
