#!/usr/bin/env bash
# 프로덕션 .env 필수값 검사 (배포 전 실행)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${BACKEND_DIR}/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ backend/.env 가 없습니다."
  echo "   cp backend/.env.production.example backend/.env 후 값을 채우세요."
  exit 1
fi

cd "$BACKEND_DIR"

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

export ENVIRONMENT="${ENVIRONMENT:-production}"

echo "=== PET EYE AI 프로덕션 환경 검사 (ENVIRONMENT=$ENVIRONMENT) ==="

python - <<'PY'
import os
import sys

# backend 루트에서 app 패키지 import
sys.path.insert(0, os.getcwd())

from app.core.startup_checks import validate_production_settings

os.environ.setdefault("ENVIRONMENT", os.environ.get("ENVIRONMENT", "production"))
issues = validate_production_settings(strict=False)
if issues:
    print("\n⚠️  수정 권장 항목:")
    for item in issues:
        print(f"  - {item}")
validate_production_settings(strict=True)
print("✅ 필수 항목 통과")
PY

echo ""
echo "추가 수동 확인:"
echo "  - RDS_ENDPOINT, DB_PASSWORD (docker compose .env)"
echo "  - VITE_KAKAO_MAP_KEY (프론트 빌드 arg)"
echo "  - SSL: /etc/ssl/ganadi/ganadi.pem, ganadi.key"
echo "  - 카카오 콘솔 Redirect URI = https://ganadi.site/auth/kakao/callback"
