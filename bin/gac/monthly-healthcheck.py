#!/usr/bin/env python3
"""Monthly Health Check — 每月架构健康检查.

全量治理门禁 + 架构成熟度评估 + 改进建议.

Usage:
    python3 bin/gac/monthly-healthcheck.py --full
    python3 bin/gac/monthly-healthcheck.py --gac-gate
    python3 bin/gac/monthly-healthcheck.py --maturity
    python3 bin/gac/monthly-healthcheck.py --report
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPORT_FILE = REPO / ".omo" / "_state" / "monthly-healthcheck-latest.json"


def _run_cmd(cmd: list[str]) -> dict:
    """Run command and return result."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[:500] if result.stdout else "",
            "stderr": result.stderr[:200] if result.stderr else "",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def run_gac_gate() -> dict:
    """Run full GaC gate."""
    return _run_cmd(["python3", str(REPO / "bin/gac/gac-local-gate.py"), "--strict"])


def assess_maturity() -> dict:
    """Assess architecture maturity."""
    checks = {
        "治理门禁": _run_cmd(["python3", str(REPO / "bin/gac/gac-validate.py"), "--gate"]),
        "脚本注册": _run_cmd(["python3", str(REPO / "bin/ssot/script-registry.py"), "validate"]),
        "探测器心跳": _run_cmd(["python3", str(REPO / "bin/gac/probe-heartbeat-monitor.py"), "--status"]),
        "防腐管道": _run_cmd(["python3", str(REPO / "bin/gac/corrosion-pipeline-connector.py"), "--dry-run"]),
        "桥接运行时": _run_cmd(["python3", str(REPO / "bin/gac/bridge-runtime.py"), "--status"]),
        "北极星": _run_cmd(["python3", str(REPO / "bin/bc-os/north_star_meter_v3.py"), "--json"]),
        "进化引擎": _run_cmd(["python3", str(REPO / "bin/bc-os/evolution_engine.py"), "--json"]),
    }

    passed = sum(1 for v in checks.values() if v.get("ok"))
    total = len(checks)

    return {
        "score": f"{passed}/{total}",
        "percentage": round(passed * 100 / total, 1) if total > 0 else 0,
        "checks": {k: v.get("ok", False) for k, v in checks.items()},
    }


def generate_report() -> dict:
    """Generate monthly health check report."""
    gac = run_gac_gate()
    maturity = assess_maturity()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gac_gate": {"ok": gac.get("ok"), "details": gac.get("stdout", "")[:200]},
        "maturity": maturity,
        "recommendations": [],
    }

    # Generate recommendations
    if not gac.get("ok"):
        report["recommendations"].append("治理门禁未通过，请检查 GaC gate 输出")

    if maturity.get("percentage", 0) < 80:
        report["recommendations"].append(f"架构成熟度 {maturity.get('percentage', 0)}% 低于 80%，需要改进")

    if not report["recommendations"]:
        report["recommendations"].append("系统健康，继续保持")

    # Save report
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Monthly Health Check")
    parser.add_argument("--full", action="store_true", help="Full health check")
    parser.add_argument("--gac-gate", action="store_true", help="Run GaC gate only")
    parser.add_argument("--maturity", action="store_true", help="Assess maturity")
    parser.add_argument("--report", action="store_true", help="Generate report")
    args = parser.parse_args()

    if args.full:
        report = generate_report()
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    if args.gac_gate:
        result = run_gac_gate()
        print(result.get("stdout", result.get("stderr", "")))
        return 0 if result.get("ok") else 1

    if args.maturity:
        result = assess_maturity()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.report:
        if not REPORT_FILE.exists():
            print("No report found. Run --full first.")
            return 1
        report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
