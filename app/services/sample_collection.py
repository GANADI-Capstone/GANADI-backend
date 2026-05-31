"""학습 데이터 수집 (collected_samples) — 진단 파이프라인과 격리."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import CollectedSample, Pet, DiagnosisResult

logger = logging.getLogger(__name__)

ALLOWED_CAPTURE_DEVICES = frozenset({"스마트폰", "검안경", "일반카메라"})


def collection_enabled() -> bool:
    return bool(settings.COLLECTION_ENABLED)


def validate_collection_request(
    training_consent: bool,
    capture_device: Optional[str],
) -> None:
    """COLLECTION_ENABLED=true 일 때만 검증."""
    if not collection_enabled():
        return
    if capture_device and capture_device not in ALLOWED_CAPTURE_DEVICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="capture_device는 스마트폰, 검안경, 일반카메라 중 하나여야 합니다.",
        )
    if training_consent and not capture_device:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="학습 활용 동의 시 촬영 장비 선택이 필요합니다.",
        )


def ai_request_data(animal_type: str, capture_device: Optional[str]) -> Dict[str, str]:
    """AI 서버 multipart data — flag off면 device 미전달(기존 동작 유지)."""
    data: Dict[str, str] = {"animal_type": animal_type}
    if collection_enabled() and capture_device:
        data["device"] = capture_device
    return data


def _snapshot_from_ai(ai_result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ai_predictions": ai_result.get("predictions") or {},
        "ai_top3": ai_result.get("top_3_diseases") or [],
        "ai_all_diseases": ai_result.get("all_diseases") or {},
        "ai_main_disease": ai_result.get("main_disease") or None,
        "ai_is_normal": bool(ai_result.get("is_normal", False)),
        "ai_model_version": ai_result.get("model_version"),
        "ai_checkpoint": ai_result.get("checkpoint"),
    }


def try_insert_collected_sample(
    db: Session,
    *,
    diagnosis: DiagnosisResult,
    pet: Pet,
    image_url: str,
    ai_result: Dict[str, Any],
    training_consent: bool,
    capture_device: str,
    consent_version: str,
) -> None:
    """진단 commit 이후 호출. 실패해도 진단 응답에 영향 없음."""
    if not collection_enabled() or not training_consent or not capture_device:
        return

    snap = _snapshot_from_ai(ai_result)
    gender_val = pet.gender.value if pet.gender is not None else None

    sample = CollectedSample(
        diagnosis_id=diagnosis.id,
        source="user_upload",
        image_url=image_url,
        animal_type=pet.species,
        capture_device=capture_device,
        pet_breed=pet.breed,
        pet_age=pet.age,
        pet_gender=gender_val,
        training_consent=True,
        consent_at=datetime.utcnow(),
        consent_version=consent_version or "v1",
        label_status="pending",
        **snap,
    )
    try:
        db.add(sample)
        db.commit()
        logger.info(
            "collected_samples inserted id pending diagnosis_id=%s device=%s",
            diagnosis.id,
            capture_device,
        )
    except Exception:
        db.rollback()
        logger.exception(
            "collected_samples insert failed (diagnosis_id=%s) — diagnosis unaffected",
            diagnosis.id,
        )
