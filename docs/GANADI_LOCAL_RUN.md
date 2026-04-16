# GANADI 팀 레포로 로컬 전체 실행

조직 GitHub에 나뉘어 있는 **프론트 / 백엔드 / AI** 세 레포를 각각 클론해, 모노레포와 **같은 흐름(로그인 → 반려동물 → 진단 → PDF)** 으로 돌리는 절차입니다.

레포 이름·URL은 조직 설정에 맞게 바꿉니다. 예시는 `GANADI-Capstone` 아래를 가정합니다.

| 구분 | 예시 레포 | 기본 포트 |
|------|-----------|-----------|
| AI (추론·리포트·PDF) | `GANADI-AI` | **8000** |
| 백엔드 (DB·JWT·진단 연계) | `GANADI-backend` | **8001** (`app/main.py` 기준) |
| 프론트 (Vite) | `GANADI-frontend` | **5173** (또는 `--port 5174`) |

포트를 바꾼 경우 **백엔드 `AI_SERVER_URL`**, **프론트 `VITE_API_URL`**, **백엔드 `CORS_ORIGINS`** 세 곳을 같이 맞춥니다.

---

## 0. 공통 준비

- **MySQL** 8.x, 빈 DB 하나 (예: `ganadi_db`)
- **Node.js** 18+
- **Python** 3.10+
- PDF/Claude 리포트까지 쓰려면 AI 쪽에 **`ANTHROPIC_API_KEY`** (`.env` 또는 셸)

---

## 1. 저장소 클론

```bash
mkdir ganadi-local && cd ganadi-local
git clone https://github.com/GANADI-Capstone/GANADI-AI.git
git clone https://github.com/GANADI-Capstone/GANADI-backend.git
git clone https://github.com/GANADI-Capstone/GANADI-frontend.git
```

AI 레포 레이아웃이 `api/main.py` + `models/` 구조인지 확인합니다. (모노레포에서 subtree로 맞춰 두었다면 동일합니다.)

---

## 2. MySQL

```sql
CREATE DATABASE ganadi_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

백엔드 `.env`의 `DATABASE_URL`을 본인 계정·비밀번호·DB명에 맞게 설정합니다.

---

## 3. AI 서버 (포트 8000)

```bash
cd GANADI-AI
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
# 선택: echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

레포 루트가 `api`가 아니라면, 해당 레포 README의 `uvicorn` 모듈 경로를 따릅니다.

---

## 4. 백엔드 (포트 8001)

```bash
cd GANADI-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 없으면 레포 안내에 따라 생성
# .env 에서:
#   DATABASE_URL=mysql+pymysql://...
#   AI_SERVER_URL=http://localhost:8000
#   CORS_ORIGINS=http://localhost:5173,http://localhost:5174
python -m app.main
# 또는: uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

`app/main.py`에 `if __name__`으로 `8001`이 박혀 있으면 그대로 두거나, 팀 규칙에 맞게 통일합니다.

---

## 5. 프론트

```bash
cd GANADI-frontend
cp .env.example .env
# VITE_API_URL=http://localhost:8001/api   (백엔드 포트에 맞출 것)
npm install
npm run dev
```

이 저장소(`capstone_petcare`)의 프론트는 **`VITE_API_URL`**이 없으면 기본으로 `http://localhost:8002/api`를 씁니다. 팀 백엔드가 **8001**이면 반드시 `.env`에 `VITE_API_URL=http://localhost:8001/api`를 넣습니다.

---

## 6. 동작 확인 순서

1. 브라우저에서 프론트 주소 접속 → 회원가입/로그인  
2. 반려동물 등록 → 진단 이미지 업로드  
3. PDF는 백엔드가 AI의 `/api/ai/report` → `/api/ai/pdf`를 호출하므로, **8000번 AI**와 **ANTHROPIC 키**가 있어야 정상 생성됩니다.

---

## 모노레포 한 번에 쓸 때

같은 머신에서 `api/`, `backend/`, `frontend/`만 쓰는 경우에도 위와 동일하게 **AI(8000) → 백엔드 → 프론트** 순으로 띄우고, 포트만 README·`.env`와 일치시키면 됩니다. 자세한 패키지·GPU 확인은 루트 [README.md](../README.md)를 참고하세요.

---

## 관리자 웹 (`/admin/dashboard`)

관리자는 **일반 사용자와 동일한** `POST /api/auth/user/login`으로 로그인하고, DB의 `users.role`이 **`admin`**인 계정만 관리자 화면에 들어갈 수 있습니다.

1. 백엔드 디렉터리에서 관리자 계정 생성 (이메일·비밀번호·이름):

   ```bash
   cd backend
   python scripts/create_admin_user.py admin@example.com '비밀번호12!' '운영자'
   ```

2. 프론트 로그인 화면에서 **「관리자」** 탭을 선택한 뒤 위 이메일/비밀번호로 로그인 → `/admin/dashboard`로 이동합니다.  
   (보호자 탭으로 로그인해도 `role`이 `admin`이면 자동으로 관리자 대시보드로 보냅니다.)

브라우저에는 `ganadi_auth_user`에 `{ name, role }`이 저장되므로, 새로고침 후에도 관리자 가드가 동작합니다.

---

## 자주 나는 문제

| 증상 | 점검 |
|------|------|
| 로그인 후 API 401/CORS | `CORS_ORIGINS`에 실제 브라우저 origin(포트 포함) 추가 |
| 진단 실패 / AI 연결 오류 | 백엔드 `AI_SERVER_URL`이 AI 서버와 같은 포트인지 |
| PDF만 실패 | AI 서버 로그에 `ANTHROPIC_API_KEY` 경고 없는지 |
| 프론트가 엉뚱한 API로 요청 | `VITE_API_URL` 저장 후 **`npm run dev` 재시작** (Vite는 빌드 시 env 고정) |
