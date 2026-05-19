#!/usr/bin/env bash
# 프로덕션 Docker Compose 배포
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$BACKEND_DIR"

if [[ ! -f .env ]]; then
  echo "❌ backend/.env 없음 — .env.production.example 을 복사해 채우세요."
  exit 1
fi

# shellcheck disable=SC1091
source .env

: "${RDS_ENDPOINT:?RDS_ENDPOINT 가 .env 에 필요합니다}"
: "${DB_PASSWORD:?DB_PASSWORD 가 .env 에 필요합니다}"
: "${VITE_KAKAO_MAP_KEY:?VITE_KAKAO_MAP_KEY 가 .env 에 필요합니다 (프론트 빌드)}"

echo "=== 1/3 환경 검사 ==="
bash "$SCRIPT_DIR/check_production_env.sh"

GIT_SHA="$(git -C "$BACKEND_DIR/.." rev-parse --short HEAD 2>/dev/null || echo unknown)"
export SERVICE_BUILD_LABEL="${SERVICE_BUILD_LABEL:-prod-$(date +%Y-%m-%d)-${GIT_SHA}}"

echo ""
echo "=== 2/3 빌드·기동 (build=$SERVICE_BUILD_LABEL) ==="
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

echo ""
echo "=== 3/3 헬스 대기 ==="
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1/api/health" >/dev/null 2>&1 || \
     curl -fsSk "https://ganadi.site/api/health" >/dev/null 2>&1; then
    echo "✅ API healthy"
    bash "$SCRIPT_DIR/smoke-test.sh" "${SMOKE_BASE_URL:-https://ganadi.site}" && exit 0
  fi
  echo "  대기 중... ($i/30)"
  sleep 5
done

echo "❌ 헬스체크 타임아웃 — docker compose logs backend nginx"
exit 1
