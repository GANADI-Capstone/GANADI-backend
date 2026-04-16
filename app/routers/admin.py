from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, cast, Date
from typing import Optional, List
from datetime import datetime, timedelta

from app.database import get_db
from app.models import AdminReport, DiagnosisResult, Opinion, Pet, User, Vet, SpeciesEnum
from app.routers.dependencies import get_current_admin
from pydantic import BaseModel, Field


router = APIRouter(prefix="/admin", tags=["admin"])


# ==================== Response Schemas ====================
class UserListResponse(BaseModel):
    id: int
    email: str
    name: str
    phone: Optional[str] = None
    is_suspended: bool = False
    created_at: datetime
    diagnosis_count: int = 0


class VetListResponse(BaseModel):
    id: int
    email: str
    name: str
    hospital_name: Optional[str] = None
    approval_status: str = "pending"
    created_at: datetime
    
    class Config:
        from_attributes = True


class DailyStatsItem(BaseModel):
    date: str
    count: int


class DiseaseStatsItem(BaseModel):
    disease: str
    count: int
    percentage: float


class MonthlyBucket(BaseModel):
    """피그마 월별 차트용 (YYYY-MM)"""
    month: str
    count: int


class ActivityItem(BaseModel):
    at: datetime
    type: str
    label: str
    ref: str


class AdminStatsResponse(BaseModel):
    total_users: int
    total_vets: int
    total_diagnoses: int
    pending_vets: int
    daily_diagnosis_counts: List[DailyStatsItem]
    disease_distribution: List[DiseaseStatsItem]
    monthly_new_users: List[MonthlyBucket] = []
    monthly_diagnoses: List[MonthlyBucket] = []
    recent_activities: List[ActivityItem] = []
    open_reports_count: int = 0
    disease_distribution_dog: List[DiseaseStatsItem] = []
    disease_distribution_cat: List[DiseaseStatsItem] = []


class AdminReportResponse(BaseModel):
    id: int
    reporter_user_id: Optional[int] = None
    reporter_email: Optional[str] = None
    target_type: str
    target_label: str
    reason: str
    status: str
    admin_note: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AdminReportPatch(BaseModel):
    status: str = Field(..., pattern="^(pending|processing|resolved|dismissed)$")
    admin_note: Optional[str] = Field(None, max_length=5000)


