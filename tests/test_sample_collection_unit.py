"""sample_collection 서비스 단위 테스트."""

import pytest
from fastapi import HTTPException

from app.models import CollectedSample, DiagnosisResult, SpeciesEnum
from app.services.sample_collection import (
    ai_request_data,
    collection_enabled,
    try_insert_collected_sample,
    validate_collection_request,
)
from tests.conftest import FAKE_AI_RESULT


def test_collection_disabled_by_default(collection_off):
    assert collection_enabled() is False


def test_validate_skipped_when_disabled(collection_off):
    validate_collection_request(training_consent=True, capture_device=None)


def test_validate_device_required_when_consent(collection_on):
    with pytest.raises(HTTPException) as exc:
        validate_collection_request(training_consent=True, capture_device=None)
    assert exc.value.status_code == 400


def test_validate_invalid_device(collection_on):
    with pytest.raises(HTTPException) as exc:
        validate_collection_request(training_consent=False, capture_device="드론")
    assert exc.value.status_code == 400


def test_ai_request_data_no_device_when_flag_off(collection_off):
    data = ai_request_data("dog", "스마트폰")
    assert data == {"animal_type": "dog"}
    assert "device" not in data


def test_ai_request_data_includes_device_when_flag_on(collection_on):
    data = ai_request_data("dog", "스마트폰")
    assert data["device"] == "스마트폰"


def test_insert_when_consent_true(collection_on, db_session, test_pet):
    diagnosis = DiagnosisResult(
        pet_id=test_pet.id,
        image_url="uploads/test.jpg",
        animal_type=SpeciesEnum.DOG,
        predictions={"결막염": {"label": "유", "confidence": 80}},
        main_disease="결막염",
        main_confidence=80,
        is_normal=False,
    )
    db_session.add(diagnosis)
    db_session.commit()
    db_session.refresh(diagnosis)

    try_insert_collected_sample(
        db_session,
        diagnosis=diagnosis,
        pet=test_pet,
        image_url="uploads/test.jpg",
        ai_result=FAKE_AI_RESULT,
        training_consent=True,
        capture_device="스마트폰",
        consent_version="v1",
    )
    rows = db_session.query(CollectedSample).all()
    assert len(rows) == 1
    assert rows[0].capture_device == "스마트폰"
    assert rows[0].ai_top3[0]["disease"] == "결막염"
    assert rows[0].ai_all_diseases["백내장"] == 0.3


def test_no_insert_when_consent_false(collection_on, db_session, test_pet):
    diagnosis = DiagnosisResult(
        pet_id=test_pet.id,
        image_url="uploads/test.jpg",
        animal_type=SpeciesEnum.DOG,
        predictions={},
        is_normal=True,
    )
    db_session.add(diagnosis)
    db_session.commit()
    db_session.refresh(diagnosis)

    try_insert_collected_sample(
        db_session,
        diagnosis=diagnosis,
        pet=test_pet,
        image_url="uploads/test.jpg",
        ai_result=FAKE_AI_RESULT,
        training_consent=False,
        capture_device="스마트폰",
        consent_version="v1",
    )
    assert db_session.query(CollectedSample).count() == 0


def test_insert_failure_does_not_raise(collection_on, db_session, test_pet, monkeypatch):
    diagnosis = DiagnosisResult(
        pet_id=test_pet.id,
        image_url="uploads/test.jpg",
        animal_type=SpeciesEnum.DOG,
        predictions={},
        is_normal=True,
    )
    db_session.add(diagnosis)
    db_session.commit()
    db_session.refresh(diagnosis)

    def _boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(db_session, "commit", _boom)

    try_insert_collected_sample(
        db_session,
        diagnosis=diagnosis,
        pet=test_pet,
        image_url="uploads/test.jpg",
        ai_result=FAKE_AI_RESULT,
        training_consent=True,
        capture_device="검안경",
        consent_version="v1",
    )
