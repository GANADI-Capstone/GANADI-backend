"""수의사 병원 프로필 API (팀 분배 문서 항목 13)

보호자 화면(카카오맵 병원 찾기, 수의사 카드, 소견 수신 화면)에서
노출될 프로필 정보를 수의사 본인이 관리한다.

- 조회:  GET /api/vets/profile  (수의사 토큰)
- 수정:  PUT /api/vets/profile  (수의사 토큰, 부분 업데이트)
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Vet
from app.routers.dependencies import get_current_vet
from app.schemas import VetProfileUpdate, VetResponse

router = APIRouter(prefix="/vets", tags=["vets"])


@router.get("/profile", response_model=VetResponse)
def get_my_profile(current_vet: Vet = Depends(get_current_vet)):
    """로그인한 수의사의 병원 프로필 조회"""
    return current_vet


@router.put("/profile", response_model=VetResponse)
def update_my_profile(
    payload: VetProfileUpdate,
    db: Session = Depends(get_db),
    current_vet: Vet = Depends(get_current_vet),
):
    """로그인한 수의사의 병원 프로필 수정 (부분 업데이트)

    요청에 포함된 필드만 갱신한다. 예를 들어 hospital_name 만 보내면
    address 등 다른 필드는 기존 값을 유지한다.
    """
    # exclude_unset=True: 요청 바디에 명시적으로 넣은 필드만 추려서
    # 나머지 컬럼이 null 로 덮이지 않게 한다.
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_vet, field, value)

    db.commit()
    db.refresh(current_vet)
    return current_vet
