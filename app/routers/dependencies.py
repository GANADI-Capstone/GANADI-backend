from typing import Union

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


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    현재 로그인한 관리자 반환 (role="admin"인 User만 허용)
    
    Usage:
        @router.get("/admin-protected")
        def admin_route(admin: User = Depends(get_current_admin)):
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
    
    if not hasattr(user, 'role') or user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )
    
    return user


def get_current_user_or_vet(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Union[User, Vet]:
    """보호자(User) 또는 수의사(Vet) 토큰 모두를 허용하는 통합 dependency.

    소견 단건 조회처럼 양쪽이 같은 리소스를 보지만 각자의 권한 범위가
    다른 엔드포인트에서 사용한다. 호출 측에서 isinstance(actor, Vet) 으로
    분기해 권한 검사를 수행한다.
    """

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 정보가 유효하지 않습니다.",
        )

    actor_type = payload.get("type")
    actor_id = payload.get("sub")
    if not actor_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰에 식별자가 없습니다.",
        )

    if actor_type == "user":
        user = db.query(User).filter(User.id == int(actor_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        return user

    if actor_type == "vet":
        vet = db.query(Vet).filter(Vet.id == int(actor_id)).first()
        if not vet:
            raise HTTPException(status_code=404, detail="수의사를 찾을 수 없습니다.")
        return vet

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보가 유효하지 않습니다.",
    )
