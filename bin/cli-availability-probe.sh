#!/usr/bin/env bash
# cli-availability-probe.sh — Cockpit CLI 可用性探针 (BET-Y1Q4-T13)
#
# 目的: 对 cockpit CLI 关键入口做轻量探活, 产出结构化 JSONL 台账,
#       供 cron 每日运行 + 人工随时手动执行。不是全量 106 命令回归
#       (全量见 docs/reports/cockpit-cli-command-availability-ledger.md, 人工触发)。
#
# 用法:
#   bash bin/cli-availability-probe.sh            # 全量探针 (~20 项)
#   bash bin/cli-availability-probe.sh --quick    # 仅核心探针 (4 项, <1min)
#
# 输出:
#   stdout                                人类可读摘要
#   runtime/probes/cli-availability.jsonl 每探针一行 JSON (追加)
#
# 退出码: 0 = 全部通过, 1 = 存在硬失败探针
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
cd "$ROOT"

QUICK=0
[[ "${1:-}" == "--quick" ]] && QUICK=1

COCKPIT=(uv run --project projects/cockpit cockpit)
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="$ROOT/runtime/probes"
OUT_FILE="$OUT_DIR/cli-availability.jsonl"
mkdir -p "$OUT_DIR"

fail=0
total=0
passed=0

# probe <name> <expect> <cmd...>
#   expect: exit0 — 命令退出码 0 即通过
#           json  — 退出码 0 且 stdout 末行可解析为 JSON object
probe() {
  local name="$1" expect="$2"
  shift 2
  total=$((total + 1))
  local start end ms out rc
  start="$SECONDS"
  out="$("$@" 2>&1)" && rc=0 || rc=$?
  end="$SECONDS"
  ms=$(( (end - start) * 1000 ))

  local status="FAIL" detail=""
  if [[ "$expect" == "exit0" ]]; then
    if [[ "$rc" -eq 0 ]]; then
      status="PASS"
    else
      detail="$(echo "$out" | tail -1 | cut -c1-200)"
    fi
  elif [[ "$expect" == "json" ]]; then
    if [[ "$rc" -eq 0 ]] && echo "$out" | python3 -c '
import json, sys
text = sys.stdin.read().strip()
for cand in (text, text.splitlines()[-1] if text else ""):
    try:
        d = json.loads(cand)
        if isinstance(d, dict):
            sys.exit(0)
    except Exception:
        pass
sys.exit(2)
' 2>/dev/null; then
      status="PASS"
    else
      detail="rc=$rc $(echo "$out" | tail -1 | cut -c1-200)"
    fi
  fi

  if [[ "$status" == "PASS" ]]; then
    passed=$((passed + 1))
  else
    fail=1
  fi

  python3 - "$TS" "$name" "$status" "$rc" "$ms" "$detail" >>"$OUT_FILE" <<'PYEOF'
import json, sys
ts, name, status, rc, ms, detail = sys.argv[1:7]
rec = {
    "ts": ts,
    "probe": name,
    "status": status,
    "exit_code": int(rc),
    "duration_ms": int(ms),
    **({"detail": detail} if detail else {}),
}
print(json.dumps(rec, ensure_ascii=False))
PYEOF
}

echo "=== cli-availability-probe @ ${TS} (quick=${QUICK}) ==="

# ── 核心探针 (always) ──────────────────────────────────────────────────────
probe "cockpit-help"         exit0 "${COCKPIT[@]}" --help
probe "memory-status-json"   json  "${COCKPIT[@]}" memory status --json
probe "governance-drift"     exit0 "${COCKPIT[@]}" governance drift-check
probe "governance-calibrate" exit0 "${COCKPIT[@]}" governance calibrate

# ── 扩展探针 (--quick 时跳过) ──────────────────────────────────────────────
if [[ "$QUICK" -eq 0 ]]; then
  probe "memory-recall-json"  json  "${COCKPIT[@]}" memory recall "probe" --limit 1 --json
  probe "harness-help"        exit0 "${COCKPIT[@]}" harness --help
  probe "agora-help"          exit0 "${COCKPIT[@]}" agora --help
  probe "bus-help"            exit0 "${COCKPIT[@]}" bus --help
  probe "events-help"         exit0 "${COCKPIT[@]}" events --help
  probe "facts-audit-help"    exit0 "${COCKPIT[@]}" facts-audit --help
  probe "domain-status-help"  exit0 "${COCKPIT[@]}" domain-status --help
  probe "mof-help"            exit0 "${COCKPIT[@]}" mof --help
  probe "telemetry-help"      exit0 "${COCKPIT[@]}" telemetry --help
  probe "data-help"           exit0 "${COCKPIT[@]}" data --help
  probe "knowledge-help"      exit0 "${COCKPIT[@]}" knowledge --help
  probe "c2g-help"            exit0 "${COCKPIT[@]}" c2g --help
  probe "workflow-help"       exit0 "${COCKPIT[@]}" workflow --help
  probe "readiness-help"      exit0 "${COCKPIT[@]}" readiness --help
fi

# 汇总行也入台账
python3 - "$TS" "$total" "$passed" "$fail" >>"$OUT_FILE" <<'PYEOF'
import json, sys
ts, total, passed, fail = sys.argv[1:5]
print(json.dumps({
    "ts": ts,
    "probe": "_summary",
    "status": "PASS" if fail == "0" else "FAIL",
    "total": int(total),
    "passed": int(passed),
    "failed": int(total) - int(passed),
}, ensure_ascii=False))
PYEOF

echo ""
echo "=== summary: ${passed}/${total} passed, fail=${fail} ==="
echo "ledger: $OUT_FILE"

exit "$fail"
