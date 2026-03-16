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
    created_at: datetime
    
    class Config:
        from_attributes = True


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


# ==================== Auth Schemas ====================
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None
    user_type: Optional[str] = None  # "user" or "vet"
