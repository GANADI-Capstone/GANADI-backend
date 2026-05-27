# 출시·배포 준비 체크리스트 (PetCare / GANADI)

데모 심사와 **실제 배포(`ganadi.site`)** 전에 확인할 항목입니다.  
코드에 이미 반영된 것과, **운영·인프라에서 따로 해야 할 것**을 구분했습니다.

> 관련 파일: `docker-compose.prod.yml`, `nginx/nginx.prod.conf`, `.env.example`, `frontend/.env.example`

---

## 1. 코드베이스에 반영된 항목

### 보안·헬스
- API 보안 헤더 (`SecurityHeadersMiddleware`)
- `/health`, `/api/health` — DB `SELECT 1` 연결 확인, SMTP·AI URL 상태 노출
- 선택적 빌드 라벨 `SERVICE_BUILD_LABEL` (`/`·`/health`의 `build` 필드)
- 진단 이미지 업로드: 5MB 제한, JPEG/PNG MIME·시그니처 검증
- Nginx 프로덕션 CSP·HSTS (`nginx/nginx.prod.conf`)

### 사용자·법무 UX
- 개인정보·이용약관 페이지 및 로그인·회원가입 링크
- 회원가입 시 약관·개인정보 동의(필수)
- AI 스크리닝·결과 화면 면책 배너

### 인증·계정
- 비밀번호 찾기/재설정 (`POST /api/auth/password/forgot|reset`)
- 프론트: `ForgotPassword.tsx`, `ResetPassword.tsx`, 라우트 등록

### 수의사·소견·결제
- 수의사 상담료 설정 (`opinion_fee_won`, `PUT /api/vets/profile`)
- 수의사 찾기 카드에 원격 소견 금액 표시 (`VetSearch.tsx`)
- `match-hospitals` API에 `opinion_fee_won` 포함
- 토스페이먼츠 결제 라우터 (`/api/payments/toss/*`)

### 관리자·신고
- 사용자 정지 사유 (`suspend_reason`)
- 신고 스레드·관리자↔수의사 메시지 (`report_messages`)
- 종류별 메일 템플릿 (`app/services/mail_templates.py`)
- SMTP 발송 (`app/core/email.py`)

### DB 마이그레이션 (배포 시 `alembic upgrade head` 필수)
| 리비전 | 내용 |
|--------|------|
| `g9h0i1j2k3l4` | `suspend_reason`, `opinion_fee_won`, `target_user_id` |
| `h0i1j2k3l4m5` | `password_reset_tokens`, `report_messages`, `target_vet_id` |

---

## 2. 배포 전 필수 (P0)

> **자동화**: `scripts/check_production_env.sh`, `deploy-prod.sh`, `smoke-test.sh`  
> **상세 절차**: [DEPLOYMENT.md](./DEPLOYMENT.md)

### 코드·DB
- [ ] 미커밋 변경사항 커밋·푸시
- [ ] 프로덕션 DB에 `alembic upgrade head` 실행 (Docker `backend` CMD에 포함)
- [ ] 스키마 불일치 시 `/health` 또는 API 500 — 배포 직후 smoke test

### 환경변수·시크릿 (`.env` — **저장소 커밋 금지**)
- [ ] `SECRET_KEY` — 랜덤 값, 기본값 사용 금지
- [ ] `DATABASE_URL` — RDS 엔드포인트·계정
- [ ] `CORS_ORIGINS=https://ganadi.site`
- [ ] `FRONTEND_ORIGIN=https://ganadi.site`
- [ ] `PASSWORD_RESET_URL_BASE=https://ganadi.site` (경로 `/reset-password`는 코드에서 자동 추가)
- [ ] `EMAIL_DEV_EXPOSE_LINK=false`
- [ ] Kakao: `KAKAO_CLIENT_ID`, `KAKAO_CLIENT_SECRET`, `KAKAO_REDIRECT_URI=https://ganadi.site/auth/kakao/callback`
- [ ] `KAKAO_REDIRECT_USE_REFERER=false` (프로덕션 권장)
- [ ] VAPID: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` (재시작마다 키 변경 시 푸시 구독 무효)
- [ ] `vapid_keys.json` Git 미추적 확인

### Docker·인프ra
- [x] `docker-compose.yml` 프론트 `context` → `../frontend`
- [x] backend·ai healthcheck, prod compose RDS·ENVIRONMENT=production
- [x] Nginx CSP 토스페이ments 도메인 추가
- [ ] SSL: `/etc/ssl/ganadi/` → nginx 볼륨 마운트
- [ ] 배포: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
- [ ] 빌드 arg: `VITE_API_URL=https://ganadi.site`, `VITE_AI_SERVER_URL=https://ganadi.site/ai`, `VITE_KAKAO_MAP_KEY`

