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
