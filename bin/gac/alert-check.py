#!/usr/bin/env python3
"""Alert Check — 统一告警检查入口.

整合约束编译、M1 合规、推理引擎、场景状态于一体,
输出结构化告警报告.

用法:
    python3 alert-check.py              # 文本报告
    python3 alert-check.py --json       # JSON 输出
    python3 alert-check.py --enforce    # P0/P1 退出码 1
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # bin/gac/ → Workspace/
ECOS = REPO / "projects/ecos"


def _run(cmd: list[str], timeout: int = 60, cwd: Path | None = None) -> tuple[int, str]:
    try:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ECOS / "src")
        # Ensure uv is in PATH
        if "/opt/homebrew/bin" not in env.get("PATH", ""):
            env["PATH"] = "/opt/homebrew/bin:" + env.get("PATH", "")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          cwd=str(cwd) if cwd else None, env=env)
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        print(f"  [_run TIMEOUT] {cmd[:3]}", file=sys.stderr)
        return -1, "TIMEOUT"
    except Exception as e:
        print(f"  [_run ERROR] {cmd[:3]}: {e}", file=sys.stderr)
        return -1, str(e)


def check_constraints() -> dict:
    """约束编译器检查."""
    rc, out = _run([
        "uv", "run", "python3", "src/ecos/ssot/tools/ecos-constraint-compiler.py",
        "--enforce"
    ], cwd=ECOS)
    print(f"  [check_constraints] rc={rc}, ok={rc==0}", file=sys.stderr)
    return {"ok": rc == 0, "failed": 0 if rc == 0 else 1}


def check_m1() -> dict:
    """M1 status 合规."""
    rc, out = _run([
        "uv", "run", "python3", "src/ecos/ssot/tools/mof-scan.py",
        "--check-status"
    ], cwd=ECOS)
    violations = 0
    for line in out.splitlines():
        if "不合规:" in line:
            try:
                violations = int("".join(c for c in line if c.isdigit()) or "0")
            except ValueError:
                pass
    return {"ok": violations == 0, "violations": violations}


def check_reasoning() -> dict:
    """推理引擎状态 (使用已知正确的参数)."""
    engines = {}
    # mof-reason: impact analysis on a real node
    rc, _ = _run(["uv", "run", "python3", "src/ecos/ssot/tools/mof-reason.py",
                  "impact", "ACTION-ACP-IMPLEMENT"], cwd=ECOS)
    engines["mof-reason"] = "ok" if rc == 0 else "fail"
    # mof-derive: full report
    rc, _ = _run(["uv", "run", "python3", "src/ecos/ssot/tools/mof-derive.py"], cwd=ECOS)
    engines["mof-derive"] = "ok" if rc == 0 else "fail"
    # mof-gate: gate check
    rc, _ = _run(["uv", "run", "python3", "src/ecos/ssot/tools/mof-gate.py"], cwd=ECOS)
    engines["mof-gate"] = "ok" if rc == 0 else "fail"
    failed = [k for k, v in engines.items() if v == "fail"]
    return {"ok": len(failed) == 0, "engines": engines, "failed": failed}


def check_scenes() -> dict:
    """场景激活状态."""
    import yaml
    scene_dir = REPO / "docs" / "scene-cards"
    scenes = {}
    if scene_dir.exists():
        for f in sorted(scene_dir.glob("*.yaml")):
            try:
                text = f.read_text()
                if text.startswith("---"):
                    end = text.find("---", 3)
                    if end > 0:
                        fm = yaml.safe_load(text[3:end])
                        if isinstance(fm, dict):
                            scenes[fm.get("scene_id", f.stem)] = fm.get("status", "?")
            except Exception:
                continue
    active = sum(1 for s in scenes.values() if s in ("active", "pilot"))
    total = len(scenes)
    return {"ok": active >= total * 0.8, "active": active, "total": total, "scenes": scenes}


def main():
    parser = argparse.ArgumentParser(description="Unified alert check")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--enforce", action="store_true", help="exit 1 on P0/P1")
    args = parser.parse_args()

    now = datetime.now(UTC).isoformat()

    # 执行所有检查
    constraints = check_constraints()
    m1 = check_m1()
    reasoning = check_reasoning()
    scenes = check_scenes()

    # Debug: print raw results
    if os.environ.get("DEBUG"):
        print(f"DEBUG constraints: {constraints}", file=sys.stderr)
        print(f"DEBUG m1: {m1}", file=sys.stderr)
        print(f"DEBUG reasoning: {reasoning}", file=sys.stderr)
        print(f"DEBUG scenes: {scenes}", file=sys.stderr)

    # 生成告警
    alerts = []
    if not constraints["ok"]:
        alerts.append({"level": "P0", "msg": f"Constraint failed: {constraints['failed']}"})
    if not m1["ok"]:
        alerts.append({"level": "P0", "msg": f"M1 violations: {m1['violations']}"})
    if not reasoning["ok"]:
        alerts.append({"level": "P1", "msg": f"Reasoning engines fail: {reasoning['failed']}"})
    if not scenes["ok"]:
        alerts.append({"level": "P2", "msg": f"Scenes not active: {scenes['active']}/{scenes['total']}"})

    report = {
        "timestamp": now,
        "constraints": constraints,
        "m1": m1,
        "reasoning": reasoning,
        "scenes": scenes,
        "alerts": alerts,
        "overall": "healthy" if not alerts else "action_required",
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print("=" * 56)
    print("  Alert Check Report")
    print("=" * 56)
    print(f"  Time: {now}")
    print(f"  Constraints: {'PASS' if constraints['ok'] else 'FAIL'} ({constraints['failed']} failed)")
    print(f"  M1:          {'PASS' if m1['ok'] else 'FAIL'} ({m1['violations']} violations)")
    print(f"  Reasoning:   {'PASS' if reasoning['ok'] else 'FAIL'} ({', '.join(reasoning['failed']) or 'none'})")
    print(f"  Scenes:      {'PASS' if scenes['ok'] else 'FAIL'} ({scenes['active']}/{scenes['total']} active)")
    print(f"  Alerts:      {len(alerts)}")
    for a in alerts:
        print(f"    [{a['level']}] {a['msg']}")
    print(f"  Overall:     {report['overall']}")
    print(f"\n{'=' * 60}")

    if args.enforce:
        critical = [a for a in alerts if a["level"] in ("P0", "P1")]
        if critical:
            sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
