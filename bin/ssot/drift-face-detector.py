#!/usr/bin/env python3
"""drift-face-detector.py — 5 类 drift face-wide 检测 (BET-Y2Q4-SH-1).

按 spec docs/superpowers/specs/2026-09-25-self-healing-drifts-foundation.md:
  1. dashboard 漂移: .omo/_control/debt-dashboard/current.yaml age 超过 SLA
  2. brief 漂移: runtime/dashboard/agent-brief.json generated_at 超过 cadence
  3. ephemeral 漂移: docs/reports/* ephemeral 已 completed 但仍顶层
  4. runs 漂移: .omo/_delivery/agent-workflows/runs/* 状态卡 active 但 lock 缺失
  5. ritual 漂移: .omo/state/heartbeats/* weekly 类超过 cadence

所有 detector 都是只读, 不写文件. fix 由 auto-pruner.py 单独跑.

用法:
  uv run python bin/ssot/drift-face-detector.py                  # human 表格输出
  uv run python bin/ssot/drift-face-detector.py --json           # 机器可读
  uv run python bin/ssot/drift-face-detector.py --class dashboard  # 单类
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

# SLA / cadence (来自各 detector 原工具的语义)
DASHBOARD_SLA_HOURS = 336       # 14 天, 与 meta-doctor 同一档
BRIEF_CADENCE_HOURS = 24        # 小时级
RUNS_STALE_HOURS = 48           # active run 缺 lock 超过 48h 即 stale
RITUAL_WEEKLY_DAYS = 14         # weekly 类 ritual SLA

# 类定义
DRIFT_CLASSES = [
    "dashboard",
    "brief",
    "ephemeral",
    "runs",
    "ritual",
]


def _age_hours(iso_ts: str | None) -> float | None:
    """Parse ISO timestamp → age in hours. None when unparseable."""
    if not iso_ts:
        return None
    try:
        # strip trailing Z for fromisoformat compatibility (py<3.11)
        ts = iso_ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - dt).total_seconds() / 3600.0
    except (ValueError, AttributeError):
        return None


def detect_dashboard() -> list[dict]:
    """检查 .omo/_control/debt-dashboard/current.yaml 是否超 SLA."""
    findings: list[dict] = []
    p = WORKSPACE_ROOT / ".omo/_control/debt-dashboard/current.yaml"
    if not p.is_file():
        findings.append({
            "class": "dashboard",
            "id": "DASHBOARD-MISSING",
            "path": str(p.relative_to(WORKSPACE_ROOT)),
            "severity": "high",
            "age_hours": None,
            "sla_hours": DASHBOARD_SLA_HOURS,
            "fix_hint": "run bin/ssot/debt-dashboard-regen.py (TODO: exists?) or manual regen",
        })
        return findings
    text = p.read_text(encoding="utf-8")
    # extract generated_at
    m = re.search(r"generated_at:\s*['\"]?([^'\"\s]+)", text)
    if not m:
        findings.append({
            "class": "dashboard",
            "id": "DASHBOARD-NO-TIMESTAMP",
            "path": str(p.relative_to(WORKSPACE_ROOT)),
            "severity": "medium",
            "age_hours": None,
            "sla_hours": DASHBOARD_SLA_HOURS,
            "fix_hint": "regen — write generated_at field",
        })
        return findings
    age = _age_hours(m.group(1))
    if age is not None and age > DASHBOARD_SLA_HOURS:
        findings.append({
            "class": "dashboard",
            "id": "DASHBOARD-STALE",
            "path": str(p.relative_to(WORKSPACE_ROOT)),
            "severity": "high" if age > DASHBOARD_SLA_HOURS * 2 else "medium",
            "age_hours": round(age, 1),
            "sla_hours": DASHBOARD_SLA_HOURS,
            "fix_hint": "auto-pruner can regen if generator script exists",
        })
    return findings


def detect_brief() -> list[dict]:
    """检查 runtime/dashboard/agent-brief.json 是否超 cadence.

    注: runtime/dashboard/ 是 gitignored (运行时产物). worktree 内通常不存在,
    主仓下 main 分支也不应有 (但 local work dir 或 cron 跑出来的有).
    在 gitignored 情况下 brief "missing" 不是真 drift, 而是未生成 — 跳过.
    """
    findings: list[dict] = []
    p = WORKSPACE_ROOT / "runtime/dashboard/agent-brief.json"
    if not p.is_file():
        # gitignored 不算 drift (运行时不挂 cron 时常见)
        return findings
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        findings.append({
            "class": "brief",
            "id": "BRIEF-MALFORMED",
            "path": str(p.relative_to(WORKSPACE_ROOT)),
            "severity": "medium",
            "age_hours": None,
            "sla_hours": BRIEF_CADENCE_HOURS,
            "fix_hint": "manual inspection — JSON parse error",
            "error": str(e),
        })
        return findings
    ts = data.get("generated_at")
    age = _age_hours(ts)
    if age is not None and age > BRIEF_CADENCE_HOURS:
        findings.append({
            "class": "brief",
            "id": "BRIEF-STALE",
            "path": str(p.relative_to(WORKSPACE_ROOT)),
            "severity": "high" if age > BRIEF_CADENCE_HOURS * 3 else "medium",
            "age_hours": round(age, 1),
            "sla_hours": BRIEF_CADENCE_HOURS,
            "fix_hint": "run bin/panorama/panorama-collect.py",
        })
    return findings


def detect_ephemeral() -> list[dict]:
    """检查 docs/reports/* 中 ephemeral + status:completed 但仍在顶层."""
    findings: list[dict] = []
    p = WORKSPACE_ROOT / "docs/reports"
    if not p.is_dir():
        return findings
    # archived path is exempt
    archive = p / "archive"
    for child in sorted(p.iterdir()):
        if not child.is_file() or not child.name.endswith(".md"):
            continue
        if child.name == "archive" or child.parent == archive:
            continue
        text = child.read_text(encoding="utf-8", errors="ignore")
        # frontmatter
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not m:
            continue
        fm = m.group(1)
        type_match = re.search(r"type:\s*(\S+)", fm)
        status_match = re.search(r"status:\s*(\S+)", fm)
        if not type_match or not status_match:
            continue
        if type_match.group(1) == "ephemeral" and status_match.group(1) in ("completed", "closed"):
            findings.append({
                "class": "ephemeral",
                "id": f"EPHEMERAL-{child.stem}",
                "path": str(child.relative_to(WORKSPACE_ROOT)),
                "severity": "low",
                "age_hours": None,
                "sla_hours": None,
                "fix_hint": "move to docs/reports/archive/ via bin/ssot/doc-lifecycle.py archive",
            })
    return findings


def detect_runs() -> list[dict]:
    """检查 .omo/_delivery/agent-workflows/runs/* 状态为 active 但 lock 文件缺失/超时."""
    findings: list[dict] = []
    runs_dir = WORKSPACE_ROOT / ".omo/_delivery/agent-workflows/runs"
    if not runs_dir.is_dir():
        return findings
    for run_file in sorted(runs_dir.glob("*.yaml")):
        try:
            text = run_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # parse status
        m = re.search(r"^\s*status:\s*(\S+)", text, re.MULTILINE)
        if not m:
            continue
        status = m.group(1)
        if status != "active":
            continue
        # parse updated_at or created_at
        ts_match = re.search(r"^\s*updated_at:\s*['\"]?([^'\"\s]+)", text, re.MULTILINE)
        if not ts_match:
            ts_match = re.search(r"^\s*created_at:\s*['\"]?([^'\"\s]+)", text, re.MULTILINE)
        if not ts_match:
            continue
        age = _age_hours(ts_match.group(1))
        if age is None or age < RUNS_STALE_HOURS:
            continue
        # check lock existence
        lock_dir = WORKSPACE_ROOT / ".omo/_delivery/agent-workflows/locks"
        run_id = run_file.stem
        lock_files = list(lock_dir.glob(f"*.lock.yaml")) if lock_dir.is_dir() else []
        lock_present = any(run_id in lf.read_text(encoding="utf-8", errors="ignore") for lf in lock_files) if lock_files else False
        findings.append({
            "class": "runs",
            "id": f"RUN-STALE-{run_id}",
            "path": str(run_file.relative_to(WORKSPACE_ROOT)),
            "severity": "medium" if not lock_present else "low",
            "age_hours": round(age, 1),
            "sla_hours": RUNS_STALE_HOURS,
            "lock_present": lock_present,
            "fix_hint": "agent-workflow.py prune-locks (TODO) or manual: set status to closed",
        })
    return findings


def detect_ritual() -> list[dict]:
    """检查 .omo/state/heartbeats/* weekly 类 ritual 超过 cadence."""
    findings: list[dict] = []
    p = WORKSPACE_ROOT / ".omo/state/heartbeats"
    if not p.is_dir():
        return findings
    for f in sorted(p.iterdir()):
        if not f.is_file() or not f.name.endswith(".json"):
            continue
        # heuristic: file with "weekly" in name is weekly ritual
        if "weekly" not in f.name:
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        ts = data.get("generated_at")
        age = _age_hours(ts)
        if age is None:
            continue
        age_days = age / 24.0
        if age_days > RITUAL_WEEKLY_DAYS:
            findings.append({
                "class": "ritual",
                "id": f"RITUAL-LAPSED-{f.stem}",
                "path": str(f.relative_to(WORKSPACE_ROOT)),
                "severity": "high" if age_days > RITUAL_WEEKLY_DAYS * 2 else "medium",
                "age_hours": round(age, 1),
                "sla_hours": RITUAL_WEEKLY_DAYS * 24,
                "fix_hint": "owner ritual trigger — not auto-fixable, needs human",
            })
    return findings


DETECTORS = {
    "dashboard": detect_dashboard,
    "brief": detect_brief,
    "ephemeral": detect_ephemeral,
    "runs": detect_runs,
    "ritual": detect_ritual,
}


def detect_all(targets: list[str] | None = None) -> list[dict]:
    """Run detectors. targets=None means all 5 classes."""
    if targets is None:
        targets = DRIFT_CLASSES
    findings: list[dict] = []
    for cls in targets:
        detector = DETECTORS.get(cls)
        if detector:
            findings.extend(detector())
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--class", dest="cls", choices=DRIFT_CLASSES, help="scan only this drift class")
    args = ap.parse_args()
    targets = [args.cls] if args.cls else None
    findings = detect_all(targets)
    if args.json:
        payload = {
            "schema": "drift-face-detector/v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "workspace_root": str(WORKSPACE_ROOT.relative_to(Path("/"))),
            "total": len(findings),
            "by_class": {c: sum(1 for f in findings if f["class"] == c) for c in DRIFT_CLASSES},
            "findings": findings,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"=== drift-face-detector ===")
        print(f"Total: {len(findings)} drift(s)")
        for c in DRIFT_CLASSES:
            count = sum(1 for f in findings if f["class"] == c)
            if count:
                print(f"  {c}: {count}")
        print()
        for f in findings:
            sev = f.get("severity", "?")
            age = f.get("age_hours", "?")
            print(f"  [{sev}] {f['id']}: {f['path']} (age={age}h)")
            print(f"    hint: {f.get('fix_hint', '-')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())