# PET EYE AI — 프로덕션 배포 가이드 (GANADI-backend)

실제 서비스(`https://ganadi.site`) 배포 절차입니다.  
체크리스트: [LAUNCH_READINESS.md](./LAUNCH_READINESS.md)

> **레포 구조:** 이 저장소는 백엔드 루트입니다. Docker 빌드 시 프론트는 **형제 폴더** `../frontend` (GANADI-frontend clone)가 필요합니다.

---

## 1. 사전 준비

### 서버 디렉터리 예시
```
/opt/ganadi/
  ├── GANADI-backend/    ← 이 레포
  └── frontend/          ← GANADI-frontend clone (docker-compose가 ../frontend 참조)
```

### 서버
- Docker + Docker Compose v2
- SSL: `/etc/ssl/ganadi/ganadi.pem`, `ganadi.key`
- RDS MySQL 8.0 (`ganadi_local`, `ganadi_user`)
- AI 체크포인트: `models/classifier/checkpoints/*.pth`

### 외부 콘솔
| 서비스 | 설정 |
|--------|------|
| 카카오 | Web `https://ganadi.site`, Redirect `https://ganadi.site/auth/kakao/callback`, JS 키 |
| 토스 | 웹훅 `https://ganadi.site/api/payments/toss/webhook` |
| SMTP | `EMAIL_DEV_EXPOSE_LINK=false` |

---

## 2. 환경변수

```bash
cp .env.production.example .env
# SECRET_KEY: openssl rand -hex 32
```

필수: `RDS_ENDPOINT`, `DB_PASSWORD`, `VITE_KAKAO_MAP_KEY`, Kakao, SMTP — `.env.production.example` 참고.

---

## 3. 배포 전 검사

```bash
chmod +x scripts/*.sh
./scripts/check_production_env.sh
```

---

## 4. 배포

```bash
./scripts/deploy-prod.sh
```

또는:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## 5. Smoke test

```bash
./scripts/smoke-test.sh https://ganadi.site
```

---

모노레포 전체 문서: [capstone_petcare](https://github.com/leejunyoung0610/capstone_petcare) `docs/DEPLOYMENT.md`

*최종 갱신: 2026-05-19*
