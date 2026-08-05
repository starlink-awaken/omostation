#!/usr/bin/env python3
"""CR-X2-METRIC-TREND — 治理指标趋势检查."""

import json, subprocess, sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

def main() -> int:
    r = subprocess.run([sys.executable, str(WORKSPACE / "bin/gac/governance-evolution.py"), "status", "--json"], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        print("WARN governance-evolution 不可用, 跳过")
        return 0
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        print("WARN governance-evolution 输出异常, 跳过")
        return 0
    current, previous = data.get("current", {}), data.get("previous", {})
    findings = []
    for k in current:
        if k in previous:
            try:
                cv, pv = float(current[k]), float(previous[k])
                if pv > 0 and cv < pv * 0.9:
                    findings.append(f"{k}: {pv} -> {cv} (下降 {((1-cv/pv)*100):.0f}%)")
            except (ValueError, TypeError):
                pass
    if findings:
        print(f"WARN {len(findings)} 个指标下降:")
        for f in findings:
            print(f"  - {f}")
    else:
        print("OK 指标趋势稳定或上升")
    return 0

if __name__ == "__main__":
    sys.exit(main())
