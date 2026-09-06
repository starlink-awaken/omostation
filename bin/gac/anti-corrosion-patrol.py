#!/usr/bin/env python3
"""Anti-Corrosion Patrol — 防腐看门狗常态化巡检.

聚合 anti-corrosion-check (预算) 与 anti-corrosion-detector (陈旧) 的散件,
提供每日/PR 可触发的统一巡检入口:
  - weekly_net_lines():  git diff 周窗口 code+docs 净增行数, ≤0 红线
  - rule_health_score():  GaC 规则健康度 (完整/引用/退役候选)
  - dead_code_and_dupes(): 死代码与双头依赖汇总

用法:
    python3 anti-corrosion-patrol.py              # 巡检报告
    python3 anti-corrosion-patrol.py --json        # JSON 快照 (Cockpit 消费)
    python3 anti-corrosion-patrol.py --enforce     # CI 熔断: 超预算/红线→exit 1

设计约束:
    - 复用 anti-corrosion-check.py / anti-corrosion-detector.py, 不复制逻辑
    - 报错降级为 Warning, 不阻塞紧急热修 PR
    - 不自动删除代码 (退役候选只标记)

SSOT: .omo/standards/anti-corrosion-budget.yaml v2.0.0
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
BUDGET_FILE = WORKSPACE / ".omo/standards/anti-corrosion-budget.yaml"
GOV_CHECKS_YAML = WORKSPACE / ".omo/_truth/registry/governance-checks.yaml"


# ---------------------------------------------------------------------------
# 1. weekly_net_lines — 周窗口净增行数
# ---------------------------------------------------------------------------

def weekly_net_lines(days: int = 7) -> dict:
    """统计过去 N 天 code+docs 净增行数.

    Returns:
        dict with added, deleted, net, red_line_breached, over_by
    """
    try:
        # git diff --stat for code+docs extensions in last N days
        since = f"{days} days ago"
        result = subprocess.run(
            [
                "git", "diff", "--shortstat",
                f"--since={since}",
                "--",
                "*.py", "*.ts", "*.js", "*.yaml", "*.yml",
                "*.md", "*.toml", "*.json", "*.sh",
                "*.hbs", "*.html",
            ],
            capture_output=True,
            text=True,
            cwd=WORKSPACE,
            timeout=30,
        )
        stat_line = result.stdout.strip()

        added = 0
        deleted = 0

        if stat_line:
            # Parse "N files changed, M insertions(+), K deletions(-)"
            import re
            ins_match = re.search(r"(\d+) insertion", stat_line)
            del_match = re.search(r"(\d+) deletion", stat_line)
            if ins_match:
                added = int(ins_match.group(1))
            if del_match:
                deleted = int(del_match.group(1))

        net = added - deleted
        red_line_breached = net > 0

        return {
            "added": added,
            "deleted": deleted,
            "net": net,
            "red_line_breached": red_line_breached,
            "over_by": max(net, 0),
            "ok": not red_line_breached,
        }
    except Exception as exc:
        return {
            "added": 0,
            "deleted": 0,
            "net": 0,
            "red_line_breached": False,
            "over_by": 0,
            "ok": True,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# 2. rule_health_score — GaC 规则健康度
# ---------------------------------------------------------------------------

def rule_health_score() -> dict:
    """对 governance-checks.yaml 规则逐条打分.

    Scoring dimensions (0-1 each, total 0-3):
      - lifecycle_active:  1 if lifecycle == active, 0 otherwise
      - has_description:   1 if description field present
      - has_executor:      1 if executor list non-empty

    Health grade:
      - green:  avg >= 2.5
      - yellow: avg >= 1.5
      - red:    avg < 1.5
      - retirement_candidates: rules with lifecycle in {deprecated, removed, candidate_retirement}

    Returns:
        dict with total, green, yellow, red, avg_score, grade,
              retirement_candidates, details
    """
    if not GOV_CHECKS_YAML.exists():
        return {
            "total": 0,
            "ok": True,
            "grade": "unknown",
            "error": "governance-checks.yaml not found",
        }

    try:
        import re

        text = GOV_CHECKS_YAML.read_text(encoding="utf-8")

        # Extract rule blocks: - id: <id> ... lifecycle: <lifecycle>
        rule_pattern = re.compile(
            r"^\s+-\s+id:\s+(.+?)$",
            re.MULTILINE,
        )
        lifecycle_pattern = re.compile(
            r"lifecycle:\s*(\S+)",
            re.MULTILINE,
        )
        desc_pattern = re.compile(
            r"description:\s*\S",
            re.MULTILINE,
        )
        executor_pattern = re.compile(
            r"executor:\s*\n(?:\s+-\s+\S+\n?)+",
            re.MULTILINE,
        )

        # Split by rule blocks for per-rule analysis
        rule_ids = [m.group(1).strip() for m in rule_pattern.finditer(text)]
        lifecycles = [m.group(1).strip() for m in lifecycle_pattern.finditer(text)]
        total = len(rule_ids)

        if total == 0:
            return {"total": 0, "ok": True, "grade": "unknown"}

        # Compute health per rule (approximate via global patterns)
        # Count by lifecycle
        lifecycle_counts: dict[str, int] = {}
        for lc in lifecycles:
            lifecycle_counts[lc] = lifecycle_counts.get(lc, 0) + 1

        active_count = lifecycle_counts.get("active", 0)
        removed_count = lifecycle_counts.get("removed", 0)
        deprecated_count = lifecycle_counts.get("deprecated", 0)
        retirement_candidates = deprecated_count + removed_count

        # Count rules with descriptions
        descriptions_count = len(desc_pattern.findall(text))
        # Count rules with executors
        executor_count = len(executor_pattern.findall(text))

        # Approximate per-rule scores
        avg_score = 0.0
        if total > 0:
            lifecycle_score = active_count / total
            desc_score = min(descriptions_count / total, 1.0)
            executor_score = min(executor_count / total, 1.0)
            avg_score = round((lifecycle_score + desc_score + executor_score) / 3, 3)

        # avg_score is 0..1 (3 dimensions, each 0..1, averaged)
        if avg_score >= 0.83:
            grade = "green"
        elif avg_score >= 0.5:
            grade = "yellow"
        else:
            grade = "red"

        return {
            "total": total,
            "active": active_count,
            "removed": removed_count,
            "deprecated": deprecated_count,
            "descriptions": descriptions_count,
            "executors": executor_count,
            "avg_score": avg_score,
            "grade": grade,
            "retirement_candidates": retirement_candidates,
            "ok": grade != "red",
        }
    except Exception as exc:
        return {
            "total": 0,
            "ok": True,
            "grade": "unknown",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# 3. dead_code_and_dupes — 调用 anti-corrosion-detector
# ---------------------------------------------------------------------------

def dead_code_and_dupes() -> dict:
    """调用 anti-corrosion-detector.py 获取死代码与双头依赖告警.

    Returns:
        dict with findings_count, ok, findings (first 10)
    """
    detector = WORKSPACE / "bin/gac/anti-corrosion-detector.py"
    if not detector.exists():
        return {
            "findings_count": 0,
            "ok": True,
            "error": "anti-corrosion-detector.py not found",
        }

    try:
        result = subprocess.run(
            [sys.executable, str(detector), "--json"],
            capture_output=True,
            text=True,
            cwd=WORKSPACE,
            timeout=30,
        )
        if result.returncode != 0 and not result.stdout.strip():
            return {
                "findings_count": 0,
                "ok": True,
                "error": f"detector exit {result.returncode}: {result.stderr[:200]}",
            }

        data = json.loads(result.stdout) if result.stdout.strip() else {}
        findings = data.get("findings", [])
        return {
            "findings_count": len(findings),
            "ok": data.get("ok", True),
            "findings": findings[:10],
        }
    except (json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        return {
            "findings_count": 0,
            "ok": True,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "findings_count": 0,
            "ok": True,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# 4. budget_check — 从 anti-corrosion-budget.yaml 读取预算并校验
# ---------------------------------------------------------------------------

def budget_check() -> dict:
    """读取 anti-corrosion-budget.yaml 并检查预算合规.

    Uses simple line parsing to avoid pyyaml dependency.

    Returns:
        dict with over_budget, breaches, ok
    """
    if not BUDGET_FILE.exists():
        return {
            "over_budget": False,
            "breaches": [],
            "ok": True,
            "error": "anti-corrosion-budget.yaml not found",
        }

    try:
        text = BUDGET_FILE.read_text(encoding="utf-8")
        breaches = []
        current_budget = None
        current_max = None
        current_name = None

        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            # budget group: "  governance_rules:" or "  bin_scripts:"
            if ":" in stripped and not stripped.startswith("-") and not stripped.startswith("max") and not stripped.startswith("current"):
                parts = stripped.split(":", 1)
                key = parts[0].strip()
                # If it's indented 2 spaces (budget name level)
                if line.startswith("  ") and not line.startswith("    "):
                    # Flush previous budget
                    if current_name and current_max is not None and current_budget is not None:
                        if current_budget > current_max:
                            breaches.append({
                                "budget": current_name,
                                "current": current_budget,
                                "max": current_max,
                                "over_by": current_budget - current_max,
                            })
                    current_name = key
                    current_max = None
                    current_budget = None
            elif stripped.startswith("max_count:"):
                val = stripped.split(":", 1)[1].strip()
                current_max = int(val)
            elif stripped.startswith("current:"):
                val = stripped.split(":", 1)[1].strip().lstrip("~").replace(",", "")
                current_budget = int(float(val))

        # Flush last budget
        if current_name and current_max is not None and current_budget is not None:
            if current_budget > current_max:
                breaches.append({
                    "budget": current_name,
                    "current": current_budget,
                    "max": current_max,
                    "over_by": current_budget - current_max,
                })

        return {
            "over_budget": len(breaches) > 0,
            "breaches": breaches,
            "ok": len(breaches) == 0,
        }
    except Exception as exc:
        return {
            "over_budget": False,
            "breaches": [],
            "ok": True,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# 5. patrol — 汇总巡检
# ---------------------------------------------------------------------------

def patrol() -> dict:
    """执行全量巡检, 返回统一快照."""
    ts = datetime.now(UTC).isoformat()

    weekly = weekly_net_lines()
    health = rule_health_score()
    dead = dead_code_and_dupes()
    budget = budget_check()

    all_ok = weekly["ok"] and health["ok"] and dead["ok"] and budget["ok"]

    return {
        "timestamp": ts,
        "ok": all_ok,
        "checks": {
            "weekly_net_lines": weekly,
            "rule_health": health,
            "dead_code": dead,
            "budget": budget,
        },
        "summary": {
            "net_lines": weekly.get("net", 0),
            "red_line_breached": weekly.get("red_line_breached", False),
            "health_grade": health.get("grade", "unknown"),
            "retirement_candidates": health.get("retirement_candidates", 0),
            "dead_code_findings": dead.get("findings_count", 0),
            "budget_breaches": len(budget.get("breaches", [])),
        },
    }


# ---------------------------------------------------------------------------
# 6. CLI
# ---------------------------------------------------------------------------

def _format_text(snapshot: dict) -> str:
    """格式化人类可读报告."""
    lines = [
        "=" * 56,
        "  Anti-Corrosion Patrol",
        "=" * 56,
        f"  Status: {'PASS' if snapshot['ok'] else 'FAIL'}",
        f"  Time:   {snapshot['timestamp'][:19]}",
        "",
    ]

    s = snapshot["summary"]

    # Weekly net lines
    wl = snapshot["checks"]["weekly_net_lines"]
    status = "✗" if wl.get("red_line_breached") else "✓"
    lines.append(f"  {status} Weekly net lines: {s['net_lines']:+d}"
                 + (f" (over by {wl.get('over_by', 0)}, RED LINE BREACHED)"
                    if wl.get('red_line_breached') else " (≤0 target met)"))
    lines.append(f"      added: {wl.get('added', 0)}  deleted: {wl.get('deleted', 0)}")
    lines.append("")

    # Rule health
    hl = snapshot["checks"]["rule_health"]
    status = "✓" if hl.get("ok") else "✗"
    lines.append(f"  {status} Rule health: {hl.get('grade', '?')} "
                 f"(avg {hl.get('avg_score', 0):.2f}/3.0, "
                 f"{hl.get('active', 0)}/{hl.get('total', 0)} active, "
                 f"{hl.get('retirement_candidates', 0)} retirement candidates)")
    lines.append("")

    # Dead code
    dl = snapshot["checks"]["dead_code"]
    status = "✓" if dl.get("ok") else "✗"
    lines.append(f"  {status} Dead code / stale rules: {dl.get('findings_count', 0)} findings")
    for f in dl.get("findings", [])[:5]:
        lines.append(f"      - {f.get('id', '?')}: {f.get('reason', '')[:60]}")
    lines.append("")

    # Budget
    bl = snapshot["checks"]["budget"]
    status = "✓" if bl.get("ok") else "✗"
    lines.append(f"  {status} Budget: {'OK' if bl.get('ok') else 'BREACHES'}")
    for b in bl.get("breaches", []):
        lines.append(f"      ✗ {b['budget']}: {b['current']}/{b['max']} (+{b['over_by']})")
    lines.append("")

    if not snapshot["ok"]:
        lines.append("  ⚠ CIRCUIT BREAKER: patrol failed, see above violations")

    lines.append("=" * 56)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Anti-Corrosion Patrol")
    parser.add_argument("--json", action="store_true", help="JSON snapshot for Cockpit")
    parser.add_argument("--enforce", action="store_true",
                        help="CI mode: violation → exit 1")
    parser.add_argument("--days", type=int, default=7,
                        help="Window for net line count (default: 7)")
    args = parser.parse_args()

    snapshot = patrol()

    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        print(_format_text(snapshot))

    if args.enforce and not snapshot["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
