from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # Database
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/petcare_db"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # AI Server
    AI_SERVER_URL: str = "http://localhost:8000"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    
    # Kakao OAuth
    KAKAO_CLIENT_ID: str = "783bb48a7f853f7cabe3821fdf103eab"
    KAKAO_CLIENT_SECRET: str = "bxuGbL01bXVrR0SqH8Bf3gz72jlO5rkv"
    KAKAO_REDIRECT_URI: str = "http://localhost:5173/auth/kakao/callback"
    
    # S3 (선택사항)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = ""
    AWS_REGION: str = "ap-northeast-2"

    # Web Push (VAPID) — 비워두면 부팅 시 자동 생성해 ./vapid_keys.json 에 저장
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:noreply@ganadi.dev"

    # 배포 메타 (헬스/버전 표시용, 선택)
    SERVICE_BUILD_LABEL: str = ""

    # 결제 (토스페이먼츠 테스트 키 — 비워두면 결제 API 비활성)
    # https://developers.tosspayments.com 에서 테스트 클라이언트·시크릿 키 발급
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    TOSS_PAYMENTS_CLIENT_KEY: str = ""
    TOSS_PAYMENTS_SECRET_KEY: str = ""
    # 웹훅 보안 키 (개발자센터 웹훅 설정). 비워두면 서명 검증 생략(캡스톤 로컬용).
    TOSS_WEBHOOK_SECURITY_KEY: str = ""
    OPINION_SERVICE_FEE_WON: int = 30000

    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def cors_origins_list(self) -> List[str]:
        """CORS origins를 리스트로 변환"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def toss_payments_configured(self) -> bool:
        return bool(self.TOSS_PAYMENTS_SECRET_KEY and self.TOSS_PAYMENTS_CLIENT_KEY)


settings = Settings()
