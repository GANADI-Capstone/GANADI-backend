#!/usr/bin/env bash
# 배포 직후 smoke test
set -euo pipefail

BASE_URL="${1:-https://ganadi.site}"
BASE_URL="${BASE_URL%/}"

echo "=== Smoke test: $BASE_URL ==="

curl -fsSk "$BASE_URL/api/health" | python3 -c "
import json, sys
data = json.load(sys.stdin)
assert data.get('status') == 'healthy', data
assert data.get('database') == 'connected', data
print('  ✓ /api/health', data.get('status'), '| smtp:', data.get('smtp_configured'))
"

curl -fsSk -o /dev/null -w "  ✓ GET / → HTTP %{http_code}\n" "$BASE_URL/"

curl -fsSk -o /dev/null -w "  ✓ GET /ai/health → HTTP %{http_code}\n" "$BASE_URL/ai/health" || \
  echo "  ⚠ /ai/health 실패 (AI 컨테이너·체크포인트 확인)"

echo ""
echo "✅ Smoke test 완료 — 브라우저에서 카카오 로그인·AI 진단·소견 요청을 수동 확인하세요."
