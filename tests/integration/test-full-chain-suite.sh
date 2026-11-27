#!/usr/bin/env bash
# ==============================================================================
# omostation eCOS v6 全系统全链路端到端自动化测试套件 (Full-Chain Test Suite)
# 涵盖核心六大业务链路:
#   1. L3 前门与交互链路 (Cockpit CLI & UI)
#   2. I0/BOS 服务总线与协议路由 (BOS 87 Domains & Agora A2A)
#   3. L2 治理内核与状态机 (OMO Advisory Lock & Workflow Compliance)
#   4. L4 异构算力织网与真实推理 (AetherForge & Studio-01 Splash :8001)
#   5. L2/L3 主权知识与记忆中枢 (SQLite PRAGMA & Gbrain / KOS)
#   6. 系统级集成架构门禁 (Architecture Baseline 0 error & A1-A5 Evidence)
# ==============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export ROOT

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

pass_count=0
total_chains=6

echo -e "${BOLD}${BLUE}======================================================${NC}"
echo -e "${BOLD}${BLUE}   omostation eCOS v6 Full-Chain Automated Test Harness   ${NC}"
echo -e "${BOLD}${BLUE}======================================================${NC}"
echo "Workspace Root: $ROOT"
echo "Timestamp:      $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

# Helper to run a step with reporting
run_chain() {
  local chain_num="$1"
  local chain_name="$2"
  local cmd="$3"

  echo -e "${BOLD}▶ [Chain $chain_num/$total_chains] $chain_name${NC}"
  local t0=$(python3 -c "import time; print(time.time())")
  
  if bash -c "$cmd"; then
    local t1=$(python3 -c "import time; print(time.time())")
    local elapsed=$(python3 -c "print(f'{($t1 - $t0):.2f}')")
    echo -e "  ${GREEN}✅ PASS${NC} (took ${elapsed}s)\n"
    pass_count=$((pass_count + 1))
  else
    echo -e "  ${RED}❌ FAILED${NC}\n"
    return 1
  fi
}

# ------------------------------------------------------------------------------
# Chain 1: Cockpit CLI & Frontend Store
# ------------------------------------------------------------------------------
run_chain 1 "L3 Front-Door & Interface (Cockpit CLI / Web / UI Store)" '
  # Ensure cockpit venv is built if missing in fresh worktree
  if [ ! -d "$ROOT/projects/cockpit/.venv" ]; then
    (cd "$ROOT/projects/cockpit" && uv sync -q)
  fi
  # Ensure cockpit-ui node_modules is present
  if [ ! -d "$ROOT/projects/cockpit-ui/node_modules" ] && [ -d "/Users/xiamingxing/Workspace/projects/cockpit-ui/node_modules" ]; then
    ln -s "/Users/xiamingxing/Workspace/projects/cockpit-ui/node_modules" "$ROOT/projects/cockpit-ui/node_modules"
  fi
  "$ROOT/bin/cockpit" memory status --json >/dev/null
  "$ROOT/bin/cockpit" bos resolve bos://memory/mos/status >/dev/null
  cd "$ROOT/projects/cockpit" && uv run pytest tests/test_cli_contract.py -q >/dev/null
  cd "$ROOT/projects/cockpit-ui" && bun test src/hermes_console/ src/stores/ >/dev/null
'

# ------------------------------------------------------------------------------
# Chain 2: BOS Service Bus & Agora
# ------------------------------------------------------------------------------
run_chain 2 "I0/BOS Service Bus & Protocol Routing (BOS 87 Domains & Agora A2A)" '
  python3 "$ROOT/bin/gac/check-mcp-bos-uri-completeness.py" >/dev/null
  cd "$ROOT/projects/agora" && uv run pytest tests/test_a2a_smoke.py tests/test_a2a_replay_protection.py -q >/dev/null
'

# ------------------------------------------------------------------------------
# Chain 3: OMO Governance & Advisory Locks
# ------------------------------------------------------------------------------
run_chain 3 "L2 Governance Kernel & State Machine (Advisory Lock & Workflow)" '
  cd "$ROOT/projects/omo" && uv run pytest tests/test_advisory_lock.py -q >/dev/null
  AGCP_REQUIREMENT_ITERATION_GATE=0 uv run --with pyyaml python "$ROOT/bin/agent-workflow.py" compliance >/dev/null
'

# ------------------------------------------------------------------------------
# Chain 4: Compute Fabric & Real Inference
# ------------------------------------------------------------------------------
run_chain 4 "L4 Compute Fabric & Inference (AetherForge & Studio-01 Splash)" '
  nc -z -w 1 127.0.0.1 4000
  omlxc status --json >/dev/null
  python3 -c "
import urllib.request, json
url = \"http://100.74.244.58:8001/v1/chat/completions\"
payload = {\"model\": \"default\", \"messages\": [{\"role\": \"user\", \"content\": \"ping\"}], \"max_tokens\": 5}
req = urllib.request.Request(url, data=json.dumps(payload).encode(\"utf-8\"), headers={\"Content-Type\": \"application/json\"})
with urllib.request.urlopen(req, timeout=5) as resp:
    res = json.loads(resp.read().decode(\"utf-8\"))
    assert \"choices\" in res, \"No choices in Splash response\"
"
'

# ------------------------------------------------------------------------------
# Chain 5: Knowledge & Memory OS
# ------------------------------------------------------------------------------
run_chain 5 "L2/L3 Knowledge & Memory OS (SQLite PRAGMA & Vector Health)" '
  CANONICAL="$(python3 -c '\''import sys; sys.path.insert(0, "'"$ROOT"'/bin/lib"); from repo_root import canonical_root; print(canonical_root())'\'')"
  DB1="$ROOT/data/scene-metrics.db"
  [ ! -s "$DB1" ] && DB1="$CANONICAL/data/scene-metrics.db"
  sqlite3 "$DB1" "PRAGMA integrity_check;" | grep -q "ok"

  DB2="$ROOT/projects/knowledge/gbrain/memu-brain.db"
  [ ! -s "$DB2" ] && DB2="$CANONICAL/projects/knowledge/gbrain/memu-brain.db"
  sqlite3 "$DB2" "PRAGMA integrity_check;" | grep -q "ok"

  test -d "$ROOT/data/kos" || test -d "$CANONICAL/data/kos"
'

# ------------------------------------------------------------------------------
# Chain 6: System Integration & Environment Gates
# ------------------------------------------------------------------------------
run_chain 6 "System Integration & Environment Gates (Baseline 0 Error & A1-A5)" '
  python3 "$ROOT/bin/gac/materialize-system-state.py" >/dev/null
  python3 "$ROOT/bin/gac/architecture-check.py" --quick >/dev/null
  python3 "$ROOT/bin/gac/check-expiry-radar.py" --horizon 7 >/dev/null
  python3 "$ROOT/bin/gac/execution-environment-steward.py" >/dev/null
'

echo -e "${BOLD}${BLUE}======================================================${NC}"
echo -e "${BOLD}Results: $pass_count/$total_chains chains successfully verified.${NC}"
if [ "$pass_count" -eq "$total_chains" ]; then
  echo -e "${GREEN}${BOLD}🎉 ALL CHAINS VERIFIED PASS! System is in full-production ready state.${NC}"
  exit 0
else
  echo -e "${RED}${BOLD}⚠️  Some chains failed verification.${NC}"
  exit 1
fi
