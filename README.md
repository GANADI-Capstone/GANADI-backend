# PetCare Backend API

반려동물 안구 질환 AI 진단 서비스의 FastAPI 백엔드입니다.

## 기술 스택

- **FastAPI** 0.109.0 - 웹 프레임워크
- **SQLAlchemy** 2.0.25 - ORM
- **Alembic** 1.13.1 - 데이터베이스 마이그레이션
- **MySQL** 8.0 - 데이터베이스
- **PyJWT** - JWT 인증
- **httpx** - AI 서버 비동기 호출

## 설치 및 실행

### 1. 가상환경 생성 및 활성화

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 실제 값으로 수정
```

`.env` 설정 항목:

```env
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/petcare_db
SECRET_KEY=your-secret-key-change-this
AI_SERVER_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### 4. MySQL 데이터베이스 생성

```bash
mysql -u root -p
```

```sql
CREATE DATABASE petcare_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

### 5. 데이터베이스 마이그레이션

```bash
# 초기 마이그레이션 생성
alembic revision --autogenerate -m "Initial migration"

# 마이그레이션 적용
alembic upgrade head
```

### 6. 서버 실행

```bash
# 개발 모드 (자동 리로드)
uvicorn app.main:app --reload --port 8001

# 또는
python app/main.py
```

서버가 `http://localhost:8001`에서 실행됩니다.

## API 문서

서버 실행 후 아래 URL에서 자동 생성된 API 문서를 확인할 수 있습니다.

- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

## 프로젝트 구조

```
backend/
├── app/
│   ├── main.py              # FastAPI 앱 엔트리포인트
│   ├── database.py          # DB 연결 설정
│   ├── models/              # SQLAlchemy 모델
│   │   └── __init__.py      # User, Vet, Pet, DiagnosisResult
│   ├── schemas/             # Pydantic 스키마
│   │   └── __init__.py      # 요청/응답 스키마
│   ├── routers/             # API 라우터
│   │   ├── auth.py          # 인증 (회원가입, 로그인)
│   │   ├── pets.py          # 반려동물 CRUD
│   │   ├── diagnosis.py     # AI 진단
│   │   └── dependencies.py  # 의존성 (인증 등)
│   └── core/
│       ├── config.py        # 설정 관리
│       └── security.py      # JWT, 비밀번호 해싱
├── alembic/                 # 마이그레이션 파일
├── requirements.txt
├── alembic.ini
└── .env.example
```

## 주요 API 엔드포인트

### 인증 (Auth)

- `POST /api/auth/user/register` - 일반 사용자 회원가입
- `POST /api/auth/user/login` - 일반 사용자 로그인
- `POST /api/auth/vet/register` - 수의사 회원가입
- `POST /api/auth/vet/login` - 수의사 로그인

### 반려동물 (Pets)

- `POST /api/pets` - 반려동물 등록
- `GET /api/pets` - 내 반려동물 목록
- `GET /api/pets/{pet_id}` - 반려동물 상세 조회
- `PUT /api/pets/{pet_id}` - 반려동물 정보 수정
- `DELETE /api/pets/{pet_id}` - 반려동물 삭제

### 진단 (Diagnosis)

- `POST /api/diagnosis/analyze` - 안구 이미지 AI 분석
- `GET /api/diagnosis/history/{pet_id}` - 진단 이력 조회
- `GET /api/diagnosis/{diagnosis_id}` - 진단 결과 상세 조회

## 데이터베이스 모델

### User (일반 사용자)

```python
id, email, password_hash, name, phone, kakao_id
created_at, updated_at
```

### Vet (수의사)

```python
id, email, password_hash, name, hospital_name
created_at, updated_at
```

### Pet (반려동물)

```python
id, owner_id (FK), name, species (dog/cat), breed, age, gender, profile_image_url
created_at, updated_at
```

### DiagnosisResult (진단 결과)

```python
id, pet_id (FK), image_url, animal_type (dog/cat)
predictions (JSON), main_disease, main_confidence, is_normal
report_pdf_url, created_at
```

## 인증 방식

JWT Bearer 토큰 사용:

```bash
curl -H "Authorization: Bearer <access_token>" http://localhost:8001/api/pets
```

## 개발 팁

### 새로운 모델 추가 후 마이그레이션

```bash
alembic revision --autogenerate -m "Add new model"
alembic upgrade head
```

### 마이그레이션 롤백

```bash
alembic downgrade -1  # 1단계 되돌리기
alembic downgrade base  # 전체 되돌리기
```

### 데이터베이스 초기화

```bash
alembic downgrade base
alembic upgrade head
```

## TODO

- [ ] S3 이미지 업로드 구현
- [ ] 진단 결과 PDF 리포트 생성
- [ ] 카카오 소셜 로그인
- [ ] 수의사 인증 시스템
- [ ] 웹소켓 실시간 알림

## 라이선스

MIT
