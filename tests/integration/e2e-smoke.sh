#!/usr/bin/env bash
# e2e-smoke.sh — 全系统端到端冒烟测试
# 验证 CLI→agora→runtime→CLI 链路基本可达
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PASS=0
FAIL=0

green() { echo "  ✅ $1"; PASS=$((PASS+1)); }
red()   { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

echo "╔═══════════════════════════════════════════╗"
echo "║  e2e Smoke — 全链路端到冒烟               ║"
echo "╚═══════════════════════════════════════════╝"

# 1. Agora 健康检查
echo ""
echo "── 1. Agora 服务 ──"
if HEALTH=$(curl -sf http://localhost:7431/health 2>&1) && [[ "$HEALTH" == *"ok"* ]]; then
  green "agora SSE :7431 /health 响应"
else
  red "agora SSE :7431 不可达"
fi

if SVC=$(curl -sf http://localhost:7431/health 2>&1) && [[ "$SVC" == *"tools"* ]]; then
  green "agora SSE :7431 服务正常"
else
  red "agora SSE :7431 响应异常"
fi

# 3. Cron-service
if CRON=$(curl -sf http://localhost:7450/health 2>&1) && [[ "$CRON" == *"scheduler_running"* ]]; then
  green "cron-service :7450 响应"
else
  red "cron-service 不可达"
fi

# 4. cockpit CLI
echo ""
echo "── 2. CLI 入口 ──"
if COCKPIT_HELP=$(cd "$ROOT/projects/cockpit" && uv run cockpit --help 2>&1) && [[ "$COCKPIT_HELP" == *"usage:"* ]]; then
  green "cockpit --help 输出"
else
  red "cockpit --help 失败"
fi

if AGORA_CLI=$(cd "$ROOT/projects/agora" && uv run agora --help 2>&1) && [[ "$AGORA_CLI" == *"usage:"* ]]; then
  green "agora --help 输出"
else
  red "agora --help 失败"
fi

if RUNTIME_CLI=$(cd "$ROOT/projects/runtime" && uv run runtime --help 2>&1) && [[ "$RUNTIME_CLI" == *"usage:"* ]]; then
  green "runtime --help 输出"
else
  red "runtime --help 失败"
fi

# 7. kairon 各包导入测试
echo ""
echo "── 3. kairon 导入 ──"
IMPORT_OK=0
IMPORT_TOTAL=0
for pkg in eidos kos kronos minerva ontoderive codeanalyze iris forge health_profile; do
  IMPORT_TOTAL=$((IMPORT_TOTAL+1))
  if RESULT=$(cd "$ROOT/projects/kairon" && uv run python3 -c "import $pkg; print('ok')" 2>&1) && echo "$RESULT" | grep -q "^ok$"; then
    IMPORT_OK=$((IMPORT_OK+1))
  fi
done
echo "  kairon 导入: $IMPORT_OK/$IMPORT_TOTAL"
if [ "$IMPORT_OK" -eq "$IMPORT_TOTAL" ]; then
  green "全部 $IMPORT_TOTAL 包可导入"
else
  red "$((IMPORT_TOTAL - IMPORT_OK))/$IMPORT_TOTAL 导入失败"
fi

# 8. gbrain CLI
echo ""
echo "── 4. gbrain — 跳过 (bun CLI 启动较慢) ──"
echo "  ⏭️  gbrain CLI 跳过 (手动: cd projects/gbrain && bun run src/cli.ts --help)"

# ── 结果 ──
echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║  结果: $PASS passed / $((PASS+FAIL)) total"
echo "╚═══════════════════════════════════════════╝"
[ "$FAIL" -gt 0 ] && exit 1 || exit 0
