from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
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
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    pets = relationship("Pet", back_populates="owner", cascade="all, delete-orphan")


class Vet(Base):
    """수의사"""
    __tablename__ = "vets"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    hospital_name = Column(String(255))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    pet = relationship("Pet", back_populates="diagnoses")