# ==================== 통계 API (고정 경로 - 먼저 선언) ====================
@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(
    days: int = Query(default=7, ge=1, le=90, description="조회할 일수 (최근 N일)"),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    관리자 대시보드 통계
    - 일별 스크리닝 건수 (최근 N일)
    - 질환별 분포
    - 전체 사용자/수의사/진단 수
    """
    
    # 전체 통계
    total_users = db.query(func.count(User.id)).scalar()
    total_vets = db.query(func.count(Vet.id)).scalar()
    total_diagnoses = db.query(func.count(DiagnosisResult.id)).scalar()
    
    # 승인 대기 중인 수의사 수
    pending_q = db.query(func.count(Vet.id))
    if hasattr(Vet, "approval_status"):
        pending_q = pending_q.filter(Vet.approval_status == "pending")
    pending_vets = pending_q.scalar()
    
    # 일별 스크리닝 건수 (최근 N일)
    start_date = datetime.utcnow() - timedelta(days=days)
    daily_results = db.query(
        cast(DiagnosisResult.created_at, Date).label('date'),
        func.count(DiagnosisResult.id).label('count')
    ).filter(
        DiagnosisResult.created_at >= start_date
    ).group_by(
        cast(DiagnosisResult.created_at, Date)
    ).order_by('date').all()
    
    daily_diagnosis_counts = [
        DailyStatsItem(date=str(row.date), count=row.count)
        for row in daily_results
    ]
    
    # 질환별 분포 (main_disease 기준, 정상 제외)
    disease_results = db.query(
        DiagnosisResult.main_disease,
        func.count(DiagnosisResult.id).label('count')
    ).filter(
        DiagnosisResult.is_normal == False,
        DiagnosisResult.main_disease.isnot(None)
    ).group_by(
        DiagnosisResult.main_disease
    ).order_by(
        func.count(DiagnosisResult.id).desc()
    ).all()
    
    total_diseases = sum(row.count for row in disease_results)
    disease_distribution = [
        DiseaseStatsItem(
            disease=row.main_disease,
            count=row.count,
            percentage=round((row.count / total_diseases * 100), 2) if total_diseases > 0 else 0
        )
        for row in disease_results
    ]

    def _species_diseases(species: SpeciesEnum) -> List[DiseaseStatsItem]:
        rows = (
            db.query(DiagnosisResult.main_disease, func.count(DiagnosisResult.id).label("cnt"))
            .filter(
                DiagnosisResult.is_normal == False,
                DiagnosisResult.main_disease.isnot(None),
                DiagnosisResult.animal_type == species,
            )
            .group_by(DiagnosisResult.main_disease)
            .order_by(func.count(DiagnosisResult.id).desc())
            .all()
        )
        tot = sum(r.cnt for r in rows) or 0
        return [
            DiseaseStatsItem(
                disease=r.main_disease,
                count=r.cnt,
                percentage=round((r.cnt / tot * 100), 2) if tot > 0 else 0,
            )
            for r in rows
        ]

    disease_distribution_dog = _species_diseases(SpeciesEnum.DOG)
    disease_distribution_cat = _species_diseases(SpeciesEnum.CAT)

    def _month_bounds(y: int, m: int):
        start = datetime(y, m, 1)
        end = datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)
        return start, end

    now = datetime.utcnow()
    y, m = now.year, now.month
    month_pairs: List[tuple] = []
    for _ in range(6):
        month_pairs.append((y, m))
        if m == 1:
            y, m = y - 1, 12
        else:
            m -= 1
    month_pairs = list(reversed(month_pairs))

    monthly_new_users: List[MonthlyBucket] = []
    monthly_diagnoses: List[MonthlyBucket] = []
    for yy, mm in month_pairs:
        start, end = _month_bounds(yy, mm)
        uq = db.query(func.count(User.id)).filter(User.created_at >= start, User.created_at < end)
        if hasattr(User, "role"):
            uq = uq.filter(User.role != "admin")
        nu = uq.scalar() or 0
        nd = (
            db.query(func.count(DiagnosisResult.id))
            .filter(DiagnosisResult.created_at >= start, DiagnosisResult.created_at < end)
            .scalar()
            or 0
        )
        monthly_new_users.append(MonthlyBucket(month=f"{yy}-{mm:02d}", count=nu))
        monthly_diagnoses.append(MonthlyBucket(month=f"{yy}-{mm:02d}", count=nd))

    open_reports_count = (
        db.query(func.count(AdminReport.id)).filter(AdminReport.status == "pending").scalar() or 0
    )

    activities_raw: List[dict] = []
    uq2 = db.query(User).order_by(User.created_at.desc())
    if hasattr(User, "role"):
        uq2 = uq2.filter(User.role != "admin")
    for u in uq2.limit(5).all():
        activities_raw.append(
            {
                "at": u.created_at,
                "type": "signup",
                "label": "신규 사용자 가입",
                "ref": u.email or "",
            }
        )
    for d in (
        db.query(DiagnosisResult)
        .options(joinedload(DiagnosisResult.pet).joinedload(Pet.owner))
        .order_by(DiagnosisResult.created_at.desc())
        .limit(5)
        .all()
    ):
        ref = ""
        if d.pet and d.pet.owner:
            ref = d.pet.owner.email or ""
        activities_raw.append(
            {
                "at": d.created_at,
                "type": "diagnosis",
                "label": "AI 분석 완료",
                "ref": ref,
            }
        )
    for o in (
        db.query(Opinion)
        .options(joinedload(Opinion.vet))
        .filter(Opinion.answered_at.isnot(None))
        .order_by(Opinion.answered_at.desc())
        .limit(5)
        .all()
    ):
        activities_raw.append(
            {
                "at": o.answered_at,
                "type": "opinion",
                "label": "수의사 소견 제공",
                "ref": (o.vet.name + " 수의사") if o.vet else "",
            }
        )
    for r in (
        db.query(AdminReport).order_by(AdminReport.created_at.desc()).limit(5).all()
    ):
        activities_raw.append(
            {
                "at": r.created_at,
                "type": "report",
                "label": "신고 접수",
                "ref": r.target_label[:80],
            }
        )

    activities_raw.sort(key=lambda x: x["at"], reverse=True)
    recent_activities = [
        ActivityItem(at=a["at"], type=a["type"], label=a["label"], ref=a["ref"])
        for a in activities_raw[:12]
    ]

    return AdminStatsResponse(
        total_users=total_users,
        total_vets=total_vets,
        total_diagnoses=total_diagnoses,
        pending_vets=pending_vets,
        daily_diagnosis_counts=daily_diagnosis_counts,
        disease_distribution=disease_distribution,
        monthly_new_users=monthly_new_users,
        monthly_diagnoses=monthly_diagnoses,
        recent_activities=recent_activities,
        open_reports_count=open_reports_count,
        disease_distribution_dog=disease_distribution_dog,
        disease_distribution_cat=disease_distribution_cat,
    )


# ==================== 신고 관리 API ====================
@router.get("/reports", response_model=List[AdminReportResponse])
def list_admin_reports(
    status_filter: Optional[str] = Query(None, alias="status"),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    q = db.query(AdminReport).order_by(AdminReport.created_at.desc())
    if status_filter:
        allowed = {"pending", "processing", "resolved", "dismissed"}
        if status_filter not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="status는 pending, processing, resolved, dismissed 중 하나여야 합니다.",
            )
        q = q.filter(AdminReport.status == status_filter)
    return q.limit(200).all()


@router.patch("/reports/{report_id}", response_model=AdminReportResponse)
def patch_admin_report(
    report_id: int,
    payload: AdminReportPatch,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    r = db.query(AdminReport).filter(AdminReport.id == report_id).first()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="신고를 찾을 수 없습니다.")
    r.status = payload.status
    if payload.admin_note is not None:
        r.admin_note = payload.admin_note
    db.commit()
    db.refresh(r)
    return r


# ==================== 보호자 관리 API ====================
@router.get("/users", response_model=List[UserListResponse])
def get_all_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    suspended_only: bool = Query(default=False, description="정지된 계정만 조회"),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    보호자 전체 목록 조회
    """
    query = db.query(User).filter(User.role != "admin") if hasattr(User, 'role') else db.query(User)
    
    if suspended_only and hasattr(User, 'is_suspended'):
        query = query.filter(User.is_suspended == True)
    
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    if not users:
        return []
    uids = [u.id for u in users]
    counts_rows = (
        db.query(Pet.owner_id, func.count(DiagnosisResult.id))
        .join(DiagnosisResult, DiagnosisResult.pet_id == Pet.id)
        .filter(Pet.owner_id.in_(uids))
        .group_by(Pet.owner_id)
        .all()
    )
    counts = {row[0]: row[1] for row in counts_rows}
    return [
        UserListResponse(
            id=u.id,
            email=u.email,
            name=u.name,
            phone=u.phone,
            is_suspended=getattr(u, "is_suspended", False),
            created_at=u.created_at,
            diagnosis_count=counts.get(u.id, 0),
        )
        for u in users
    ]


@router.patch("/users/{user_id}/suspend", response_model=UserListResponse)
def suspend_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    보호자 계정 정지
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    
    if hasattr(user, 'role') and user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="관리자 계정은 정지할 수 없습니다."
        )
    
    if not hasattr(user, 'is_suspended'):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User 모델에 is_suspended 필드가 없습니다. 마이그레이션을 실행해주세요."
        )
    
    user.is_suspended = True
    db.commit()
    db.refresh(user)

    diag_n = (
        db.query(func.count(DiagnosisResult.id))
        .join(Pet, Pet.id == DiagnosisResult.pet_id)
        .filter(Pet.owner_id == user.id)
        .scalar()
        or 0
    )
    return UserListResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        phone=user.phone,
        is_suspended=user.is_suspended,
        created_at=user.created_at,
        diagnosis_count=diag_n,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    보호자 계정 삭제 (cascade로 펫, 진단 기록 등도 함께 삭제됨)
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    
    if hasattr(user, 'role') and user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="관리자 계정은 삭제할 수 없습니다."
        )
    
    db.delete(user)
    db.commit()
    
    return None


