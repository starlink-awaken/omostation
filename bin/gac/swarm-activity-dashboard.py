#!/usr/bin/env python3
"""swarm-activity-dashboard — 多 agent 实时活动监控面板.

聚合分散的 agent 活动数据源, 输出"当前谁在干什么"的实时视图:

- active runs        (agent-workflow status: 运行中的 workflow + objective)
- locks              (谁占用了哪些路径/scope)
- worktree           (per-session 隔离工作区)
- branch/adr claims  (D1/D2 占位)
- submodule dirty    (各子模块未提交改动 → 判断 agent 工作范围)
- swarm 冲突         (unclaimed_write 事件, ADR-0220 冲突观测)

数据源:
  .omo/_delivery/agent-workflows/{runs,locks,events.jsonl}
  .omo/_delivery/{branch-claims,adr-claims}
  git worktree list / git -C projects/* status

使用:
  python3 bin/gac/swarm-activity-dashboard.py
  python3 bin/gac/swarm-activity-dashboard.py --json
  python3 bin/gac/swarm-activity-dashboard.py --watch 10   # 每 10s 刷新
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
RUNS_DIR = WORKSPACE / ".omo/_delivery/agent-workflows/runs"
LOCKS_DIR = WORKSPACE / ".omo/_delivery/agent-workflows/locks"
EVENTS_LOG = WORKSPACE / ".omo/_delivery/agent-workflows/events.jsonl"
BRANCH_CLAIMS = WORKSPACE / ".omo/_delivery/branch-claims"
ADR_CLAIMS = WORKSPACE / ".omo/_delivery/adr-claims"
CONFLICT_LOG = WORKSPACE / ".omo/_delivery/swarm-conflicts/events.jsonl"
SUBMODULES = [
    "agora", "kairon", "cockpit", "gbrain", "omo", "ecos", "metaos",
    "runtime", "c2g", "model-driven", "l4-kernel", "cockpit-ui",
    "family-hub", "aetherforge", "bus-foundation", "observability",
    "omo-debt",
]


def _read_run(run_id: str) -> dict:
    """Read run yaml fields (objective/status/agent/updated_at)."""
    path = RUNS_DIR / f"{run_id}.yaml"
    if not path.is_file():
        return {}
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError):
        return {}
    return {
        "run_id": run_id,
        "objective": str(data.get("objective") or ""),
        "status": str(data.get("status") or ""),
        "actor": str(data.get("actor") or ""),
        "profile": str(data.get("agent_profile") or ""),
        "updated_at": str(data.get("updated_at") or ""),
        "created_at": str(data.get("created_at") or ""),
    }


def _active_runs() -> list[dict]:
    """active runs via agent-workflow status --json."""
    try:
        out = subprocess.run(
            ["uv", "run", "--with", "pyyaml", "python",
             str(WORKSPACE / "bin/agent-workflow.py"), "status", "--json"],
            cwd=WORKSPACE, capture_output=True, text=True, timeout=60,
            check=False,
        ).stdout
        import json as _json

        data = _json.loads(out)
        return [_read_run(r) for r in data.get("active_runs", [])]
    except (subprocess.SubprocessError, json.JSONDecodeError, ValueError) as exc:
        return [{"error": str(exc)}]


def _locks() -> list[dict]:
    """Parse lock files: scope → run_id + expires_at."""
    locks = []
    if not LOCKS_DIR.is_dir():
        return locks
    try:
        import yaml
    except ImportError:
        return locks
    for f in sorted(LOCKS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except (yaml.YAMLError, OSError):
            continue
        locks.append({
            "file": f.name,
            "scope": str(data.get("scope") or f.stem),
            "run_id": str(data.get("run_id") or ""),
            "actor": str(data.get("actor") or ""),
            "expires_at": str(data.get("expires_at") or ""),
        })
    return locks


def _worktrees() -> list[dict]:
    out = subprocess.run(
        ["git", "worktree", "list"], cwd=WORKSPACE,
        capture_output=True, text=True, timeout=30,
        check=False,
    ).stdout
    rows = []
    for line in out.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2:
            rows.append({"path": parts[0], "ref": parts[1],
                         "branch": parts[2] if len(parts) > 2 else ""})
    return rows


def _claims(dir_path: Path) -> list[str]:
    if not dir_path.is_dir():
        return []
    return sorted(f.stem for f in dir_path.glob("*.json"))


def _submodule_dirty() -> list[dict]:
    dirty = []
    for sub in SUBMODULES:
        p = WORKSPACE / "projects" / sub
        if not (p / ".git").exists():
            continue
        out = subprocess.run(
            ["git", "status", "--porcelain"], cwd=p,
            capture_output=True, text=True, timeout=15,
            check=False,
        ).stdout
        count = len([line for line in out.splitlines() if line.strip()])
        if count:
            dirty.append({"submodule": sub, "dirty_count": count})
    return dirty


def _conflicts(since_hours: int = 24) -> list[dict]:
    conflicts = []
    if not CONFLICT_LOG.is_file():
        return conflicts
    cutoff = datetime.now(UTC) - timedelta(hours=since_hours)
    for line in CONFLICT_LOG.read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(line)
            ts = ev.get("ts", "")
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt < cutoff:
                    continue
            except ValueError:
                pass
            detail = ev.get("detail") or {}
            conflicts.append({
                "ts": ts,
                "kind": ev.get("kind", ""),
                "branch": detail.get("branch", ""),
                "paths": detail.get("paths", [])[:3],
            })
        except (json.JSONDecodeError, ValueError):
            continue
    return conflicts


def _recent_events(hours: int = 1) -> int:
    if not EVENTS_LOG.is_file():
        return 0
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    count = 0
    for line in EVENTS_LOG.read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(line)
            dt = datetime.fromisoformat(ev.get("ts", "").replace("Z", "+00:00"))
            if dt >= cutoff:
                count += 1
        except (json.JSONDecodeError, ValueError):
            continue
    return count


def build_report() -> dict:
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "active_runs": _active_runs(),
        "locks": _locks(),
        "worktrees": _worktrees(),
        "branch_claims": _claims(BRANCH_CLAIMS),
        "adr_claims": _claims(ADR_CLAIMS),
        "submodule_dirty": _submodule_dirty(),
        "conflicts_24h": _conflicts(24),
        "events_1h": _recent_events(1),
    }
    return report


def print_text(report: dict) -> None:
    print("=" * 68)
    print("🤖 Swarm Activity Dashboard")
    print(f"   生成: {report['generated_at'][:19]} | 事件(1h): {report['events_1h']}")
    print("=" * 68)

    runs = [r for r in report["active_runs"] if not r.get("error")]
    print(f"\n▶ Active runs ({len(runs)}):")
    for r in runs:
        obj = r.get("objective", "")[:70]
        print(f"  🔄 {r.get('run_id','')[:40]}")
        print(f"     {r.get('profile',''):12s} {obj}")
    for r in report["active_runs"]:
        if r.get("error"):
            print(f"  ⚠️  run 查询失败: {r['error']}")

    locks = report["locks"]
    print(f"\n🔒 Locks ({len(locks)}):")
    by_run: dict[str, list[str]] = {}
    for lk in locks:
        by_run.setdefault(lk["run_id"] or "?", []).append(lk["scope"])
    for run_id, scopes in sorted(by_run.items()):
        print(f"  {run_id[:40]:42s} {len(scopes)} scopes: {', '.join(scopes[:4])}{'...' if len(scopes)>4 else ''}")

    wts = report["worktrees"]
    print(f"\n📁 Worktrees ({len(wts)}):")
    for wt in wts:
        marker = " ← 主工作区" if wt["path"] == str(WORKSPACE) else ""
        print(f"  {wt['path'].replace(str(WORKSPACE.parent), '~'):48s} {wt.get('branch','')}{marker}")

    print(f"\n🎫 Claims: branch={len(report['branch_claims'])} adr={len(report['adr_claims'])}")
    if report["branch_claims"]:
        print(f"  branch: {', '.join(report['branch_claims'][:8])}")
    if report["adr_claims"]:
        print(f"  adr:    {', '.join(report['adr_claims'][:8])}")

    dirty = report["submodule_dirty"]
    print(f"\n📦 Submodule dirty ({len(dirty)}):")
    if dirty:
        for d in dirty:
            print(f"  {d['submodule']:20s} {d['dirty_count']} files")
    else:
        print("   (全部干净)")

    conf = report["conflicts_24h"]
    print(f"\n🚨 Swarm conflicts (24h): {len(conf)}")
    for c in conf[:5]:
        print(f"  {c['ts'][:19]} [{c['kind']}] {c.get('branch','')}: {', '.join(c['paths'][:2])}")
    print("=" * 68)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--watch", type=int, default=0,
                        help="每隔 N 秒刷新 (0=单次)")
    args = parser.parse_args()

    if args.watch:
        import time

        while True:
            os.system("clear")
            report = build_report()
            print_text(report)
            time.sleep(args.watch)
        return 0

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
