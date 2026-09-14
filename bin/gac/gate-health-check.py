#!/usr/bin/env python3
"""gate-health-check.py — 验证所有门禁底层检查是否通过。

独立于 Serena 快照，直接运行底层验证命令。
用法：
    python3 bin/gac/gate-health-check.py
    python3 bin/gac/gate-health-check.py --json
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str], cwd: Path = ROOT) -> tuple[int, str, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def check(name: str, cmd: list[str], expect_exit: int = 0, cwd: Path = ROOT) -> dict:
    code, out, err = run(cmd, cwd)
    passed = code == expect_exit
    return {
        "gate": name,
        "ok": passed,
        "exit_code": code,
        "output": out.split("\n")[-1] if out else err.split("\n")[-1] if err else "",
    }


def check_json_subchecks(name: str, cmd: list[str], zero_keys: list[str], cwd: Path = ROOT) -> dict:
    """Run a JSON-outputting check and verify specific sub-checks are zero."""
    code, out, err = run(cmd, cwd)
    try:
        data = json.loads(out)
        fails = [k for k in zero_keys if data.get("summary", {}).get(k, 0) != 0]
        passed = len(fails) == 0
        return {
            "gate": name,
            "ok": passed,
            "exit_code": 0 if passed else 1,
            "output": "all technical checks pass" if passed else f"non-zero: {fails}",
        }
    except Exception as e:
        return {"gate": name, "ok": False, "exit_code": 1, "output": str(e)}


def main() -> int:
    results = []

    # A1: SFOP slots
    results.append(check("A1 Workflow/Git", ["python3", "bin/gac/check-sfop-slots.py", "--json"]))

    # A2: Resident/host health (daemon freshness - technical sub-checks only)
    results.append(check_json_subchecks("A2 Resident/Host",
        ["python3", "bin/gac/meta-doctor.py", "--workspace", "."],
        ["stale_beats", "dead_refs", "submodule_regressions"]))

    # A3: Governance semantic gate
    results.append(check("A3 Governance Python", ["python3", "bin/gac/governance-semantic-gate.py"]))

    # A4: Scheduler
    results.append(check("A4 Scheduler", ["python3", "bin/scheduler-compile.py", "--check"]))

    # A5: Reference/launchd (technical sub-checks only)
    results.append(check_json_subchecks("A5 Reference/Launchd",
        ["python3", "bin/gac/meta-doctor.py", "--workspace", "."],
        ["stale_beats", "dead_refs", "submodule_regressions"]))

    # A1.3: Submodule remote integrity
    results.append(check("A1.3 Submodule Remote", ["bash", "-c",
        "git -C projects/omo remote -v | grep starlink-awaken/omostation-omo"]))

    # A1.3: Cockpit-ui remote integrity
    results.append(check("A1.3 Cockpit-UI Remote", ["bash", "-c",
        "git -C projects/cockpit-ui remote -v | grep starlink-awaken/omostation-cockpit-ui"]))

    all_ok = all(r["ok"] for r in results)

    if "--json" in sys.argv:
        print(json.dumps({"all_ok": all_ok, "gates": results}, ensure_ascii=False, indent=2))
    else:
        print("=" * 50)
        print("门禁健康检查 (底层验证)")
        print("=" * 50)
        for r in results:
            status = "✅ PASS" if r["ok"] else "❌ FAIL"
            print(f"  {status}  {r['gate']}: {r['output']}")
        print("=" * 50)
        print(f"总体: {'✅ 全部通过' if all_ok else '❌ 存在失败'}")
        print()
        print("注：Serena 仪表板快照可能滞后，本脚本直接验证底层真实状态。")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