# ==================== 수의사 관리 API ====================
@router.get("/vets", response_model=List[VetListResponse])
def get_all_vets(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    approval_status: Optional[str] = Query(
        default=None,
        description="승인 상태 필터 (pending/approved/rejected)"
    ),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    수의사 전체 목록 조회 (승인 상태 필터링 가능)
    """
    query = db.query(Vet)
    
    if approval_status and hasattr(Vet, 'approval_status'):
        if approval_status not in ["pending", "approved", "rejected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="approval_status는 pending, approved, rejected 중 하나여야 합니다."
            )
        query = query.filter(Vet.approval_status == approval_status)
    
    vets = query.order_by(Vet.created_at.desc()).offset(skip).limit(limit).all()
    return vets


@router.patch("/vets/{vet_id}/approve", response_model=VetListResponse)
def approve_vet(
    vet_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    수의사 승인
    """
    vet = db.query(Vet).filter(Vet.id == vet_id).first()
    
    if not vet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="수의사를 찾을 수 없습니다."
        )
    
    if not hasattr(vet, 'approval_status'):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vet 모델에 approval_status 필드가 없습니다. 마이그레이션을 실행해주세요."
        )
    
    vet.approval_status = "approved"
    db.commit()
    db.refresh(vet)
    
    return vet


@router.patch("/vets/{vet_id}/reject", response_model=VetListResponse)
def reject_vet(
    vet_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    수의사 거절
    """
    vet = db.query(Vet).filter(Vet.id == vet_id).first()
    
    if not vet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="수의사를 찾을 수 없습니다."
        )
    
    if not hasattr(vet, 'approval_status'):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vet 모델에 approval_status 필드가 없습니다. 마이그레이션을 실행해주세요."
        )
    
    vet.approval_status = "rejected"
    db.commit()
    db.refresh(vet)
    
    return vet
