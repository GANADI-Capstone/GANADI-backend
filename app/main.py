from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.config import settings
from app.routers import auth, pets, diagnosis, opinions, vets, notifications

# 업로드 디렉토리 생성
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# 스키마는 alembic 을 단일 소스로 관리한다.
# 과거에는 기동 시 Base.metadata.create_all(bind=engine) 로 자동 생성했으나,
# 모델만 수정하고 마이그레이션을 빼먹어도 DB 가 바뀌어버려
# 팀원 간 스키마 불일치의 원인이 되므로 제거했다.
# 신규 테이블/컬럼은 반드시 `alembic revision --autogenerate` + `alembic upgrade head` 로 반영한다.

# FastAPI 앱 생성
app = FastAPI(
    title="PetCare API",
    description="반려동물 안구 질환 진단 서비스 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙 (로컬 이미지)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 라우터 등록
app.include_router(auth.router, prefix="/api")
app.include_router(pets.router, prefix="/api")
app.include_router(diagnosis.router, prefix="/api")
app.include_router(opinions.router, prefix="/api")
app.include_router(vets.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")


@app.get("/")
def read_root():
    """헬스 체크"""
    return {
        "status": "ok",
        "service": "PetCare Backend API",
        "version": "1.0.0"
    }


@app.get("/health")
def health_check():
    """상세 헬스 체크"""
    return {
        "status": "healthy",
        "database": "connected",
        "ai_server": settings.AI_SERVER_URL
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)
