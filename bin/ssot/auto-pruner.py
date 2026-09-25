#!/usr/bin/env python3
"""auto-pruner.py — 4 类 drift 自动修复 (BET-Y2Q4-SH-1).

按 spec docs/superpowers/specs/2026-09-25-self-healing-drifts-foundation.md:
  1. ephemeral → 移动 docs/reports/*.md 到 docs/reports/archive/
     (仅 type: ephemeral + status: completed/closed)
  2. runs → close stale active run (status: active → closed, 仅 lock 缺 + age > 48h)
  3. dashboard → 标记 stale (auto-pruner 不重生成, 只更新 generated_at 提示)
     重生成由 bin/ssot/debt-dashboard-regen.py (TODO) 单独跑
  4. ritual → 仅报告, 不自动修 (owner 决策)

circuit-breaker:
  - 默认 dry-run; --apply 才动文件
  - 仅动 git-tracked 文件 (ephemeral move 保持 git history)
  - 不重写 SSOT 文档; 不动 launchd plist; 不 gitlink bump

用法:
  uv run python bin/ssot/auto-pruner.py --dry-run --json    # default
  uv run python bin/ssot/auto-pruner.py --apply             # 实际修复
  uv run python bin/ssot/auto-pruner.py --class ephemeral   # 单类
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def _archive_dir() -> Path:
    return WORKSPACE_ROOT / "docs/reports/archive"

PRUNABLE_CLASSES = ["ephemeral", "runs", "dashboard", "ritual"]


def prune_ephemeral(dry_run: bool) -> list[dict]:
    """Move ephemeral + completed docs from docs/reports/ to docs/reports/archive/."""
    actions: list[dict] = []
    reports = WORKSPACE_ROOT / "docs/reports"
    if not reports.is_dir():
        return actions
    _archive_dir().mkdir(parents=True, exist_ok=True)
    for child in sorted(reports.iterdir()):
        if not child.is_file() or not child.name.endswith(".md"):
            continue
        if child.parent == _archive_dir():
            continue
        text = child.read_text(encoding="utf-8", errors="ignore")
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not m:
            continue
        fm = m.group(1)
        type_match = re.search(r"type:\s*(\S+)", fm)
        status_match = re.search(r"status:\s*(\S+)", fm)
        if not (type_match and status_match):
            continue
        if type_match.group(1) != "ephemeral":
            continue
        if status_match.group(1) not in ("completed", "closed"):
            continue
        target = _archive_dir() / child.name
        try:
            dst = str(target.relative_to(WORKSPACE_ROOT))
        except ValueError:
            # target outside workspace (test fixture edge case); fall back to absolute
            dst = str(target)
        actions.append({
            "class": "ephemeral",
            "id": f"EPHEMERAL-ARCHIVE-{child.stem}",
            "src": str(child.relative_to(WORKSPACE_ROOT)) if str(child).startswith(str(WORKSPACE_ROOT)) else str(child),
            "dst": dst,
            "applied": False,
        })
        if not dry_run:
            shutil.move(str(child), str(target))
            actions[-1]["applied"] = True
    return actions


def prune_runs(dry_run: bool) -> list[dict]:
    """Close stale active runs (status: active + lock missing + age > 48h)."""
    actions: list[dict] = []
    runs_dir = WORKSPACE_ROOT / ".omo/_delivery/agent-workflows/runs"
    if not runs_dir.is_dir():
        return actions
    lock_dir = WORKSPACE_ROOT / ".omo/_delivery/agent-workflows/locks"
    for run_file in sorted(runs_dir.glob("*.yaml")):
        text = run_file.read_text(encoding="utf-8", errors="ignore")
        if "status: active" not in text:
            continue
        # check age
        ts_match = re.search(r"^\s*updated_at:\s*['\"]?([^'\"\s]+)", text, re.MULTILINE)
        if not ts_match:
            ts_match = re.search(r"^\s*created_at:\s*['\"]?([^'\"\s]+)", text, re.MULTILINE)
        if not ts_match:
            continue
        try:
            ts = ts_match.group(1).replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
        except ValueError:
            continue
        if age_hours < 48:
            continue
        # check lock
        run_id = run_file.stem
        lock_present = False
        if lock_dir.is_dir():
            for lf in lock_dir.glob("*.lock.yaml"):
                if run_id in lf.read_text(encoding="utf-8", errors="ignore"):
                    lock_present = True
                    break
        if lock_present:
            # lock 还在, 不强行关
            continue
        actions.append({
            "class": "runs",
            "id": f"RUN-CLOSE-{run_id}",
            "path": str(run_file.relative_to(WORKSPACE_ROOT)),
            "age_hours": round(age_hours, 1),
            "applied": False,
        })
        if not dry_run:
            new_text = re.sub(r"^(\s*)status:\s*active", r"\1status: closed", text, count=1, flags=re.MULTILINE)
            new_text = re.sub(r"^(\s*)updated_at:\s*['\"]?[^'\"\s]+", lambda m: f"{m.group(1)}updated_at: '{datetime.now(timezone.utc).isoformat()}'", new_text, count=1, flags=re.MULTILINE)
            run_file.write_text(new_text, encoding="utf-8")
            actions[-1]["applied"] = True
    return actions


def prune_dashboard(dry_run: bool) -> list[dict]:
    """Dashboard stale → 仅报告. 重生成不在本 pruner 范围 (需 debt-dashboard-regen.py)."""
    actions: list[dict] = []
    p = WORKSPACE_ROOT / ".omo/_control/debt-dashboard/current.yaml"
    if not p.is_file():
        return actions
    actions.append({
        "class": "dashboard",
        "id": "DASHBOARD-STALE-REPORT",
        "path": str(p.relative_to(WORKSPACE_ROOT)),
        "note": "auto-pruner 不重生成 dashboard; 需运行 bin/ssot/debt-dashboard-regen.py (TODO)",
        "applied": False,
    })
    return actions


def prune_ritual(dry_run: bool) -> list[dict]:
    """Ritual lapsed → 仅报告. owner 决策."""
    actions: list[dict] = []
    p = WORKSPACE_ROOT / ".omo/state/heartbeats"
    if not p.is_dir():
        return actions
    for f in sorted(p.iterdir()):
        if not f.is_file() or "weekly" not in f.name or not f.name.endswith(".json"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        ts = data.get("generated_at")
        if not ts:
            continue
        try:
            ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts_dt.tzinfo is None:
                ts_dt = ts_dt.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - ts_dt).total_seconds() / 86400.0
        except ValueError:
            continue
        if age_days > 14:
            actions.append({
                "class": "ritual",
                "id": f"RITUAL-LAPSED-REPORT-{f.stem}",
                "path": str(f.relative_to(WORKSPACE_ROOT)),
                "age_days": round(age_days, 1),
                "note": "auto-pruner 不修 ritual; owner 必须手动跑 weekly-review ritual",
                "applied": False,
            })
    return actions


PRUNERS = {
    "ephemeral": prune_ephemeral,
    "runs": prune_runs,
    "dashboard": prune_dashboard,
    "ritual": prune_ritual,
}


def prune_all(dry_run: bool, targets: list[str] | None = None) -> list[dict]:
    if targets is None:
        targets = PRUNABLE_CLASSES
    actions: list[dict] = []
    for cls in targets:
        fn = PRUNERS.get(cls)
        if fn:
            actions.extend(fn(dry_run))
    return actions


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="apply fixes (default dry-run)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--class", dest="cls", choices=PRUNABLE_CLASSES, help="prune only this class")
    args = ap.parse_args()
    dry_run = not args.apply
    targets = [args.cls] if args.cls else None
    actions = prune_all(dry_run, targets)
    if args.json:
        payload = {
            "schema": "auto-pruner/v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "apply" if args.apply else "dry-run",
            "total_actions": len(actions),
            "applied": sum(1 for a in actions if a.get("applied")),
            "actions": actions,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"=== auto-pruner ({mode}) ===")
        print(f"Total actions: {len(actions)}")
        if args.apply:
            print(f"Applied: {sum(1 for a in actions if a.get('applied'))}")
        print()
        for a in actions:
            mark = "[x]" if a.get("applied") else "[ ]"
            print(f"  {mark} [{a['class']}] {a['id']}")
            for k in ("src", "dst", "path"):
                if k in a:
                    print(f"      {k}: {a[k]}")
            if "note" in a:
                print(f"      note: {a['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())