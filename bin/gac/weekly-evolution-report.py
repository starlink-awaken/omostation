#!/usr/bin/env python3
"""Weekly Evolution Report — 轻量级进化反馈循环.

不依赖缺失的数据源，直接使用现有工具生成进化报告:
- gac-drift: 治理漂移检测
- auto-fix-loop: 可修复漂移
- architecture-drift: 架构漂移
- bet-ledger: BET 执行状态
- resident-status: 常驻 agent 状态

Usage:
    python3 bin/gac/weekly-evolution-report.py [--apply]
"""
import json
import subprocess
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPORT_FILE = REPO / ".omo" / "state" / "weekly-evolution-report.json"


def run(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, "", str(e)


def main():
    now = datetime.now(UTC).isoformat()
    report = {"generated_at": now, "checks": {}, "proposals": []}

    # 1. GaC drift
    rc, out, _ = run(["python3", "bin/gac/gac-drift.py", "--json"])
    report["checks"]["gac_drift"] = {"ok": rc == 0, "output": out[:500]}

    # 2. Auto-fix (dry-run)
    rc, out, _ = run(["python3", "bin/gac/auto-fix-loop.py", "--json"])
    try:
        drift_data = json.loads(out) if out else {"total": 0}
    except:
        drift_data = {"total": 0}
    report["checks"]["auto_fix"] = {"drifts": drift_data.get("total", 0)}

    # 3. Architecture drift
    rc, out, _ = run(["python3", "bin/gac/architecture-drift.py", "--json"])
    report["checks"]["arch_drift"] = {"ok": rc == 0}

    # 4. BET ledger status
    rc, out, _ = run(["uv", "run", "--with", "pyyaml", "python", "bin/plan/bet-ledger.py", "status", "--json"])
    report["checks"]["bet_ledger"] = {"ok": rc == 0}

    # 5. Resident status
    rc, out, _ = run(["python3", "bin/gac/check-resident-status.py", "--json"])
    report["checks"]["resident"] = {"ok": rc == 0}

    # Generate proposals
    if drift_data.get("total", 0) > 0:
        report["proposals"].append({
            "type": "auto_fix",
            "description": f"Found {drift_data['total']} auto-fixable drifts",
            "command": "python3 bin/gac/auto-fix-loop.py --apply"
        })

    if not report["checks"]["gac_drift"]["ok"]:
        report["proposals"].append({
            "type": "gac_fix",
            "description": "GaC drift detected, needs manual review",
            "command": "python3 bin/gac/gac-drift.py"
        })

    # Save report
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    # Print summary
    print(f"Weekly Evolution Report — {now[:10]}")
    print(f"  GaC drift: {'PASS' if report['checks']['gac_drift']['ok'] else 'FAIL'}")
    print(f"  Auto-fix drifts: {drift_data.get('total', 0)}")
    print(f"  Architecture: {'PASS' if report['checks']['arch_drift']['ok'] else 'FAIL'}")
    print(f"  BET ledger: {'PASS' if report['checks']['bet_ledger']['ok'] else 'FAIL'}")
    print(f"  Resident: {'PASS' if report['checks']['resident']['ok'] else 'FAIL'}")
    print(f"  Proposals: {len(report['proposals'])}")
    print(f"\nReport saved to: {REPORT_FILE}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
