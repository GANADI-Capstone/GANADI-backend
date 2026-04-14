from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Any, Dict
import httpx

from app.database import get_db
from app.models import DiagnosisResult, Pet, User
from app.schemas import DiagnosisResponse
from app.routers.dependencies import get_current_user
from app.core.config import settings
from app.core.storage import save_image

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
        
        # 이미지 파일 읽기
        image_bytes = await image.read()
        
        # 이미지 저장 (S3 또는 로컬)
        image_url = await save_image(image_bytes, image.filename)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
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
    
    # 결과 DB 저장
    db_diagnosis = DiagnosisResult(
        pet_id=pet_id,
        image_url=image_url,  # S3 URL 또는 로컬 경로
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


def _predictions_for_ai_server(raw: Any) -> Dict[str, Dict[str, Any]]:
    """DB JSON → AI 서버 Report/PDF API용 predictions 형식"""
    if not raw or not isinstance(raw, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for disease, pred in raw.items():
        if not isinstance(pred, dict):
            continue
        label = pred.get("label")
        conf = pred.get("confidence")
        if label is None or conf is None:
            continue
        out[str(disease)] = {"label": str(label), "confidence": float(conf)}
    return out


@router.get("/{diagnosis_id}/pdf")
async def download_diagnosis_pdf(
    diagnosis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    진단 결과 기반 PDF 보고서 다운로드.
    1) AI 서버 /api/ai/report 로 Claude 리포트 생성
    2) AI 서버 /api/ai/pdf 로 PDF 생성 후 바이너리 반환
    """
    diagnosis = (
        db.query(DiagnosisResult).filter(DiagnosisResult.id == diagnosis_id).first()
    )
    if not diagnosis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="진단 결과를 찾을 수 없습니다.",
        )

    pet = db.query(Pet).filter(Pet.id == diagnosis.pet_id).first()
    if not pet or pet.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="접근 권한이 없습니다.",
        )

    animal_type = diagnosis.animal_type.value
    predictions_payload = _predictions_for_ai_server(diagnosis.predictions)
    if not predictions_payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="저장된 예측 결과가 없어 PDF를 만들 수 없습니다.",
        )

    report_body = {
        "animal_type": animal_type,
        "pet_name": pet.name,
        "predictions": predictions_payload,
    }

    timeout = httpx.Timeout(120.0, connect=30.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            report_resp = await client.post(
                f"{settings.AI_SERVER_URL}/api/ai/report",
                json=report_body,
            )
            if report_resp.status_code >= 400:
                detail = report_resp.text
                try:
                    detail = report_resp.json().get("detail", detail)
                except Exception:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"AI 리포트 생성 실패: {detail}",
                )

            report = report_resp.json()

            pdf_body = {
                "pet_name": pet.name,
                "animal_type": animal_type,
                "predictions": predictions_payload,
                "report": {
                    "summary": report.get("summary", ""),
                    "disease_analysis": report.get("disease_analysis") or {},
                    "visit_urgency": report.get("visit_urgency", "정기검진"),
                    "vet_required": bool(report.get("vet_required", False)),
                    "precautions": report.get("precautions") or [],
                },
            }

            pdf_resp = await client.post(
                f"{settings.AI_SERVER_URL}/api/ai/pdf",
                json=pdf_body,
            )
            if pdf_resp.status_code >= 400:
                detail = pdf_resp.text
                try:
                    detail = pdf_resp.json().get("detail", detail)
                except Exception:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"AI PDF 생성 실패: {detail}",
                )

            content = pdf_resp.content
            if not content or len(content) < 100:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="PDF 파일이 비어 있거나 올바르지 않습니다.",
                )

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI 서버 연결 오류: {str(e)}",
        )

    filename = f"petcare_diagnosis_{diagnosis_id}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/history", response_model=List[DiagnosisResponse])
def get_all_diagnosis_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """현재 사용자의 전체 진단 이력 조회"""
    
    diagnoses = db.query(DiagnosisResult).join(Pet).filter(
        Pet.owner_id == current_user.id
    ).order_by(DiagnosisResult.created_at.desc()).all()
    
    return diagnoses


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
