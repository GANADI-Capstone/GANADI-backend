from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Vet
from app.core.security import decode_access_token

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    현재 로그인한 일반 사용자 반환
    
    Usage:
        @router.get("/protected")
        def protected_route(current_user: User = Depends(get_current_user)):
            ...
    """
    
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload or payload.get("type") != "user":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 정보가 유효하지 않습니다."
        )
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    
    return user


def get_current_vet(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Vet:
    """
    현재 로그인한 수의사 반환
    
    Usage:
        @router.get("/vet-protected")
        def vet_route(current_vet: Vet = Depends(get_current_vet)):
            ...
    """
    
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload or payload.get("type") != "vet":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 정보가 유효하지 않습니다."
        )
    
    vet_id = payload.get("sub")
    vet = db.query(Vet).filter(Vet.id == int(vet_id)).first()
    
    if not vet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="수의사를 찾을 수 없습니다."
        )
    
    return vet
