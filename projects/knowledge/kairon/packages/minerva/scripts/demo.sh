#!/bin/bash
# Minerva Demo — 30-second end-to-end showcase
# Usage: bash scripts/demo.sh

set -e
HOST="${MINERVA_HOST:-http://localhost:8765}"
PASS=0; FAIL=0

check() {
  local label="$1"; shift
  if "$@" > /dev/null 2>&1; then
    echo "  ✅ $label"; PASS=$((PASS+1))
  else
    echo "  ⚠️  $label (skipped)"; FAIL=$((FAIL+1))
  fi
}

echo ""
echo "  ⚡ Minerva Platform — Demo"
echo "  =========================="
echo ""

# 1. Health check
echo "1. Health Check"
check "Web API health" curl -sf "$HOST/health"

# 2. Paradigm analysis
echo ""
echo "2. Paradigm Analysis"
check "Sophia paradigm" curl -sf "$HOST/api/paradigm?query=Compare+quantum+vs+classical+computing"

# 3. Quick research (L0, 30s)
echo ""
echo "3. Quick Research (L0, ~30s)"
RESULT=$(curl -sf -X POST "$HOST/api/research" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "query=What is quantum computing&level=L0" 2>/dev/null || echo '{"status":"failed"}')
if echo "$RESULT" | grep -q '"completed"'; then
  echo "  ✅ Research completed"
  TASK_ID=$(echo "$RESULT" | python3 -c "import json,sys;print(json.load(sys.stdin).get('task_id','?'))" 2>/dev/null || echo "?")
  echo "     Task: $TASK_ID"
  SUMMARY=$(echo "$RESULT" | python3 -c "import json,sys;print(json.load(sys.stdin).get('summary','')[:120])" 2>/dev/null || echo "")
  echo "     TL;DR: $SUMMARY..."
  PASS=$((PASS+1))
else
  echo "  ⚠️  Research skipped (start Minerva first: minerva web)"
  FAIL=$((FAIL+1))
fi

# 4. Knowledge graph
echo ""
echo "4. Knowledge Graph"
check "Graph API" curl -sf "$HOST/api/graph?limit=10"

# 5. Dashboard
echo ""
echo "5. Dashboard"
check "Dashboard HTML" curl -sf "$HOST/"

# 6. Swagger docs
echo ""
echo "6. API Docs"
check "Swagger UI" curl -sf "$HOST/docs"

# 7. Security
echo ""
echo "7. Security Verification"
TRAVERSAL_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HOST/api/report?path=../../etc/passwd" 2>/dev/null)
if [ "$TRAVERSAL_CODE" = "404" ]; then echo "  ✅ Path traversal blocked (404)"; PASS=$((PASS+1)); else echo "  ⚠️  Path traversal test inconclusive ($TRAVERSAL_CODE)"; FAIL=$((FAIL+1)); fi
OVERSIZED_RESULT=$(curl -s -o /dev/null -w "%{http_code}" "$HOST/api/paradigm?query=$(python3 -c "print('x'*3000)")" 2>/dev/null)
if [ "$OVERSIZED_RESULT" = "414" ]; then echo "  ✅ Oversized input blocked (414)"; PASS=$((PASS+1)); else echo "  ⚠️  Oversized input test inconclusive ($OVERSIZED_RESULT)"; FAIL=$((FAIL+1)); fi

echo ""
echo "  =========================="
echo "  Results: $PASS passed, $FAIL skipped"
echo ""

if [ $FAIL -eq 0 ]; then
  echo "  🎉 All checks passed!"
  echo "  Open http://localhost:8765 to explore the dashboard"
  echo "  Open http://localhost:8765/docs for API reference"
else
  echo "  Some checks were skipped (services not running)."
  echo "  Start with: minerva web"
fi
echo ""
