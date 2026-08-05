#!/usr/bin/env python3
"""Registry-driven CI check runner (ADR-0379 E-2).

从 ci-surfaces.yaml SSOT 读取某 workflow 登记的检查清单并逐个执行.
ci-surfaces.yaml 是执行清单的唯一来源: 新增/移除检查只改 registry,
不再手写 bash 循环 (governance-check.yml 旧实现 21 行 FAILED=1 循环废除,
消除 P77 silent-fail 调试史).

用法:
  python3 bin/gac/ci-check-runner.py --workflow governance-check.yml
  python3 bin/gac/ci-check-runner.py --workflow governance-check.yml --json
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
CI_SURFACES = WORKSPACE / ".omo" / "_truth" / "registry" / "ci-surfaces.yaml"


def _load_yaml(path: Path) -> dict:
    import yaml

    if not path.exists():
        return {}
    try:
        docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
    except Exception:
        return {}
    return docs[-1] if docs else {}


def run_surfaces(workflow: str, cwd: Path = WORKSPACE) -> dict:
    registry = _load_yaml(CI_SURFACES)
    surfaces = registry.get("surfaces") or []
    selected = [
        s
        for s in surfaces
        if isinstance(s, dict)
        and s.get("workflow") == workflow
        and s.get("status", "active") != "orphan"
    ]
    results = []
    failures = 0
    for surface in selected:
        tool = str(surface.get("tool") or "")
        if not tool:
            continue
        cmd = [sys.executable, tool] if tool.endswith(".py") else [tool]
        cmd += [str(a) for a in (surface.get("args") or [])]
        try:
            proc = subprocess.run(
                cmd, cwd=str(cwd), capture_output=True, text=True, check=False, timeout=300
            )
        except subprocess.TimeoutExpired:
            results.append({"tool": tool, "ok": False, "detail": "timeout (>300s)"})
            failures += 1
            continue
        ok = proc.returncode == 0
        if not ok:
            failures += 1
        results.append(
            {
                "tool": tool,
                "ok": ok,
                "detail": (proc.stderr or proc.stdout).strip().splitlines()[-1][:160]
                if not ok and (proc.stderr or proc.stdout)
                else "",
            }
        )
    return {
        "ok": failures == 0,
        "workflow": workflow,
        "selected": len(selected),
        "failures": failures,
        "results": results,
    }


def main() -> int:
    args = sys.argv[1:]
    json_mode = "--json" in args
    workflow = ""
    if "--workflow" in args:
        workflow = args[args.index("--workflow") + 1]
    if not workflow:
        print("❌ 需要 --workflow <file> (如 governance-check.yml)", file=sys.stderr)
        return 2
    report = run_surfaces(workflow)
    if json_mode:
        import json

        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    print(f"=== CI check runner: {workflow} ({report['selected']} checks) ===")
    for r in report["results"]:
        mark = "✅" if r["ok"] else "❌"
        detail = f" — {r['detail']}" if not r["ok"] and r["detail"] else ""
        print(f"  {mark} {r['tool']}{detail}")
    if report["ok"]:
        print(f"✅ {report['selected']} checks PASS")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
