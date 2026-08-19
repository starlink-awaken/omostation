#!/usr/bin/env bash
# GaC 治理快照每日落盘 — 替代从未入库的 cron-daily-dashboard.sh (T6-08 幽灵 cron 修复)
# 产出: .omo/_delivery/dashboard/daily-scan.jsonl (append-only, 一日一行)
# 语义: governance-scanner 的 stdout 汇总落盘, 补 F1 删行后缺失的文件产物面
# 治理: BET-Y1Q1-T6-08 处置修正 (推演文档 §3.1 产出对比结论: scanner stdout-only,
#       与旧 dashboard HTML 视图不等价 → 本脚本补落盘, 不重建 HTML)
set -euo pipefail

ROOT="${1:-$HOME/Workspace}"
OUT_DIR="$ROOT/.omo/_delivery/dashboard"
OUT="$OUT_DIR/daily-scan.jsonl"
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

mkdir -p "$OUT_DIR"

# scanner 汇总段 (===...Autonomy 行) 转单行 JSON 追加
python3 - "$ROOT" "$TS" "$OUT" <<'PYEOF'
import json, subprocess, sys
from pathlib import Path

root, ts, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
r = subprocess.run(
    ["python3", str(Path(root) / "bin/ssot/governance-scanner.py")],
    capture_output=True, text=True, timeout=600, cwd=root,
)
entry = {"recorded_at": ts, "exit": r.returncode}
for line in r.stdout.splitlines():
    if ":" in line and any(k in line for k in ("Debt:", "Agents:", "MOS:", "A2A:", "Autonomy:")):
        k, _, v = line.strip().partition(":")
        entry[k.strip()] = v.strip()
with out.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
print(f"dashboard: appended {ts} -> {out}")
PYEOF
