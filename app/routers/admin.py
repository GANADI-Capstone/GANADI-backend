from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from typing import Optional, List
from datetime import datetime, timedelta

from app.database import get_db
from app.models import User, Vet, DiagnosisResult
from app.routers.dependencies import get_current_admin
from pydantic import BaseModel


router = APIRouter(prefix="/admin", tags=["admin"])


# ==================== Response Schemas ====================
class UserListResponse(BaseModel):
    id: int
    email: str
    name: str
    phone: Optional[str] = None
    is_suspended: bool = False
    created_at: datetime
    
    class Config:
        from_attributes = True


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


class AdminStatsResponse(BaseModel):
    total_users: int
    total_vets: int
    total_diagnoses: int
    pending_vets: int
    daily_diagnosis_counts: List[DailyStatsItem]
    disease_distribution: List[DiseaseStatsItem]


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
    pending_vets = db.query(func.count(Vet.id)).filter(
        Vet.approval_status == "pending" if hasattr(Vet, 'approval_status') else True
    ).scalar()
    
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
    
    return AdminStatsResponse(
        total_users=total_users,
        total_vets=total_vets,
        total_diagnoses=total_diagnoses,
        pending_vets=pending_vets,
        daily_diagnosis_counts=daily_diagnosis_counts,
        disease_distribution=disease_distribution
    )


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
    return users


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
    
    return user


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
