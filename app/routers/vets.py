"""수의사 병원 프로필 API (팀 분배 문서 항목 13)

보호자 화면(카카오맵 병원 찾기, 수의사 카드, 소견 수신 화면)에서
노출될 프로필 정보를 수의사 본인이 관리한다.

- 조회:  GET /api/vets/profile  (수의사 토큰)
- 수정:  PUT /api/vets/profile  (수의사 토큰, 부분 업데이트)
- 대시보드: GET /api/vets/dashboard-summary (수의사 토큰, 피그마 수의사 포털 통계)
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DiagnosisResult, Opinion, Vet
from app.routers.dependencies import get_current_vet
from app.schemas import VetProfileUpdate, VetResponse

router = APIRouter(prefix="/vets", tags=["vets"])


class MonthlyCount(BaseModel):
    month: str
    count: int


class DiseaseSlice(BaseModel):
    disease: str
    count: int


class VetDashboardSummary(BaseModel):
    pending_count: int
    completed_total: int
    completed_last_7_days: int
    avg_rating: Optional[float] = None
    review_count: int = 0
    revenue_this_month: int = 0
    monthly_requests: List[MonthlyCount] = []
    disease_breakdown: List[DiseaseSlice] = []


def _month_bounds(y: int, m: int):
    start = datetime(y, m, 1)
    end = datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)
    return start, end


@router.get("/dashboard-summary", response_model=VetDashboardSummary)
def vet_dashboard_summary(
    db: Session = Depends(get_db),
    current_vet: Vet = Depends(get_current_vet),
):
    """수의사 대시보드 KPI·월별 요청·질환 분포 (피그마 통계 탭 데이터 소스)"""
    vid = current_vet.id
    pending_count = (
        db.query(func.count(Opinion.id))
        .filter(Opinion.vet_id == vid, Opinion.content.is_(None))
        .scalar()
        or 0
    )
    completed_total = (
        db.query(func.count(Opinion.id))
        .filter(Opinion.vet_id == vid, Opinion.content.isnot(None))
        .scalar()
        or 0
    )
    since = datetime.utcnow() - timedelta(days=7)
    completed_last_7_days = (
        db.query(func.count(Opinion.id))
        .filter(
            Opinion.vet_id == vid,
            Opinion.answered_at.isnot(None),
            Opinion.answered_at >= since,
        )
        .scalar()
        or 0
    )

    avg = (
        db.query(func.avg(Opinion.owner_rating))
        .filter(Opinion.vet_id == vid, Opinion.owner_rating.isnot(None))
        .scalar()
    )
    avg_rating = round(float(avg), 2) if avg is not None else None
    review_count = (
        db.query(func.count(Opinion.id))
        .filter(Opinion.vet_id == vid, Opinion.owner_rating.isnot(None))
        .scalar()
        or 0
    )

    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    rev = (
        db.query(func.coalesce(func.sum(Opinion.service_fee), 0))
        .filter(
            Opinion.vet_id == vid,
            Opinion.answered_at.isnot(None),
            Opinion.answered_at >= month_start,
        )
        .scalar()
    )
    revenue_this_month = int(rev or 0)

    y, m = now.year, now.month
    pairs = []
    for _ in range(6):
        pairs.append((y, m))
        if m == 1:
            y, m = y - 1, 12
        else:
            m -= 1
    pairs = list(reversed(pairs))

    monthly_requests: List[MonthlyCount] = []
    for yy, mm in pairs:
        start, end = _month_bounds(yy, mm)
        c = (
            db.query(func.count(Opinion.id))
            .filter(
                Opinion.vet_id == vid,
                Opinion.created_at >= start,
                Opinion.created_at < end,
            )
            .scalar()
            or 0
        )
        monthly_requests.append(MonthlyCount(month=f"{yy}-{mm:02d}", count=c))

    rows = (
        db.query(DiagnosisResult.main_disease, func.count(DiagnosisResult.id).label("cnt"))
        .join(Opinion, Opinion.diagnosis_id == DiagnosisResult.id)
        .filter(
            Opinion.vet_id == vid,
            Opinion.content.isnot(None),
            DiagnosisResult.main_disease.isnot(None),
        )
        .group_by(DiagnosisResult.main_disease)
        .order_by(func.count(DiagnosisResult.id).desc())
        .limit(8)
        .all()
    )
    disease_breakdown = [DiseaseSlice(disease=r[0], count=r[1]) for r in rows]

    return VetDashboardSummary(
        pending_count=pending_count,
        completed_total=completed_total,
        completed_last_7_days=completed_last_7_days,
        avg_rating=avg_rating,
        review_count=review_count,
        revenue_this_month=revenue_this_month,
        monthly_requests=monthly_requests,
        disease_breakdown=disease_breakdown,
    )


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


# ==================== 카카오맵 ↔ GANADI 매칭 ====================

class HospitalLookup(BaseModel):
    """카카오 로컬 API에서 받은 병원 정보 한 건"""
    place_id: str = Field(..., description="카카오 place id (문자열)")
    place_name: str
    address: Optional[str] = None
    road_address: Optional[str] = None
    phone: Optional[str] = None
    x: float = Field(..., description="경도(longitude)")
    y: float = Field(..., description="위도(latitude)")
    distance_m: Optional[float] = None  # 카카오가 알려준 거리


class HospitalMatchResult(BaseModel):
    """매칭 결과 — 카카오 데이터 + GANADI 정보 합본"""
    place_id: str
    place_name: str
    address: Optional[str] = None
    road_address: Optional[str] = None
    phone: Optional[str] = None
    x: float
    y: float
    distance_m: Optional[float] = None

    is_ganadi: bool = False
    vet_id: Optional[int] = None
    vet_name: Optional[str] = None
    specialty: Optional[str] = None
    business_hours: Optional[str] = None
    rating: Optional[float] = None
    review_count: int = 0


class HospitalMatchRequest(BaseModel):
    hospitals: List[HospitalLookup]


class RegisteredVetCard(BaseModel):
    """공용 수의사 목록/추천 카드 응답.

    소견 요청 흐름의 직접 진입 동선을 위해 보호자/비회원 모두 조회 가능.
    민감 정보(이메일·면허번호 등)는 노출하지 않는다.
    """
    id: int
    name: str
    hospital_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    specialty: Optional[str] = None
    business_hours: Optional[str] = None
    rating: Optional[float] = None
    review_count: int = 0


def _build_rating_map(db: Session) -> dict[int, tuple[Optional[float], int]]:
    rows = (
        db.query(
            Opinion.vet_id,
            func.avg(Opinion.owner_rating).label("avg_rating"),
            func.count(Opinion.id).label("review_count"),
        )
        .filter(Opinion.owner_rating.isnot(None))
        .group_by(Opinion.vet_id)
        .all()
    )
    return {
        row.vet_id: (
            round(float(row.avg_rating), 1) if row.avg_rating is not None else None,
            int(row.review_count or 0),
        )
        for row in rows
    }


def _vet_to_card(vet: Vet, rating_map: dict[int, tuple[Optional[float], int]]) -> RegisteredVetCard:
    rating, count = rating_map.get(vet.id, (None, 0))
    return RegisteredVetCard(
        id=vet.id,
        name=vet.name,
        hospital_name=vet.hospital_name,
        address=vet.address,
        phone=vet.phone,
        specialty=vet.specialty,
        business_hours=vet.business_hours,
        rating=rating,
        review_count=count,
    )


@router.get("/registered", response_model=List[RegisteredVetCard])
def list_registered_vets(
    db: Session = Depends(get_db),
    sort: str = "rating",  # rating | reviews | recent
    limit: int = 50,
    offset: int = 0,
    specialty: Optional[str] = None,
):
    """승인된 GANADI 등록 수의사 공개 목록.

    소견 요청 흐름의 진입 동선(AI 결과 직접 CTA, /vets 페이지의 등록 병원 토글)
    에서 사용된다. 인증 불필요.
    """
    q = db.query(Vet).filter(Vet.approval_status == "approved")
    if specialty:
        q = q.filter(Vet.specialty.ilike(f"%{specialty}%"))

    vets = q.all()
    rating_map = _build_rating_map(db)

    cards = [_vet_to_card(v, rating_map) for v in vets]
    if sort == "rating":
        cards.sort(key=lambda c: ((c.rating or 0), c.review_count), reverse=True)
    elif sort == "reviews":
        cards.sort(key=lambda c: (c.review_count, c.rating or 0), reverse=True)
    else:  # recent — DB 순서 그대로 (created_at desc)
        id_order = {v.id: i for i, v in enumerate(sorted(vets, key=lambda v: v.created_at, reverse=True))}
        cards.sort(key=lambda c: id_order.get(c.id, 0))

    return cards[offset : offset + limit]


@router.get("/recommended", response_model=List[RegisteredVetCard])
def recommended_vets(
    db: Session = Depends(get_db),
    limit: int = 3,
    specialty: Optional[str] = None,
):
    """AI 분석 결과 페이지 등에서 보여줄 "추천 수의사" 짧은 목록.

    실서비스에서는 보호자 위치/반려동물 종/관심 질환을 반영한 매칭으로
    확장 가능. 지금은 평점·리뷰순 상위 N명을 반환한다.
    """
    return list_registered_vets(db=db, sort="rating", limit=limit, offset=0, specialty=specialty)


def _normalize(text: Optional[str]) -> str:
    if not text:
        return ""
    return "".join(ch for ch in text.lower() if not ch.isspace())


@router.post("/match-hospitals", response_model=List[HospitalMatchResult])
def match_hospitals(payload: HospitalMatchRequest, db: Session = Depends(get_db)):
    """카카오 병원 리스트 ↔ GANADI 등록 수의사 매칭.

    - 병원명/주소를 키로 GANADI 에 등록된 승인된(`approved`) 수의사가 있는지 찾는다
    - 매칭되면 평점/리뷰수/진료과목/영업시간을 함께 채워서 반환
    - 매칭 안 되면 `is_ganadi=false` 로 카카오 정보만 그대로 돌려준다
    """
    if not payload.hospitals:
        return []

    # GANADI 의 승인된 수의사 전부 미리 로드 (보통 수십~수백 건)
    approved_vets: List[Vet] = (
        db.query(Vet).filter(Vet.approval_status == "approved").all()
    )

    # 평점/리뷰 카운트 일괄 계산 (가입자 수가 많지 않으므로 한 번에)
    rating_rows = (
        db.query(
            Opinion.vet_id,
            func.avg(Opinion.owner_rating).label("avg_rating"),
            func.count(Opinion.id).label("review_count"),
        )
        .filter(Opinion.owner_rating.isnot(None))
        .group_by(Opinion.vet_id)
        .all()
    )
    rating_map = {
        row.vet_id: (
            round(float(row.avg_rating), 1) if row.avg_rating is not None else None,
            int(row.review_count or 0),
        )
        for row in rating_rows
    }

    # 병원명을 키로 빠르게 매칭하기 위한 인덱스 (간단한 normalize)
    name_index: dict[str, Vet] = {}
    for v in approved_vets:
        if v.hospital_name:
            name_index[_normalize(v.hospital_name)] = v

    results: List[HospitalMatchResult] = []
    for h in payload.hospitals:
        matched: Optional[Vet] = None
        norm = _normalize(h.place_name)
        if norm in name_index:
            matched = name_index[norm]
        else:
            # 부분 일치(양방향 contains) — 카카오 명칭이 길거나 짧아도 잡히도록
            for key, vet in name_index.items():
                if not key or not norm:
                    continue
                if key in norm or norm in key:
                    matched = vet
                    break

        if matched:
            avg, count = rating_map.get(matched.id, (None, 0))
            results.append(
                HospitalMatchResult(
                    place_id=h.place_id,
                    place_name=h.place_name,
                    address=h.address,
                    road_address=h.road_address,
                    phone=h.phone,
                    x=h.x,
                    y=h.y,
                    distance_m=h.distance_m,
                    is_ganadi=True,
                    vet_id=matched.id,
                    vet_name=matched.name,
                    specialty=matched.specialty,
                    business_hours=matched.business_hours,
                    rating=avg,
                    review_count=count,
                )
            )
        else:
            results.append(
                HospitalMatchResult(
                    place_id=h.place_id,
                    place_name=h.place_name,
                    address=h.address,
                    road_address=h.road_address,
                    phone=h.phone,
                    x=h.x,
                    y=h.y,
                    distance_m=h.distance_m,
                    is_ganadi=False,
                )
            )

    return results
