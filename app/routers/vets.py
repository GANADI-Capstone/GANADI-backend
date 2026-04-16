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
from pydantic import BaseModel
from sqlalchemy import func
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
