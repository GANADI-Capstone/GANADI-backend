"""수의사 소견 관련 API

담당 범위 (팀 분배 문서 항목 8~14):
  - 보호자: 진단 결과에 대해 특정 수의사에게 소견을 요청
  - 수의사: 받은 요청 목록 조회, 소견 작성, 작성된 소견 수정
  - 보호자: 수신한 소견 상세 조회

라우팅 정책:
  - 보호자 토큰 필요:  POST /request, GET /{diagnosis_id}
  - 수의사 토큰 필요:  GET /requests, POST /{opinion_id}, PUT /{opinion_id}
  - 권한은 get_current_user / get_current_vet 의존성으로 분리된다.

주의:
  - GET /requests 와 GET /{diagnosis_id} 는 같은 prefix 를 쓰지만 경로와 메서드가
    달라 FastAPI 가 올바르게 라우팅한다. 신규 GET 엔드포인트를 추가할 때는
    고정 경로(/requests 같은)가 가변 경로(/{...})보다 먼저 선언되도록 주의한다.
  - 소견 요청(POST /request) 시점에 알림을 보내지 않는다. 알림은 수의사가
    소견을 "작성 완료"한 순간(항목 12)에 보호자에게 발송될 예정이며,
    notifications 테이블이 보호자 담당자에 의해 생성된 이후에 연결된다.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import DiagnosisResult, Opinion, Pet, User, Vet
from app.routers.dependencies import get_current_user, get_current_vet
from app.schemas import (
    OpinionDetailResponse,
    OpinionRequestCreate,
    OpinionResponse,
    OpinionWrite,
)

router = APIRouter(prefix="/opinions", tags=["opinions"])


# ==================== 보호자 → 수의사에게 소견 요청 ====================
@router.post("/request", response_model=OpinionResponse, status_code=status.HTTP_201_CREATED)
def create_opinion_request(
    payload: OpinionRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """보호자가 특정 수의사에게 소견 요청 전송

    생성된 Opinion 은 content/answered_at 이 null 인 "미답변" 상태로 시작한다.
    이후 수의사 대시보드의 GET /requests 목록에 "pending" 으로 노출된다.
    """

    # 진단 결과가 존재하고 현재 보호자의 반려동물 것인지 확인 (다른 보호자의
    # 진단에 대해 요청을 생성하는 것을 차단)
    diagnosis = (
        db.query(DiagnosisResult)
        .join(Pet, Pet.id == DiagnosisResult.pet_id)
        .filter(
            DiagnosisResult.id == payload.diagnosis_id,
            Pet.owner_id == current_user.id,
        )
        .first()
    )
    if not diagnosis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="진단 결과를 찾을 수 없습니다.",
        )

    vet = db.query(Vet).filter(Vet.id == payload.vet_id).first()
    if not vet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="수의사를 찾을 수 없습니다.",
        )

    opinion = Opinion(
        diagnosis_id=payload.diagnosis_id,
        vet_id=payload.vet_id,
        symptom_memo=payload.symptom_memo,
    )
    db.add(opinion)
    db.commit()
    db.refresh(opinion)

    return opinion


# ==================== 수의사: 소견 요청 목록 ====================
@router.get("/requests", response_model=List[OpinionDetailResponse])
def list_opinion_requests(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        pattern="^(pending|answered)$",
        description="pending=미답변, answered=완료",
    ),
    db: Session = Depends(get_db),
    current_vet: Vet = Depends(get_current_vet),
):
    """수의사에게 들어온 소견 요청 목록 (미답변/완료 필터)

    미답변/완료의 구분은 Opinion.content 가 null 인지로 판별한다.
    별도 상태 컬럼을 두지 않은 이유: 라이프사이클이 단순해 상태 머신이 불필요.
    """

    # joinedload 로 diagnosis→pet 까지 한 번에 가져와서 N+1 쿼리를 방지
    query = (
        db.query(Opinion)
        .options(joinedload(Opinion.diagnosis).joinedload(DiagnosisResult.pet))
        .filter(Opinion.vet_id == current_vet.id)
    )

    if status_filter == "pending":
        query = query.filter(Opinion.content.is_(None))
    elif status_filter == "answered":
        query = query.filter(Opinion.content.isnot(None))

    opinions = query.order_by(Opinion.created_at.desc()).all()

    return [_to_detail_response(op, current_vet) for op in opinions]


# ==================== 수의사: 소견 작성 ====================
@router.post("/{opinion_id}", response_model=OpinionResponse)
def write_opinion(
    opinion_id: int,
    payload: OpinionWrite,
    db: Session = Depends(get_db),
    current_vet: Vet = Depends(get_current_vet),
):
    """수의사가 요청받은 소견에 대해 작성 (최초 1회)

    - 본인에게 온 요청만 작성 가능 (vet_id 일치 체크)
    - 이미 작성된 소견은 400 을 반환하여 수정 API 로 유도
    - 성공 시 answered_at 을 서버 시각으로 기록
    """

    opinion = (
        db.query(Opinion)
        .filter(Opinion.id == opinion_id, Opinion.vet_id == current_vet.id)
        .first()
    )
    if not opinion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="소견 요청을 찾을 수 없습니다.",
        )

    # 같은 요청을 두 번 작성해서 answered_at 이 밀리는 것을 방지
    if opinion.content is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 작성된 소견입니다. 수정 API를 사용하세요.",
        )

    opinion.content = payload.content
    opinion.recommendation = payload.recommendation
    opinion.visit_required = payload.visit_required
    opinion.answered_at = datetime.utcnow()

    db.commit()
    db.refresh(opinion)

    # TODO(항목 12): 보호자 담당자가 notifications 테이블을 만든 뒤,
    # 이 지점에서 보호자에게 "소견이 도착했습니다" 알림을 생성하도록 연결.
    return opinion


# ==================== 수의사: 소견 수정 ====================
@router.put("/{opinion_id}", response_model=OpinionResponse)
def update_opinion(
    opinion_id: int,
    payload: OpinionWrite,
    db: Session = Depends(get_db),
    current_vet: Vet = Depends(get_current_vet),
):
    """수의사가 이미 작성한 소견 수정

    answered_at 은 "최초 작성 시각"을 의미하므로 수정 시에는 갱신하지 않는다.
    updated_at 은 SQLAlchemy onupdate 로 자동 갱신된다.
    """

    opinion = (
        db.query(Opinion)
        .filter(Opinion.id == opinion_id, Opinion.vet_id == current_vet.id)
        .first()
    )
    if not opinion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="소견을 찾을 수 없습니다.",
        )

    # 아직 작성되지 않은 요청을 PUT 으로 채우려는 경우는 POST 로 유도
    if opinion.content is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="아직 작성되지 않은 소견입니다. 작성 API를 사용하세요.",
        )

    opinion.content = payload.content
    opinion.recommendation = payload.recommendation
    opinion.visit_required = payload.visit_required

    db.commit()
    db.refresh(opinion)

    return opinion


# ==================== 보호자: 수신한 소견 상세 조회 ====================
@router.get("/{diagnosis_id}", response_model=OpinionDetailResponse)
def get_opinion_for_owner(
    diagnosis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """보호자가 특정 진단에 대해 수신한 소견 상세 조회

    - 본인 반려동물의 진단이어야 조회 가능
    - content 가 채워진(= 수의사가 작성 완료한) 소견만 노출
    - 동일 진단에 여러 수의사 소견이 있을 수 있으므로 answered_at 기준으로 최신 1건 반환
    """

    opinion = (
        db.query(Opinion)
        .options(
            joinedload(Opinion.vet),
            joinedload(Opinion.diagnosis).joinedload(DiagnosisResult.pet),
        )
        .join(DiagnosisResult, Opinion.diagnosis_id == DiagnosisResult.id)
        .join(Pet, Pet.id == DiagnosisResult.pet_id)
        .filter(
            Opinion.diagnosis_id == diagnosis_id,
            Pet.owner_id == current_user.id,
            Opinion.content.isnot(None),
        )
        .order_by(Opinion.answered_at.desc())
        .first()
    )

    if not opinion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="수신한 소견이 없습니다.",
        )

    return _to_detail_response(opinion, opinion.vet)


def _to_detail_response(opinion: Opinion, vet: Optional[Vet]) -> OpinionDetailResponse:
    """Opinion ORM → OpinionDetailResponse 변환 헬퍼

    diagnosis/pet/vet 관계를 평탄화해 프론트가 카드 UI를 한 번에 렌더링할 수 있게 한다.
    호출자는 vet 을 명시적으로 넘겨야 한다 (목록 조회는 current_vet, 보호자 조회는 opinion.vet).
    """
    diagnosis = opinion.diagnosis
    pet = diagnosis.pet if diagnosis else None

    return OpinionDetailResponse(
        id=opinion.id,
        diagnosis_id=opinion.diagnosis_id,
        vet_id=opinion.vet_id,
        content=opinion.content,
        recommendation=opinion.recommendation,
        visit_required=opinion.visit_required,
        symptom_memo=opinion.symptom_memo,
        created_at=opinion.created_at,
        answered_at=opinion.answered_at,
        vet_name=vet.name if vet else None,
        hospital_name=vet.hospital_name if vet else None,
        pet_name=pet.name if pet else None,
        diagnosis=diagnosis,
    )
