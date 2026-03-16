from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import httpx
import json

from app.database import get_db
from app.models import DiagnosisResult, Pet, User
from app.schemas import DiagnosisResponse
from app.routers.dependencies import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


@router.post("/analyze", response_model=DiagnosisResponse)
async def analyze_pet_eye(
    pet_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    반려동물 안구 질환 AI 분석
    
    1. 반려동물 소유자 확인
    2. AI 서버로 이미지 전송
    3. 결과 DB 저장
    """
    
    # 반려동물 소유자 확인
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id
    ).first()
    
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="반려동물을 찾을 수 없습니다."
        )
    
    # AI 서버 호출
    try:
        # pet의 species를 animal_type으로 변환 (SpeciesEnum -> str)
        animal_type = pet.species.value  # "dog" 또는 "cat"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 이미지 파일 읽기
            image_bytes = await image.read()
            
            # multipart/form-data로 file과 animal_type 전송
            files = {"file": (image.filename, image_bytes, image.content_type)}
            data = {"animal_type": animal_type}
            
            response = await client.post(
                f"{settings.AI_SERVER_URL}/api/ai/analyze",
                files=files,
                data=data
            )
            response.raise_for_status()
            ai_result = response.json()
    
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI 서버 오류: {str(e)}"
        )
    
    # TODO: 이미지를 S3에 업로드하고 URL 받기 (현재는 임시)
    image_url = f"temp/{image.filename}"
    
    # 결과 DB 저장
    db_diagnosis = DiagnosisResult(
        pet_id=pet_id,
        image_url=image_url,
        animal_type=pet.species,
        predictions=ai_result.get("predictions", {}),
        main_disease=ai_result.get("main_disease"),
        main_confidence=ai_result.get("main_confidence"),
        is_normal=ai_result.get("is_normal", False)
    )
    db.add(db_diagnosis)
    db.commit()
    db.refresh(db_diagnosis)
    
    return db_diagnosis


@router.get("/history/{pet_id}", response_model=List[DiagnosisResponse])
def get_diagnosis_history(
    pet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """반려동물 진단 이력 조회"""
    
    # 반려동물 소유자 확인
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id
    ).first()
    
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="반려동물을 찾을 수 없습니다."
        )
    
    diagnoses = db.query(DiagnosisResult).filter(
        DiagnosisResult.pet_id == pet_id
    ).order_by(DiagnosisResult.created_at.desc()).all()
    
    return diagnoses


@router.get("/{diagnosis_id}", response_model=DiagnosisResponse)
def get_diagnosis_detail(
    diagnosis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """진단 결과 상세 조회"""
    
    diagnosis = db.query(DiagnosisResult).filter(
        DiagnosisResult.id == diagnosis_id
    ).first()
    
    if not diagnosis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="진단 결과를 찾을 수 없습니다."
        )
    
    # 소유자 확인
    pet = db.query(Pet).filter(Pet.id == diagnosis.pet_id).first()
    if not pet or pet.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="접근 권한이 없습니다."
        )
    
    return diagnosis
