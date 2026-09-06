#!/usr/bin/env python3
"""check-submodule-consistency.py — 子模块指针一致性门禁 (BET-Y1Q4-T10-129)

CI 级检查：检测 .gitmodules 中声明的所有子模块的 HEAD 指针是否漂移。

用法:
  python3 bin/gac/check-submodule-consistency.py                 # 默认检查
  python3 bin/gac/check-submodule-consistency.py --fail-on-drift # 有漂移时 exit 1
  python3 bin/gac/check-submodule-consistency.py --json          # JSON 输出
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WS_ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    r = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd or WS_ROOT,
    )
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _parse_submodules() -> list[dict[str, str]]:
    """从 .gitmodules 解析子模块列表。"""
    gitmodules = WS_ROOT / ".gitmodules"
    if not gitmodules.exists():
        return []
    modules: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in gitmodules.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("[submodule "):
            if current:
                modules.append(current)
            name = line.split('"')[1] if '"' in line else ""
            current = {"name": name}
        elif line.startswith("path ="):
            current["path"] = line.split("=", 1)[1].strip()
        elif line.startswith("url ="):
            current["url"] = line.split("=", 1)[1].strip()
        elif line.startswith("branch ="):
            current["branch"] = line.split("=", 1)[1].strip()
    if current:
        modules.append(current)
    return modules


def _check_drift(modules: list[dict[str, str]]) -> list[dict]:
    """检查每个子模块的指针漂移状态。"""
    results = []
    for mod in modules:
        path = mod.get("path", "")
        name = mod.get("name", path)
        full_path = WS_ROOT / path

        entry: dict = {
            "name": name,
            "path": path,
            "url": mod.get("url", ""),
            "status": "unknown",
            "current_sha": None,
            "dirty": False,
            "error": None,
        }

        if not full_path.exists():
            entry["status"] = "missing"
            entry["error"] = f"submodule path does not exist: {path}"
            results.append(entry)
            continue

        # Check if it's a valid git repo
        rc, sha, err = _git("rev-parse", "HEAD", cwd=full_path)
        if rc != 0:
            entry["status"] = "not_a_repo"
            entry["error"] = f"not a git repository: {err}"
            results.append(entry)
            continue

        entry["current_sha"] = sha

        # Check for dirty working tree
        rc, status_out, _ = _git("status", "--porcelain", cwd=full_path)
        if status_out:
            entry["dirty"] = True

        # Check if the recorded commit matches what's in the superproject index
        rc, recorded, _ = _git(
            "ls-tree", "HEAD", "--", path, cwd=WS_ROOT
        )
        if rc == 0 and recorded:
            # Format: "160000 commit <sha>\tpath"
            recorded_sha = recorded.split()[2] if len(recorded.split()) >= 3 else ""
            if recorded_sha and recorded_sha != sha:
                entry["status"] = "drifted"
                entry["recorded_sha"] = recorded_sha
            else:
                entry["status"] = "consistent"
        else:
            entry["status"] = "untracked"

        results.append(entry)

    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fail-on-drift", action="store_true",
                    help="有漂移时返回 exit 1")
    ap.add_argument("--json", action="store_true", dest="json_output",
                    help="JSON 格式输出")
    args = ap.parse_args()

    modules = _parse_submodules()
    if not modules:
        if args.json_output:
            print(json.dumps({"modules": [], "drift_count": 0, "total": 0}))
        else:
            print("No submodules found.")
        return 0

    results = _check_drift(modules)
    drift_count = sum(1 for r in results if r["status"] == "drifted")
    dirty_count = sum(1 for r in results if r.get("dirty"))
    missing_count = sum(1 for r in results if r["status"] in ("missing", "not_a_repo"))

    if args.json_output:
        output = {
            "modules": results,
            "total": len(results),
            "drift_count": drift_count,
            "dirty_count": dirty_count,
            "missing_count": missing_count,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        # Human-readable output
        status_icons = {
            "consistent": "✅",
            "drifted": "🔴",
            "dirty": "⚠️",
            "missing": "❌",
            "not_a_repo": "❌",
            "untracked": "❓",
            "unknown": "❓",
        }
        print(f"=== Submodule Consistency Check ({len(results)} modules) ===")
        for r in results:
            icon = status_icons.get(r["status"], "❓")
            dirty_mark = " [dirty]" if r.get("dirty") else ""
            drift_mark = ""
            if r["status"] == "drifted":
                drift_mark = f" (recorded: {r.get('recorded_sha', '?')[:8]})"
            err_mark = f" — {r['error']}" if r.get("error") else ""
            print(f"  {icon} {r['path']}{dirty_mark}{drift_mark}{err_mark}")

        print(f"\nSummary: {len(results)} total, {drift_count} drifted, "
              f"{dirty_count} dirty, {missing_count} missing/error")

    if args.fail_on_drift and (drift_count > 0 or missing_count > 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
