"""POST /diagnosis/analyze 수집 통합 테스트."""

from app.models import CollectedSample, DiagnosisResult
from tests.conftest import MINIMAL_JPEG


def _post_analyze(client, auth_headers, pet_id, **form_fields):
    data = {"training_consent": "false"}
    data.update(form_fields)
    return client.post(
        f"/api/diagnosis/analyze?pet_id={pet_id}",
        headers=auth_headers,
        files={"image": ("test.jpg", MINIMAL_JPEG, "image/jpeg")},
        data=data,
    )


def test_analyze_legacy_no_extra_fields(
    client, auth_headers, test_pet, mock_ai_and_storage, collection_off,
):
    """기존 클라이언트: 추가 Form 없이 200."""
    resp = client.post(
        f"/api/diagnosis/analyze?pet_id={test_pet.id}",
        headers=auth_headers,
        files={"image": ("test.jpg", MINIMAL_JPEG, "image/jpeg")},
    )
    assert resp.status_code == 200
    assert resp.json()["main_disease"] == "결막염"


def test_analyze_no_collection_when_consent_false(
    client, auth_headers, test_pet, mock_ai_and_storage, collection_on, db_session,
):
    resp = _post_analyze(
        client, auth_headers, test_pet.id,
        capture_device="스마트폰",
        training_consent="false",
    )
    assert resp.status_code == 200
    assert db_session.query(CollectedSample).count() == 0


def test_analyze_inserts_when_consent_true(
    client, auth_headers, test_pet, mock_ai_and_storage, collection_on, db_session,
):
    resp = _post_analyze(
        client, auth_headers, test_pet.id,
        capture_device="스마트폰",
        training_consent="true",
        consent_version="v1",
    )
    assert resp.status_code == 200
    samples = db_session.query(CollectedSample).all()
    assert len(samples) == 1
    assert samples[0].diagnosis_id == resp.json()["id"]
    assert samples[0].ai_all_diseases["결막염"] == 0.8


def test_analyze_400_missing_device_with_consent(
    client, auth_headers, test_pet, mock_ai_and_storage, collection_on,
):
    resp = _post_analyze(
        client, auth_headers, test_pet.id,
        training_consent="true",
    )
    assert resp.status_code == 400


def test_analyze_200_when_collection_insert_fails(
    client, auth_headers, test_pet, mock_ai_and_storage, collection_on, db_session, monkeypatch,
):
    def _fail_insert(*args, **kwargs):
        raise RuntimeError("simulated insert failure")

    monkeypatch.setattr(
        "app.routers.diagnosis.try_insert_collected_sample",
        _fail_insert,
    )
    resp = _post_analyze(
        client, auth_headers, test_pet.id,
        capture_device="일반카메라",
        training_consent="true",
    )
    assert resp.status_code == 200
    assert db_session.query(DiagnosisResult).count() == 1


def test_ai_receives_device_when_collection_on(
    client, auth_headers, test_pet, mock_ai_and_storage, collection_on,
):
    _post_analyze(
        client, auth_headers, test_pet.id,
        capture_device="검안경",
        training_consent="false",
    )
    mock_client = mock_ai_and_storage
    call_kwargs = mock_client.post.call_args
    assert call_kwargs.kwargs["data"]["device"] == "검안경"


def test_ai_no_device_when_collection_off(
    client, auth_headers, test_pet, mock_ai_and_storage, collection_off,
):
    _post_analyze(
        client, auth_headers, test_pet.id,
        capture_device="스마트폰",
        training_consent="true",
    )
    mock_client = mock_ai_and_storage
    call_kwargs = mock_client.post.call_args
    assert "device" not in call_kwargs.kwargs["data"]
