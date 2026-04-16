from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class GenderEnum(str, Enum):
    MALE = "male"
    FEMALE = "female"


class SpeciesEnum(str, Enum):
    DOG = "dog"
    CAT = "cat"


# ==================== User Schemas ====================
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    phone: Optional[str] = None
    kakao_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== Vet Schemas ====================
class VetCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=2, max_length=100)
    hospital_name: Optional[str] = None


class VetLogin(BaseModel):
    email: EmailStr
    password: str


class VetResponse(BaseModel):
    id: int
    email: str
    name: str
    hospital_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    specialty: Optional[str] = None
    business_hours: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class VetProfileUpdate(BaseModel):
    """PUT /api/vets/profile 요청 스키마 — 전달된 필드만 부분 업데이트된다."""
    hospital_name: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    specialty: Optional[str] = Field(None, max_length=255)
    business_hours: Optional[str] = Field(None, max_length=255)


# ==================== Pet Schemas ====================
class PetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    species: SpeciesEnum
    breed: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=30)
    gender: Optional[GenderEnum] = None
    profile_image_url: Optional[str] = None


class PetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    breed: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=30)
    gender: Optional[GenderEnum] = None
    profile_image_url: Optional[str] = None


class PetResponse(BaseModel):
    id: int
    owner_id: int
    name: str
    species: SpeciesEnum
    breed: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[GenderEnum] = None
    profile_image_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== Diagnosis Schemas ====================
class DiagnosisCreate(BaseModel):
    pet_id: int
    image_url: str
    animal_type: SpeciesEnum
    predictions: dict
    main_disease: Optional[str] = None
    main_confidence: Optional[int] = None
    is_normal: bool = False


class DiagnosisResponse(BaseModel):
    id: int
    pet_id: int
    image_url: str
    animal_type: SpeciesEnum
    predictions: dict
    main_disease: Optional[str] = None
    main_confidence: Optional[int] = None
    is_normal: bool
    report_pdf_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== Opinion Schemas ====================
# 소견 요청/작성/조회 DTO. Opinion 모델 하나로 "요청"과 "작성된 소견"을
# 모두 표현하므로 용도별로 입력 스키마를 분리한다.

class OpinionRequestCreate(BaseModel):
    """보호자 → 수의사 소견 요청 (POST /api/opinions/request)"""
    diagnosis_id: int
    vet_id: int
    symptom_memo: Optional[str] = None  # 보호자가 남기는 증상 메모


class OpinionWrite(BaseModel):
    """수의사 소견 작성/수정 (POST·PUT /api/opinions/{id})"""
    content: str = Field(..., min_length=1)     # 소견 본문 (필수)
    recommendation: Optional[str] = None        # 권고사항 (예: "24시간 이내 내원")
    visit_required: bool = False                # 병원 방문 권유 여부
    service_fee: Optional[int] = Field(None, ge=0, description="소견 서비스 금액(원), 선택")


class OpinionResponse(BaseModel):
    """단건 조회 / 작성 결과 응답"""
    id: int
    diagnosis_id: int
    vet_id: int
    content: Optional[str] = None               # 요청 상태면 null
    recommendation: Optional[str] = None
    visit_required: bool
    symptom_memo: Optional[str] = None
    created_at: datetime
    answered_at: Optional[datetime] = None      # 작성 전이면 null
    service_fee: Optional[int] = None
    owner_rating: Optional[int] = None
    owner_review: Optional[str] = None

    class Config:
        from_attributes = True


class OpinionOwnerRating(BaseModel):
    """보호자: 소견에 대한 별점·리뷰 (작성 완료된 건만)"""
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = Field(None, max_length=2000)


class OpinionDetailResponse(OpinionResponse):
    """목록/상세 조회 응답: 프론트가 추가 API 호출 없이 카드를 그릴 수 있도록
    수의사·반려동물·진단 결과를 함께 내려준다."""
    vet_name: Optional[str] = None
    hospital_name: Optional[str] = None
    pet_name: Optional[str] = None
    owner_name: Optional[str] = None
    diagnosis: Optional[DiagnosisResponse] = None


# ==================== Auth Schemas ====================
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str
    role: str


class TokenData(BaseModel):
    user_id: Optional[int] = None
    user_type: Optional[str] = None  # "user" or "vet"


# ==================== Notification Schemas ====================
class NotificationResponse(BaseModel):
    id: int
    user_id: int
    message: str
    type: str
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True
