from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from pathlib import Path

# uvicorn 을 프로젝트 루트에서 띄워도 backend/.env 를 읽도록 고정
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.is_file() else None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    # development | staging | production
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/petcare_db"
    
    # JWT
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # AI Server
    AI_SERVER_URL: str = "http://localhost:8000"

    # 학습 데이터 수집 (Phase 1) — false면 수집 로직·검증 전부 비활성 (기본)
    COLLECTION_ENABLED: bool = False
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    
    # Kakao OAuth — backend/.env 에 반드시 설정
    KAKAO_CLIENT_ID: str = ""
    KAKAO_CLIENT_SECRET: str = ""
    KAKAO_REDIRECT_URI: str = "http://localhost:5173/auth/kakao/callback"
    # True: Referer(프론트 origin)로 redirect_uri 자동 결정 — LAN IP·포트마다 카카오 콘솔에 URI 추가 필요
    # False: 항상 KAKAO_REDIRECT_URI만 사용 — 로컬은 콘솔에 해당 URI 하나만 등록하면 됨
    KAKAO_REDIRECT_USE_REFERER: bool = True
    
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

    # 이메일 (SMTP) — 비밀번호 재설정·신고/관리자 안내
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    # 네이버(465) 등 SSL 직접 연결 — true 이면 SMTP_USE_TLS 무시
    SMTP_USE_SSL: bool = False
    EMAIL_FROM: str = "noreply@peteyeai.com"
    EMAIL_FROM_NAME: str = "PET EYE AI"
    # 비밀번호 재설정 링크 베이스 — 프론트 origin (예: https://ganadi.site).
    # /reset-password 경로는 password_reset_url_base 프로퍼티가 붙임.
    PASSWORD_RESET_URL_BASE: str = ""
    PASSWORD_RESET_EXPIRE_MINUTES: int = 60
    # 신고 접수 시 관리자 알림 (선택)
    ADMIN_NOTIFY_EMAIL: str = ""
    # SMTP 미설정 시 재설정 링크를 API/화면에 노출 (로컬 개발용, 배포 시 false)
    EMAIL_DEV_EXPOSE_LINK: bool = True

    @property
    def password_reset_url_base(self) -> str:
        base = (self.PASSWORD_RESET_URL_BASE or self.FRONTEND_ORIGIN or "").rstrip("/")
        if not base:
            return "/reset-password"
        # .env 에 .../reset-password 를 넣은 경우 이중 경로 방지
        if base.endswith("/reset-password"):
            return base
        return f"{base}/reset-password"

    @property
    def is_mailpit_smtp(self) -> bool:
        host = (self.SMTP_HOST or "").strip().lower()
        return host in ("localhost", "127.0.0.1", "mailpit", "host.docker.internal")

    @property
    def smtp_configured(self) -> bool:
        if not self.SMTP_HOST or not self.EMAIL_FROM:
            return False
        if self.is_mailpit_smtp:
            return True
        return bool(self.SMTP_USER and self.SMTP_PASSWORD)

    @property
    def smtp_envelope_from(self) -> str:
        """네이버 등은 로그인 계정과 From 이 일치해야 함."""
        if self.SMTP_USER and not self.is_mailpit_smtp:
            return self.SMTP_USER.strip()
        return self.EMAIL_FROM.strip()

    @property
    def should_expose_dev_reset_link(self) -> bool:
        return self.EMAIL_DEV_EXPOSE_LINK and not self.smtp_configured

    @property
    def cors_origins_list(self) -> List[str]:
        """CORS origins를 리스트로 변환"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def toss_payments_configured(self) -> bool:
        return bool(self.TOSS_PAYMENTS_SECRET_KEY and self.TOSS_PAYMENTS_CLIENT_KEY)

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "development"

    @property
    def allow_lan_cors(self) -> bool:
        """LAN CORS regex — 로컬·스테이징 PWA 검증용. 프로덕션에서는 비활성."""
        return not self.is_production


settings = Settings()
