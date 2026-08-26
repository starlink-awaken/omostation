#!/usr/bin/env python3
"""Cell Dashboard — AGE-v2 Agent Cell 监控仪表板.

提供 Cell Pool 实时指标、Episode 执行历史、健康状态的可视化展示.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def get_pool_status() -> dict:
    """获取 Cell Pool 状态."""
    try:
        from omo.resident.cell_pool import CellPool

        pool = CellPool()
        return pool.get_pool_status()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_metrics() -> dict:
    """获取详细指标."""
    try:
        from omo.resident.cell_pool import CellPool

        pool = CellPool()
        return pool.get_metrics()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_health() -> dict:
    """获取全链路健康状态."""
    results = {}
    scripts = [
        (
            "planner",
            "projects/omo/src/omo/resident/planner.py",
            ["--action", "plan", "--intent", "health-check", "--json"],
        ),
        (
            "executor",
            "projects/omo/src/omo/resident/executor.py",
            ["--action", "task", "--task", '{"action":"scan","target":"."}', "--json"],
        ),
        (
            "verifier",
            "projects/omo/src/omo/resident/verifier.py",
            ["--action", "check", "--result", '{"results":[{"ok":true}]}', "--json"],
        ),
        ("governor", "projects/omo/src/omo/resident/governor.py", ["--action", "decide", "--risk", "R0", "--json"]),
    ]
    for name, script, args in scripts:
        try:
            import subprocess

            result = subprocess.run(
                ["python3", str(ROOT / script)] + args,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            results[name] = (
                json.loads(result.stdout)
                if result.returncode == 0
                else {"ok": False, "error": result.stderr.strip()[-200:]}
            )
        except Exception as e:
            results[name] = {"ok": False, "error": str(e)}
    return results


def render_dashboard(status: dict, metrics: dict, health: dict) -> str:
    """渲染仪表板文本."""
    lines = []
    lines.append("=" * 60)
    lines.append("  AGE-v2 Agent Cell Dashboard")
    lines.append("=" * 60)

    # Pool Status
    lines.append("")
    lines.append("── Cell Pool ──")
    if status.get("total_cells") is not None:
        lines.append(
            f"  Cells: {status['total_cells']}/{status.get('max_cells', '?')} (min: {status.get('min_cells', '?')})"
        )
        lines.append(f"  Active Episodes: {status.get('active_episodes', 0)}")
        lines.append(f"  Utilization: {status.get('utilization', 0) * 100:.0f}%")
        lines.append(f"  Auto-scale: {'ON' if status.get('auto_scale') else 'OFF'}")
        states = status.get("state_distribution", {})
        if states:
            lines.append(f"  States: {', '.join(f'{k}:{v}' for k, v in states.items())}")
    else:
        lines.append(f"  Error: {status.get('error', 'unknown')}")

    # Metrics
    if metrics.get("pool"):
        lines.append("")
        lines.append("── Metrics ──")
        pool = metrics["pool"]
        lines.append(f"  Utilization: {pool.get('utilization', 0) * 100:.0f}%")
        dispatch = metrics.get("dispatch", {})
        lines.append(f"  Total Dispatches: {dispatch.get('total_dispatches', 0)}")
        lines.append(f"  Last 1h: {dispatch.get('recent_1h', 0)}")

    # Health
    lines.append("")
    lines.append("── Health Check ──")
    for name, result in health.items():
        status_icon = "✓" if result.get("ok") or result.get("state") else "✗"
        lines.append(f"  {status_icon} {name}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="AGE-v2 Cell Dashboard")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    status = get_pool_status()
    metrics = get_metrics()
    health = get_health()

    if args.json:
        print(
            json.dumps(
                {
                    "status": status,
                    "metrics": metrics,
                    "health": health,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(render_dashboard(status, metrics, health))

    return 0


if __name__ == "__main__":
    sys.exit(main())
