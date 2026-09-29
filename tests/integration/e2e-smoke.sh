#!/usr/bin/env bash
# e2e-smoke.sh — 全系统端到端冒烟测试
# 验证 CLI→agora→runtime→CLI 链路基本可达
#
# 用法:
#   bash tests/integration/e2e-smoke.sh                  # 全量 (默认; 需 agora SSE :7431 / cron-service :7450 在线)
#   bash tests/integration/e2e-smoke.sh --no-services    # 跳过「服务在线」段
#   bash tests/integration/e2e-smoke.sh --no-imports     # 跳过「kairon 导入」段
#   bash tests/integration/e2e-cli-smoke.sh              # CI 纳入版 = CLI 入口子集 (上面两个开关都开)
#
# 为什么要开关: `tests/run-shell-suites.sh` 的纳入/排除粒度是**整文件**, 而本文件自带环境依赖
# (服务端口 / 各子项目 uv 环境) ⇒ 整份无法纳入 CI, 只能整份排除。加了开关之后, 「不需要外部
# 服务」的 CLI 入口子集可由 e2e-cli-smoke.sh 单独纳入, 而逻辑仍然只有这一份, 不会两边漂移。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PASS=0
FAIL=0

WITH_SERVICES=1
WITH_IMPORTS=1
for arg in "$@"; do
  case "$arg" in
    --no-services) WITH_SERVICES=0 ;;
    --no-imports)  WITH_IMPORTS=0 ;;
    -h|--help)     sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "e2e-smoke: 未知参数 $arg" >&2; exit 2 ;;
  esac
done

green() { echo "  ✅ $1"; PASS=$((PASS+1)); }
red()   { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

echo "╔═══════════════════════════════════════════╗"
echo "║  e2e Smoke — 全链路端到冒烟               ║"
echo "╚═══════════════════════════════════════════╝"

# 1. Agora 健康检查
echo ""
if [ "$WITH_SERVICES" = "1" ]; then
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
else
  echo "── 1. Agora 服务 ── ⏭ 跳过 (--no-services: CI 无 :7431/:7450 在线)"
fi

# 4. cockpit CLI
echo ""
echo "── 2. CLI 入口 ──"
# 断言口径: rc=0 **且** 输出含该工具名 —— 即「入口可达 + 打出来的是它自己的 help」。
# 早先三处都断言输出含 `usage:`, 但那只对 argparse 风格成立; cockpit 是自定义富文本 help
# (实测 rc=0, 输出 `╭─── 🚀 快速入口 ───╮`, 含 "cockpit" 不含 "usage:") ⇒ 该断言从一开始就是错的,
# 只因本文件被 shell-suites.exclude 排除、从没人跑过而无人发现 (2026-09-29)。
assert_help() {  # $1=tool $2=help-output
  [ -n "$2" ] && case "$2" in *"$1"*) return 0 ;; esac
  return 1
}

if COCKPIT_HELP=$(cd "$ROOT/projects/cockpit" && uv run --frozen cockpit --help 2>&1) && assert_help cockpit "$COCKPIT_HELP"; then
  green "cockpit --help 输出 (含自身标识)"
else
  red "cockpit --help 失败"
fi

if AGORA_CLI=$(cd "$ROOT/projects/agora" && uv run --frozen agora --help 2>&1) && assert_help agora "$AGORA_CLI"; then
  green "agora --help 输出 (含自身标识)"
else
  red "agora --help 失败"
fi

if RUNTIME_CLI=$(cd "$ROOT/projects/runtime" && uv run --frozen runtime --help 2>&1) && assert_help runtime "$RUNTIME_CLI"; then
  green "runtime --help 输出 (含自身标识)"
else
  red "runtime --help 失败"
fi

# 7. kairon 各包导入测试
echo ""
if [ "$WITH_IMPORTS" = "1" ]; then
  echo "── 3. kairon 导入 ──"
  IMPORT_OK=0
  IMPORT_TOTAL=0
  for pkg in eidos kos kronos minerva ontoderive codeanalyze iris forge health_profile; do
    IMPORT_TOTAL=$((IMPORT_TOTAL+1))
    if RESULT=$(cd "$ROOT/projects/knowledge/kairon" && uv run python3 -c "import $pkg; print('ok')" 2>&1) && echo "$RESULT" | command grep -q "^ok$"; then
      IMPORT_OK=$((IMPORT_OK+1))
    fi
  done
  echo "  kairon 导入: $IMPORT_OK/$IMPORT_TOTAL"
  if [ "$IMPORT_OK" -eq "$IMPORT_TOTAL" ]; then
    green "全部 $IMPORT_TOTAL 包可导入"
  else
    red "$((IMPORT_TOTAL - IMPORT_OK))/$IMPORT_TOTAL 导入失败"
  fi
else
  echo "── 3. kairon 导入 ── ⏭ 跳过 (--no-imports: kairon-ci.yml 的 make test-fast 覆盖面更强)"
fi

# 8. gbrain CLI
echo ""
echo "── 4. gbrain — 跳过 (bun CLI 启动较慢) ──"
echo "  ⏭️  gbrain CLI 跳过 (手动: cd projects/knowledge/gbrain && bun run src/cli.ts --help)"

# ── 结果 ──
echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║  结果: $PASS passed / $((PASS+FAIL)) total"
echo "╚═══════════════════════════════════════════╝"
[ "$FAIL" -gt 0 ] && exit 1 || exit 0
