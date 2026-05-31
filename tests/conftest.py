"""Pytest fixtures — SQLite in-memory, auth, mocks."""

from __future__ import annotations

import os
from typing import Generator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 테스트 DB·시크릿 (app import 전)
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("COLLECTION_ENABLED", "false")
os.environ.setdefault("ENVIRONMENT", "development")

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, Pet, SpeciesEnum, GenderEnum  # noqa: E402
from app.core.security import get_password_hash, create_access_token  # noqa: E402
from app.core.config import settings  # noqa: E402

FAKE_AI_RESULT = {
    "predictions": {"결막염": {"label": "유", "confidence": 80.0}},
    "main_disease": "결막염",
    "main_confidence": 80,
    "is_normal": False,
    "top_3_diseases": [{"disease": "결막염", "confidence": 0.8}],
    "all_diseases": {"결막염": 0.8, "백내장": 0.3},
    "model_version": "random_split",
    "checkpoint": "models/classifier/checkpoints/dog_best_random_split.pth",
}

MINIMAL_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xd9"
)


@pytest.fixture()
def db_session() -> Generator:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session) -> Generator[TestClient, None, None]:
    def _override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(db_session) -> User:
    user = User(
        email="test@example.com",
        password_hash=get_password_hash("password123"),
        name="테스트",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def test_pet(db_session, test_user) -> Pet:
    pet = Pet(
        owner_id=test_user.id,
        name="뽀삐",
        species=SpeciesEnum.DOG,
        breed="말티즈",
        age=3,
        gender=GenderEnum.MALE,
    )
    db_session.add(pet)
    db_session.commit()
    db_session.refresh(pet)
    return pet


@pytest.fixture()
def auth_headers(test_user) -> dict:
    token = create_access_token({"sub": str(test_user.id), "type": "user"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def mock_ai_and_storage():
    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json = lambda: FAKE_AI_RESULT.copy()

    with patch(
        "app.routers.diagnosis.save_image",
        new_callable=AsyncMock,
        return_value="uploads/pet_images/test.jpg",
    ), patch(
        "app.routers.diagnosis.httpx.AsyncClient",
    ) as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client
        yield mock_client


@pytest.fixture()
def collection_on(monkeypatch):
    monkeypatch.setattr(settings, "COLLECTION_ENABLED", True)
    yield
    monkeypatch.setattr(settings, "COLLECTION_ENABLED", False)


@pytest.fixture()
def collection_off(monkeypatch):
    monkeypatch.setattr(settings, "COLLECTION_ENABLED", False)
    yield
