#!/usr/bin/env python3
"""CR-P74-SUBMODULE-DRIFT: detect submodule pointer vs origin/main divergence.

Part of T1-02 (BET-Y1Q1-T1-02): submodule pointer alignment + drift CI gate.

Policy (from docs/project-registry.yaml::submodule_policy):
  - stable:    MUST be on origin/main HEAD (fail on drift)
  - tracking:  MUST be on origin/main HEAD (fail on drift)
  - feature:   allowed on feature branches (warn if >tolerance_days stale)
  - dormant:   warn only

Exit codes:
  0 = all clear
  1 = stable/tracking drift detected (fail)
  2 = internal error
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

STABLE = {
    "projects/bus-foundation",
    "projects/kairon",
    "projects/l4-kernel",
    "projects/omo-debt",
}

TRACKING = {
    "projects/ecos",
    "projects/runtime",
    "scripts",
    "projects/omo",
}

FEATURE = {
    "projects/cockpit",
    "projects/metaos",
    "projects/aetherforge",
    "projects/agora",
}

DORMANT = {
    "projects/family-hub",
    "projects/model-driven",
    "projects/observability",
    "projects/gbrain",
}

EXTRA = {
    "projects/c2g",
    "projects/cockpit-ui",
    "projects/l4-kernel",
}


def _run(cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=15
        )
        return r.returncode, r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 2, ""


def _get_submodules(root: Path) -> list[str]:
    rc, out = _run(["git", "submodule", "foreach", "--quiet", "echo $sm_path"], str(root))
    if rc != 0 or not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _check_submodule(root: Path, sm_path: str) -> dict:
    sm_root = root / sm_path
    if not sm_root.is_dir():
        return {"path": sm_path, "status": "missing"}

    rc_head, head = _run(["git", "rev-parse", "HEAD"], str(sm_root))
    if rc_head != 0:
        return {"path": sm_path, "status": "no_head"}

    rc_origin, origin_main = _run(
        ["git", "rev-parse", "origin/main"], str(sm_root)
    )
    if rc_origin != 0:
        return {"path": sm_path, "status": "no_origin_main", "head": head[:9]}

    rc_branch, branch = _run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], str(sm_root)
    )

    aligned = head == origin_main
    ahead = behind = 0
    if not aligned:
        _, ahead_s = _run(
            ["git", "rev-list", "--count", f"origin/main..{head}"], str(sm_root)
        )
        _, behind_s = _run(
            ["git", "rev-list", "--count", f"{head}..origin/main"], str(sm_root)
        )
        ahead = int(ahead_s) if ahead_s.isdigit() else -1
        behind = int(behind_s) if behind_s.isdigit() else -1

    category = "unknown"
    for cat, paths in [
        ("stable", STABLE),
        ("tracking", TRACKING),
        ("feature", FEATURE),
        ("dormant", DORMANT),
    ]:
        if sm_path in paths:
            category = cat
            break
    if category == "unknown" and sm_path in EXTRA:
        category = "stable"

    return {
        "path": sm_path,
        "status": "aligned" if aligned else "drifted",
        "category": category,
        "head": head[:9],
        "origin_main": origin_main[:9],
        "branch": branch if rc_branch == 0 else "?",
        "ahead": ahead,
        "behind": behind,
    }


def main() -> int:
    root = Path(__file__).resolve().parent.parent.parent
    if not (root / ".gitmodules").exists():
        root = Path.cwd()

    submodules = _get_submodules(root)
    if not submodules:
        print("No submodules found")
        return 0

    results = [_check_submodule(root, sm) for sm in submodules]

    drifted_stable = [r for r in results if r.get("category") in ("stable", "tracking") and r.get("status") == "drifted"]
    drifted_feature = [r for r in results if r.get("category") == "feature" and r.get("status") == "drifted"]
    drifted_dormant = [r for r in results if r.get("category") == "dormant" and r.get("status") == "drifted"]

    json_out = "--json" in sys.argv
    if json_out:
        print(json.dumps({
            "total": len(results),
            "aligned": len([r for r in results if r.get("status") == "aligned"]),
            "drifted_stable": len(drifted_stable),
            "drifted_feature": len(drifted_feature),
            "drifted_dormant": len(drifted_dormant),
            "details": results,
        }, indent=2))
    else:
        aligned = [r for r in results if r.get("status") == "aligned"]
        for r in aligned:
            print(f"  ✅ {r['path']:<30s} [{r['category']:<8s}] {r['head']}")
        for r in drifted_stable + drifted_feature + drifted_dormant:
            icon = "❌" if r["category"] in ("stable", "tracking") else "⚠️ "
            print(
                f"  {icon} {r['path']:<30s} [{r['category']:<8s}] "
                f"HEAD={r['head']} origin/main={r['origin_main']} "
                f"ahead={r['ahead']} behind={r['behind']}"
            )
        print(f"\n  {len(aligned)}/{len(results)} aligned")

    if drifted_stable:
        names = ", ".join(r["path"] for r in drifted_stable)
        print(f"\n  FAIL: stable/tracking drift detected: {names}")
        return 1

    if drifted_feature:
        names = ", ".join(r["path"] for r in drifted_feature)
        print(f"\n  WARN: feature drift (non-blocking): {names}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
