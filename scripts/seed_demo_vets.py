"""시연용 GANADI 등록 수의사 시드 스크립트.

실 카카오맵 키워드 검색에 잡히는 서울 주요 동물병원 이름을 사용해서
`approved` 상태의 수의사 5명을 한 번에 만든다. 이미 같은 이메일이 있으면
건너뛰고, 약간의 더미 평점·리뷰도 함께 박는다.

사용:
    cd backend && source venv/bin/activate
    python -m scripts.seed_demo_vets

비밀번호는 모두 `demo1234!` 로 통일 (필요 시 수정).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

# 스크립트를 단독 실행해도 `app.*` 임포트가 되도록 backend 루트를 sys.path 에 추가
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import DiagnosisResult, Opinion, Pet, User, Vet  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402


DEMO_PASSWORD = "demo1234!"

DEMO_VETS: list[dict] = [
    {
        "email": "demo.gangnam@ganadi.dev",
        "name": "김지훈",
        "hospital_name": "이리온 동물병원",
        "address": "서울특별시 강남구 봉은사로 612",
        "phone": "02-1234-1111",
        "specialty": "안과, 내과",
        "business_hours": "평일 10:00-20:00 · 토 10:00-17:00",
        "license_number": "GD-2018-0001",
    },
    {
        "email": "demo.hongdae@ganadi.dev",
        "name": "박서연",
        "hospital_name": "홍대 24시 동물병원",
        "address": "서울특별시 마포구 양화로 188",
        "phone": "02-1234-2222",
        "specialty": "안과, 응급의학",
        "business_hours": "24시간 운영",
        "license_number": "GD-2019-0002",
    },
    {
        "email": "demo.myeongdong@ganadi.dev",
        "name": "이도윤",
        "hospital_name": "명동 펫메디칼센터",
        "address": "서울특별시 중구 명동길 26",
        "phone": "02-1234-3333",
        "specialty": "안과, 외과",
        "business_hours": "평일 09:30-19:00",
        "license_number": "GD-2017-0003",
    },
    {
        "email": "demo.seongsu@ganadi.dev",
        "name": "최가은",
        "hospital_name": "성수 펫아이센터",
        "address": "서울특별시 성동구 성수일로 56",
        "phone": "02-1234-4444",
        "specialty": "안과 전문",
        "business_hours": "평일 11:00-21:00 · 일 12:00-18:00",
        "license_number": "GD-2020-0004",
    },
    {
        "email": "demo.jamsil@ganadi.dev",
        "name": "정시우",
        "hospital_name": "잠실 동물의료센터",
        "address": "서울특별시 송파구 올림픽로 240",
        "phone": "02-1234-5555",
        "specialty": "안과, 피부과",
        "business_hours": "평일 09:00-22:00",
        "license_number": "GD-2016-0005",
    },
]


def _attach_demo_rating(db, vet_id: int, rating: int, samples: int = 4) -> None:
    """별점/리뷰 카운트를 만들기 위해 더미 사용자·반려동물·진단·소견을 만든다.

    이미 같은 vet 에 demo rating 이 있으면 중복 생성을 피한다.
    """

    existing = (
        db.query(Opinion)
        .filter(Opinion.vet_id == vet_id, Opinion.owner_review.like("[demo seed]%"))
        .count()
    )
    if existing >= samples:
        return

    owner = db.query(User).filter(User.email == "demo.owner@ganadi.dev").first()
    if owner is None:
        owner = User(
            email="demo.owner@ganadi.dev",
            password_hash=get_password_hash(DEMO_PASSWORD),
            name="데모 보호자",
            phone="010-0000-0000",
        )
        db.add(owner)
        db.flush()

    pet = (
        db.query(Pet)
        .filter(Pet.owner_id == owner.id, Pet.name == "데모 반려동물")
        .first()
    )
    if pet is None:
        pet = Pet(
            owner_id=owner.id,
            name="데모 반려동물",
            species="dog",
            breed="시츄",
            age=5,
        )
        db.add(pet)
        db.flush()

    for i in range(samples - existing):
        diagnosis = DiagnosisResult(
            pet_id=pet.id,
            image_url="https://placehold.co/200x200?text=demo",
            animal_type="dog",
            predictions={"결막염": {"label": "유", "confidence": 80}},
            main_disease="결막염",
            main_confidence=80,
            is_normal=False,
        )
        db.add(diagnosis)
        db.flush()

        opinion = Opinion(
            diagnosis_id=diagnosis.id,
            vet_id=vet_id,
            content="데모 시드: 결막염 의심으로 24시간 내 내원을 권장드립니다.",
            recommendation="내원 권장",
            visit_required=True,
            symptom_memo="데모용 증상 메모",
            answered_at=datetime.utcnow() - timedelta(days=2),
            service_fee=30000,
            owner_rating=rating,
            owner_review=f"[demo seed] 친절하고 빠른 답변 감사합니다 #{i+1}",
        )
        db.add(opinion)


def _upsert_vet(db, payload: dict, rating: int) -> Vet:
    existing = db.query(Vet).filter(Vet.email == payload["email"]).first()
    if existing:
        # 정보 갱신 (시드 재실행 시 최신 값 반영)
        for key, value in payload.items():
            setattr(existing, key, value)
        existing.approval_status = "approved"
        if existing.reviewed_at is None:
            existing.reviewed_at = datetime.utcnow()
        return existing

    vet = Vet(
        **payload,
        password_hash=get_password_hash(DEMO_PASSWORD),
        approval_status="approved",
        reviewed_at=datetime.utcnow(),
    )
    db.add(vet)
    db.flush()
    return vet


def main() -> None:
    db = SessionLocal()
    try:
        created: list[str] = []
        for i, payload in enumerate(DEMO_VETS):
            # 평점 4.6 ~ 5.0 사이로 적당히 분포
            rating = 5 if i % 2 == 0 else 4
            vet = _upsert_vet(db, payload, rating=rating)
            _attach_demo_rating(db, vet.id, rating=rating, samples=4)
            created.append(f"{vet.hospital_name} ({vet.email})")
        db.commit()
        print("✅ 시드 완료")
        for line in created:
            print(f"  - {line}")
        print(f"\n로그인 비밀번호 (수의사): {DEMO_PASSWORD}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
