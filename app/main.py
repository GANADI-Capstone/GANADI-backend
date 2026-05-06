from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.config import settings
from app.routers import auth, pets, diagnosis, opinions, vets, notifications, admin, users, reports

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
# - 명시 origin 은 .env 의 CORS_ORIGINS (배포 환경 등)
# - 개발 중 휴대폰 PWA 검증을 위해 같은 LAN 사설 대역(127/localhost/10/172.16-31/192.168) 자동 허용
LAN_REGEX = (
    r"^https?:\/\/("
    r"localhost"
    r"|127\.0\.0\.1"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r")(:\d+)?$"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=LAN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙 (로컬 이미지)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 라우터 등록
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(pets.router, prefix="/api")
app.include_router(diagnosis.router, prefix="/api")
app.include_router(opinions.router, prefix="/api")
app.include_router(vets.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(reports.router, prefix="/api")


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
