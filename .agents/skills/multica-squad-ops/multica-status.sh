#!/usr/bin/env bash
# multica-status.sh — multica squad 体系秒级状态摘要
#
# 有意不并入 bin/omo-status 的 Rich TUI 内部（那是 projects/cockpit 子仓代码，
# 改它要走独立子仓 PR/CI 流程，成本和本次需求不成比例）。这是一个独立、轻量、
# 只读的旁路脚本，跟 omo-status/omo-top 平级存在，不是替代品。
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== multica squads ==="
multica squad list --output json 2>/dev/null | python3 -c '
import json, sys
squads = json.load(sys.stdin)
for s in squads:
    name = s.get("name")
    members = s.get("member_count")
    sid = s.get("id")
    print(f"  {name:12s} members={members}  id={sid}")
'

echo ""
echo "=== multica agents (multica-squad-ops 相关) ==="
multica agent list --output json 2>/dev/null | python3 -c '
import json, sys
agents = json.load(sys.stdin)
watch = {
    "Claude Lead", "Codex Sage", "Grok Devil", "Kimi CrossReview",
    "Codebuddy Batch", "Reasonix Batch", "Opencode Batch", "Pi Local", "OMP Local",
}
for a in agents:
    skill_names = [s.get("name") for s in a.get("skills", [])]
    name = a.get("name")
    if "multica-squad-ops" in skill_names or name in watch:
        status = a.get("status")
        runtime_id = a.get("runtime_id")
        print(f"  {name:20s} status={status:6s} runtime_id={runtime_id}")
'

echo ""
echo "=== quota-ledger 熔断状态 ==="
python3 -c '
import sys
import yaml
from pathlib import Path
ledger = Path(sys.argv[1]) / "quota-ledger.yaml"
d = yaml.safe_load(ledger.read_text())
for e in d.get("entries", []):
    runtime = e.get("runtime")
    tier = e.get("tier")
    mode = e.get("invocation_mode")
    flag = "EXHAUSTED" if e.get("last_exhausted_at") else "ok"
    print(f"  {runtime:12s} tier={tier:3s} mode={mode:14s} {flag}")
' "$SCRIPT_DIR"
