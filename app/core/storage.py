import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
import uuid
from datetime import datetime
from pathlib import Path
import os

# 로컬 저장 디렉토리
UPLOAD_DIR = Path("uploads/pet_images")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 수의사 자격증/증빙 문서 (이미지 또는 PDF)
VET_DOCS_DIR = Path("uploads/vet_documents")
VET_DOCS_DIR.mkdir(parents=True, exist_ok=True)

# S3 클라이언트 초기화 (환경변수가 있을 때만)
s3_client = None
if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
    except Exception as e:
        print(f"S3 client initialization failed: {e}")


async def save_image_locally(file_bytes: bytes, filename: str) -> str:
    """
    이미지를 로컬 파일 시스템에 저장
    
    Args:
        file_bytes: 이미지 바이트 데이터
        filename: 원본 파일명
    
    Returns:
        저장된 파일의 상대 경로
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}_{filename}"
    file_path = UPLOAD_DIR / unique_filename
    
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    
    # 상대 경로 반환
    return f"uploads/pet_images/{unique_filename}"


async def upload_image_to_s3(file_bytes: bytes, filename: str) -> str:
    """
    이미지를 S3에 업로드
    
    Args:
        file_bytes: 이미지 바이트 데이터
        filename: 원본 파일명
    
    Returns:
        S3 URL
    """
    if not s3_client:
        raise Exception("S3 client not configured. Check AWS credentials.")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"pet_images/{timestamp}_{uuid.uuid4().hex[:8]}_{filename}"
    
    try:
        s3_client.put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=unique_filename,
            Body=file_bytes,
            ContentType='image/jpeg',
            ACL='public-read'  # 공개 읽기 권한
        )
        
        # Public URL 생성
        url = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{unique_filename}"
        return url
    
    except ClientError as e:
        raise Exception(f"S3 upload failed: {str(e)}")


async def save_image(file_bytes: bytes, filename: str) -> str:
    """
    이미지 저장 (S3 우선, 실패 시 로컬)
    
    Args:
        file_bytes: 이미지 바이트 데이터
        filename: 원본 파일명
    
    Returns:
        저장된 이미지 URL 또는 경로
    """
    # S3가 설정되어 있으면 S3에 업로드 시도
    if s3_client and settings.AWS_S3_BUCKET:
        try:
            return await upload_image_to_s3(file_bytes, filename)
        except Exception as e:
            print(f"S3 upload failed, falling back to local storage: {e}")
    
    # S3 실패 또는 미설정 시 로컬 저장
    return await save_image_locally(file_bytes, filename)


# ==================== Vet Documents (license, employment proof) ====================

ALLOWED_DOC_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
MAX_DOC_SIZE_MB = 10


def _safe_extension(filename: str) -> str:
    """파일명에서 안전한 확장자만 추출 (소문자)."""
    ext = Path(filename).suffix.lower()
    return ext if ext in ALLOWED_DOC_EXTENSIONS else ""


async def save_vet_document(file_bytes: bytes, original_filename: str, kind: str) -> str:
    """수의사 증빙 문서(면허증, 재직증명서 등) 로컬 저장.

    - kind: "license" 또는 "employment" — 파일명 prefix로 사용
    - 반환: 상대 경로 (DB 저장용)

    이미지든 PDF든 동일 디렉토리(`uploads/vet_documents/`)에 저장한다.
    추후 S3 사용 시 이 함수만 교체하면 된다.
    """
    if not file_bytes:
        raise ValueError("빈 파일은 업로드할 수 없습니다.")
    if len(file_bytes) > MAX_DOC_SIZE_MB * 1024 * 1024:
        raise ValueError(f"파일 크기는 {MAX_DOC_SIZE_MB}MB 이하여야 합니다.")

    ext = _safe_extension(original_filename)
    if not ext:
        raise ValueError(
            "허용되지 않은 파일 형식입니다. (jpg/jpeg/png/webp/pdf만 가능)"
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"{kind}_{timestamp}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = VET_DOCS_DIR / unique_filename

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    return f"uploads/vet_documents/{unique_filename}"
