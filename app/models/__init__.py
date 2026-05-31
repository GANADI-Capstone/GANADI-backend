from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional
import enum

from app.database import Base


class GenderEnum(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"


class SpeciesEnum(str, enum.Enum):
    DOG = "dog"
    CAT = "cat"


class User(Base):
    """일반 사용자 (반려동물 보호자)"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(20))
    kakao_id = Column(String(255), unique=True, index=True)
    profile_image_url = Column(String(500))
    
    role = Column(String(20), default="user", nullable=False)
    is_suspended = Column(Boolean, default=False, nullable=False)
    suspend_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    pets = relationship("Pet", back_populates="owner", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    payment_orders = relationship("PaymentOrder", back_populates="user")


class Vet(Base):
    """수의사 계정 + 병원 프로필

    회원가입 시 email/password/name/hospital_name만 채워지고,
    프로필 관련 4개 필드(address/phone/specialty/business_hours)는
    PUT /api/vets/profile 에서 나중에 수정된다.
    """
    __tablename__ = "vets"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    hospital_name = Column(String(255))

    # 병원 프로필 (마이페이지에서 수정, 카카오맵 병원찾기/수의사 카드에 노출)
    address = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    specialty = Column(String(255), nullable=True)           # 예: "안과, 피부과"
    business_hours = Column(String(255), nullable=True)      # 예: "평일 09:00-19:00"

    # 자격증 인증 (회원가입 시 입력 → 관리자 검토 후 approval_status 결정)
    license_number = Column(String(50), nullable=True)            # 수의사 면허번호
    license_image_url = Column(String(500), nullable=True)        # 면허증 사본 (이미지/PDF)
    employment_doc_url = Column(String(500), nullable=True)       # 재직/개업 증명서 (선택)

    approval_status = Column(String(20), default="pending", nullable=False)
    rejection_reason = Column(Text, nullable=True)                # 반려 시 사유
    # 원격 소견 결제 금액(원). 비우면 서버 기본값(OPINION_SERVICE_FEE_WON) 사용
    opinion_fee_won = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)                 # 관리자 검토 일시

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 이 수의사가 받은/작성한 소견 목록
    opinions = relationship("Opinion", back_populates="vet", cascade="all, delete-orphan")


class Pet(Base):
    """반려동물"""
    __tablename__ = "pets"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    name = Column(String(100), nullable=False)
    species = Column(Enum(SpeciesEnum), nullable=False)  # dog, cat
    breed = Column(String(100))
    age = Column(Integer)
    gender = Column(Enum(GenderEnum))  # male, female
    profile_image_url = Column(String(500))
    is_neutered = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="pets")
    diagnoses = relationship("DiagnosisResult", back_populates="pet", cascade="all, delete-orphan")


class DiagnosisResult(Base):
    """진단 결과"""
    __tablename__ = "diagnosis_results"
    
    id = Column(Integer, primary_key=True, index=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False)
    
    image_url = Column(String(500), nullable=False)
    animal_type = Column(Enum(SpeciesEnum), nullable=False)  # dog, cat
    
    # AI 분석 결과
    predictions = Column(JSON, nullable=False)  # {"결막염": {"label": "유", "confidence": 87.3}, ...}
    main_disease = Column(String(100))
    main_confidence = Column(Integer)
    is_normal = Column(Boolean, default=False)
    
    report_pdf_url = Column(String(500))
    report_data = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    pet = relationship("Pet", back_populates="diagnoses")
    opinions = relationship("Opinion", back_populates="diagnosis", cascade="all, delete-orphan")

    # 응답 평탄화: Pydantic from_attributes=True 가 그대로 매핑한다.
    # 라우터에서 joinedload(DiagnosisResult.pet) 로 N+1 을 방지할 것.
    @property
    def pet_name(self) -> Optional[str]:
        return self.pet.name if self.pet else None


class Opinion(Base):
    """수의사 소견서 (보호자 요청 → 수의사 작성까지의 라이프사이클을 한 테이블로 관리)

    라이프사이클:
      1. 보호자가 POST /api/opinions/request 로 요청 → 행이 생성되며 content/answered_at 은 null
      2. 수의사가 POST /api/opinions/{id} 로 작성 → content/recommendation/visit_required/answered_at 채움
      3. 수의사가 PUT /api/opinions/{id} 로 내용 수정 가능 (answered_at 은 유지)

    "미답변/완료" 필터는 content IS NULL 여부로 판별한다 (별도 상태 컬럼 없음).
    """
    __tablename__ = "opinions"

    id = Column(Integer, primary_key=True, index=True)
    diagnosis_id = Column(Integer, ForeignKey("diagnosis_results.id"), nullable=False, index=True)
    vet_id = Column(Integer, ForeignKey("vets.id"), nullable=False, index=True)

    # 수의사 작성 영역 — 요청 시점에는 null, 작성되면 채워짐
    content = Column(Text, nullable=True)                    # 소견 본문
    recommendation = Column(Text, nullable=True)             # 권고사항
    visit_required = Column(Boolean, default=False)          # 병원 방문 권유 여부

    # 보호자 요청 영역 — 요청 시 전달한 증상 메모 (수의사가 참고)
    symptom_memo = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)  # 요청 접수 시각
    answered_at = Column(DateTime, nullable=True)                       # 수의사가 최초 작성한 시각
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 수의사가 작성 시 설정 가능(원 단위). 보호자 평점/리뷰는 작성 완료 후 별도 API 로 저장.
    service_fee = Column(Integer, nullable=True)
    owner_rating = Column(Integer, nullable=True)
    owner_review = Column(Text, nullable=True)

    diagnosis = relationship("DiagnosisResult", back_populates="opinions")
    vet = relationship("Vet", back_populates="opinions")


class PaymentOrder(Base):
    """토스페이먼츠 테스트 결제 주문 → 승인 후 Opinion 행 생성."""

    __tablename__ = "payment_orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    toss_order_id = Column(String(64), unique=True, nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    currency = Column(String(10), default="KRW", nullable=False)
    status = Column(String(32), default="pending", nullable=False)
    payment_key = Column(String(200), nullable=True)

    vet_id = Column(Integer, ForeignKey("vets.id"), nullable=False)
    diagnosis_id = Column(Integer, ForeignKey("diagnosis_results.id"), nullable=False)
    symptom_memo = Column(Text, nullable=True)

    opinion_id = Column(Integer, ForeignKey("opinions.id"), nullable=True)
    webhook_last_status = Column(String(32), nullable=True)
    webhook_last_payload = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="payment_orders")


class Notification(Base):
    """사용자 알림"""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    message = Column(String(500), nullable=False)
    type = Column(String(50), nullable=False)
    is_read = Column(Boolean, default=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="notifications")


class PushSubscription(Base):
    """Web Push 구독 정보 (보호자/수의사 공용).

    - PushManager.subscribe() 가 만들어 준 endpoint/keys 를 그대로 저장.
    - 한 사용자가 여러 브라우저/기기에서 구독할 수 있어 N 건 가능.
    - 백엔드 알림 발송 시 user_id 또는 vet_id 로 lookup.
    """

    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)

    # 둘 중 하나만 채워진다. (보호자 또는 수의사)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    vet_id = Column(Integer, ForeignKey("vets.id"), nullable=True, index=True)

    endpoint = Column(Text, nullable=False)
    p256dh = Column(String(255), nullable=False)
    auth_secret = Column(String(255), nullable=False)
    user_agent = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AdminReport(Base):
    """관리자가 처리하는 신고 (피그마 신고 관리 탭 대응)

    보호자가 POST /api/reports 로 접수하고, 관리자가 상태를 갱신한다.
    """

    __tablename__ = "admin_reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reporter_email = Column(String(255), nullable=True)
    target_type = Column(String(32), nullable=False)  # vet, user, review, other
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    target_vet_id = Column(Integer, ForeignKey("vets.id"), nullable=True, index=True)
    target_label = Column(String(255), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending, processing, resolved, dismissed
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        "ReportMessage",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="ReportMessage.created_at",
    )


class ReportMessage(Base):
    """신고 건별 관리자↔신고자/피신고자 소통 스레드"""

    __tablename__ = "report_messages"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("admin_reports.id"), nullable=False, index=True)
    sender_role = Column(String(16), nullable=False)  # admin, user, vet, system
    sender_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sender_vet_id = Column(Integer, ForeignKey("vets.id"), nullable=True)
    # reporter: 신고자에게 공개 | subject: 피신고 대상 | internal: 관리자 전용
    audience = Column(String(16), nullable=False)
    body = Column(Text, nullable=False)
    email_sent = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    report = relationship("AdminReport", back_populates="messages")


class CollectedSample(Base):
    """학습 데이터 수집 (동의 opt-in, 검수 후 export)."""

    __tablename__ = "collected_samples"

    id = Column(Integer, primary_key=True, index=True)
    diagnosis_id = Column(
        Integer, ForeignKey("diagnosis_results.id"), nullable=True, unique=True, index=True,
    )
    source = Column(String(32), nullable=False, default="user_upload")

    image_url = Column(String(500), nullable=False)
    image_storage_key = Column(String(500), nullable=True)

    animal_type = Column(Enum(SpeciesEnum), nullable=False)
    capture_device = Column(String(32), nullable=False)
    pet_breed = Column(String(100), nullable=True)
    pet_age = Column(Integer, nullable=True)
    pet_gender = Column(String(20), nullable=True)

    ai_predictions = Column(JSON, nullable=False)
    ai_top3 = Column(JSON, nullable=False)
    ai_all_diseases = Column(JSON, nullable=False)
    ai_main_disease = Column(String(100), nullable=True)
    ai_is_normal = Column(Boolean, nullable=False, default=False)
    ai_model_version = Column(String(64), nullable=True)
    ai_checkpoint = Column(String(255), nullable=True)

    training_consent = Column(Boolean, nullable=False, default=True)
    consent_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    consent_version = Column(String(32), nullable=False, default="v1")

    label_status = Column(String(32), nullable=False, default="pending", index=True)
    confirmed_disease = Column(String(100), nullable=True)
    confirmed_severity = Column(String(32), nullable=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reject_reason = Column(Text, nullable=True)

    exported_at = Column(DateTime, nullable=True)
    export_batch_id = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    diagnosis = relationship("DiagnosisResult", backref="collected_sample")


class PasswordResetToken(Base):
    """비밀번호 재설정 1회용 토큰 (원문은 DB에 저장하지 않음)"""

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    account_type = Column(String(8), nullable=False)  # user | vet
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    vet_id = Column(Integer, ForeignKey("vets.id"), nullable=True, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
