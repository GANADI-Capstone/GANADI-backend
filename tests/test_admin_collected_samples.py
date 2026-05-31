"""Admin collected_samples API tests."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.models import CollectedSample, DiagnosisResult, SpeciesEnum, User


@pytest.fixture()
def admin_user(db_session) -> User:
    user = User(
        email="admin@test.com",
        password_hash=get_password_hash("adminpass"),
        name="관리자",
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def admin_headers(admin_user) -> dict:
    token = create_access_token({"sub": str(admin_user.id), "type": "user"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def sample_row(db_session, test_pet) -> CollectedSample:
    diag = DiagnosisResult(
        pet_id=test_pet.id,
        image_url="uploads/test.jpg",
        animal_type=SpeciesEnum.DOG,
        predictions={"결막염": {"label": "유", "confidence": 90}},
        main_disease="결막염",
        is_normal=False,
    )
    db_session.add(diag)
    db_session.commit()
    db_session.refresh(diag)

    row = CollectedSample(
        diagnosis_id=diag.id,
        source="user_upload",
        image_url="uploads/test.jpg",
        animal_type=SpeciesEnum.DOG,
        capture_device="스마트폰",
        pet_breed="믹스",
        ai_predictions={"결막염": {"label": "유", "confidence": 90}},
        ai_top3=[{"disease": "결막염", "confidence": 0.9}],
        ai_all_diseases={"결막염": 0.9},
        ai_main_disease="결막염",
        ai_is_normal=False,
        training_consent=True,
        consent_at=datetime.utcnow(),
        consent_version="v1",
        label_status="pending",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_list_collected_samples_requires_admin(client: TestClient, sample_row, auth_headers):
    resp = client.get("/api/admin/collected-samples", headers=auth_headers)
    assert resp.status_code == 403


def test_list_collected_samples(client: TestClient, sample_row, admin_headers):
    resp = client.get("/api/admin/collected-samples", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["capture_device"] == "스마트폰"
    assert data["items"][0]["ai_main_disease"] == "결막염"


def test_list_filter_by_status(client: TestClient, sample_row, admin_headers):
    resp = client.get(
        "/api/admin/collected-samples",
        headers=admin_headers,
        params={"label_status": "pending"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp2 = client.get(
        "/api/admin/collected-samples",
        headers=admin_headers,
        params={"label_status": "confirmed"},
    )
    assert resp2.json()["total"] == 0


def test_get_collected_sample_detail(client: TestClient, sample_row, admin_headers):
    resp = client.get(f"/api/admin/collected-samples/{sample_row.id}", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_all_diseases"]["결막염"] == 0.9
    assert len(body["ai_top3"]) == 1


def test_get_collected_sample_detail_requires_admin(
    client: TestClient, sample_row, auth_headers,
):
    resp = client.get(
        f"/api/admin/collected-samples/{sample_row.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 403


def test_patch_requires_admin(client: TestClient, sample_row, auth_headers):
    resp = client.patch(
        f"/api/admin/collected-samples/{sample_row.id}",
        headers=auth_headers,
        json={"label_status": "confirmed", "confirmed_disease": "결막염"},
    )
    assert resp.status_code == 403


def test_patch_not_found_returns_404(client: TestClient, admin_headers):
    resp = client.patch(
        "/api/admin/collected-samples/99999",
        headers=admin_headers,
        json={"label_status": "rejected", "reject_reason": "테스트"},
    )
    assert resp.status_code == 404


def test_patch_invalid_label_status_returns_422(client: TestClient, sample_row, admin_headers):
    resp = client.patch(
        f"/api/admin/collected-samples/{sample_row.id}",
        headers=admin_headers,
        json={"label_status": "invalid_status"},
    )
    assert resp.status_code == 422


def test_patch_does_not_modify_diagnosis_results(
    client: TestClient, db_session, sample_row, admin_headers,
):
    """PATCH는 collected_samples만 변경하고 diagnosis_results는 건드리지 않는다."""
    diag = db_session.query(DiagnosisResult).filter(
        DiagnosisResult.id == sample_row.diagnosis_id,
    ).one()
    before = {
        "main_disease": diag.main_disease,
        "predictions": dict(diag.predictions or {}),
        "image_url": diag.image_url,
        "is_normal": diag.is_normal,
    }

    resp = client.patch(
        f"/api/admin/collected-samples/{sample_row.id}",
        headers=admin_headers,
        json={
            "label_status": "confirmed",
            "confirmed_disease": "백내장",
            "confirmed_severity": "성숙",
        },
    )
    assert resp.status_code == 200

    db_session.expire_all()
    diag_after = db_session.query(DiagnosisResult).filter(
        DiagnosisResult.id == sample_row.diagnosis_id,
    ).one()
    assert diag_after.main_disease == before["main_disease"]
    assert diag_after.predictions == before["predictions"]
    assert diag_after.image_url == before["image_url"]
    assert diag_after.is_normal == before["is_normal"]

    sample = db_session.query(CollectedSample).filter(CollectedSample.id == sample_row.id).one()
    assert sample.label_status == "confirmed"
    assert sample.confirmed_disease == "백내장"


def test_patch_confirm_sample(client: TestClient, db_session, sample_row, admin_headers, admin_user):
    resp = client.patch(
        f"/api/admin/collected-samples/{sample_row.id}",
        headers=admin_headers,
        json={
            "label_status": "confirmed",
            "confirmed_disease": "결막염",
            "confirmed_severity": "유",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["label_status"] == "confirmed"
    assert body["confirmed_disease"] == "결막염"
    assert body["reviewer_id"] == admin_user.id

    row = db_session.query(CollectedSample).filter(CollectedSample.id == sample_row.id).one()
    assert row.label_status == "confirmed"


def test_patch_confirm_requires_disease(client: TestClient, sample_row, admin_headers):
    resp = client.patch(
        f"/api/admin/collected-samples/{sample_row.id}",
        headers=admin_headers,
        json={"label_status": "confirmed"},
    )
    assert resp.status_code == 400


def test_gap_stats(client: TestClient, sample_row, admin_headers):
    resp = client.get("/api/admin/collected-samples/stats/gap", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status_counts"].get("pending") == 1
    assert len(data["pending_ai"]) >= 1
