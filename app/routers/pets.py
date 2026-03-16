from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Pet, User
from app.schemas import PetCreate, PetUpdate, PetResponse
from app.routers.dependencies import get_current_user

router = APIRouter(prefix="/pets", tags=["pets"])


@router.post("", response_model=PetResponse, status_code=status.HTTP_201_CREATED)
def create_pet(
    pet_data: PetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """반려동물 등록"""
    
    db_pet = Pet(
        owner_id=current_user.id,
        name=pet_data.name,
        species=pet_data.species,
        breed=pet_data.breed,
        age=pet_data.age,
        gender=pet_data.gender,
        profile_image_url=pet_data.profile_image_url
    )
    db.add(db_pet)
    db.commit()
    db.refresh(db_pet)
    
    return db_pet


@router.get("", response_model=List[PetResponse])
def get_my_pets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """내 반려동물 목록 조회"""
    
    pets = db.query(Pet).filter(Pet.owner_id == current_user.id).all()
    return pets


@router.get("/{pet_id}", response_model=PetResponse)
def get_pet(
    pet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """반려동물 상세 조회"""
    
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id
    ).first()
    
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="반려동물을 찾을 수 없습니다."
        )
    
    return pet


@router.put("/{pet_id}", response_model=PetResponse)
def update_pet(
    pet_id: int,
    pet_data: PetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """반려동물 정보 수정"""
    
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id
    ).first()
    
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="반려동물을 찾을 수 없습니다."
        )
    
    # 수정
    update_data = pet_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pet, field, value)
    
    db.commit()
    db.refresh(pet)
    
    return pet


@router.delete("/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pet(
    pet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """반려동물 삭제"""
    
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id
    ).first()
    
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="반려동물을 찾을 수 없습니다."
        )
    
    db.delete(pet)
    db.commit()
    
    return None