### 보안 (코드 반영)
- [x] `ENVIRONMENT=production` 시 OpenAPI `/docs` 비활성, LAN CORS regex 비활성
- [x] 프로덕션 기동 시 `SECRET_KEY`·SMTP dev 링크 등 검증
- [x] 로그인·비밀번호 찾기 rate limit
- [x] config.py 카카오 시크릿 하드코딩 제거

### 카카오 개발자 콘솔
- [ ] Web 사이트 도메인: `https://ganadi.site`
- [ ] Redirect URI: `https://ganadi.site/auth/kakao/callback`
- [ ] JavaScript 키 → 프론트 빌드

---

## 3. 핵심 기능 확인 (P1)

### 이메일
- [ ] SMTP 설정 (`SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` 등)
- [ ] `python scripts/test_smtp.py` 발송 테스트
- [ ] 비밀번호 재설정 메일 E2E
- [ ] 신고 접수 → `ADMIN_NOTIFY_EMAIL` 알림

### 결제 (토스)
- [ ] `TOSS_PAYMENTS_CLIENT_KEY`, `TOSS_PAYMENTS_SECRET_KEY`
- [ ] 소견 요청 → 결제 → 성공/실패 리다이렉트
- [ ] 웹훅 URL(HTTPS) + `TOSS_WEBHOOK_SECURITY_KEY`
- [x] Nginx CSP에 토스페이ments 도메인 추가

### Web Push (PWA)
- [ ] HTTPS에서 구독·알림 수신 E2E
- [ ] 소견 완료 시 보호자 푸시

### AI·저장
- [ ] AI 컨테이너 기동, `.pth` 체크포인트 마운트
- [ ] 진단 API 1회 호출
- [ ] S3 또는 `uploads` 볼륨 백업 계획

---

## 4. QA 시나리오 (P2)

| 역할 | 확인 항목 |
|------|-----------|
| 보호자 | 가입(약관) → 반려동물 → AI 진단 → 수의사 찾기(상담료) → 소견·결제 → 결과 |
| 수의사 | 상담료 설정 → 소견 작성 → PDF |
| 관리자 | 수의사 승인/정지 → 신고 스레드·메일 |
| 공통 | 카카오 로그인, PWA, 면책 배너 |

---

## 5. 배포 당일 Smoke Test (약 10분)

```
□ https://ganadi.site 로드
□ GET /api/health → status: healthy, database: connected
□ 카카오 로그인
□ AI 진단 1회
□ 수의사 찾기 → 상담료 표시 → 소견 요청
□ (결제 ON) 테스트 결제
□ 비밀번호 재설정 메일 1통
```

---

## 6. 배포 실행 계획 (권장 5일)

| 일차 | 작업 |
|------|------|
| D-5~4 | 코드 정리·커밋, `.env`·카카오·토스·SMTP 콘솔 설정, docker-compose 경로 확인 |
| D-3~2 | 스테이징 배포, 마이그레이션, SMTP·결제·푸시·AI E2E |
| D-1 | 역할별 QA, CSP·보안, `SERVICE_BUILD_LABEL`, 백업·모니터링 등록 |
| D-Day | 프로덕션 `docker compose ... up -d --build`, smoke test, 24h 모니터링 |

---

## 7. 법무·준수 (정식 서비스 전)

- 개인정보 처리방침·이용약관 **전문** 검토
- 수의사법·의료기기·동물보건 관련 표현 검토
- AI 고지 문구를 마케팅·스토어 정책에 맞게 정리

---

## 8. 데모 시연 팁

- 시연 계정·시드 (`python -m scripts.seed_demo_vets`)·AI 서버 가용성 사전 확인
- 네트워크 차단 시 사용자-facing 오류 메시지 확인
- Mailpit 로컬 테스트: `docker run -d --name peteye-mailpit -p 8025:8025 -p 1025:1025 axllent/mailpit` → UI http://localhost:8025

---

## 관련 문서

- [DEPLOYMENT.md](./DEPLOYMENT.md) — 배포 절차·스크립트
- [CHANGELOG_SESSION_2026-05-19.md](./CHANGELOG_SESSION_2026-05-19.md) — 기능 변경 이력

---

*최종 갱신: 2026-05-19*
