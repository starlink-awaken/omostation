#!/usr/bin/env python3
"""weekly-review.py — 主人必读周报卡片.

聚合四源生成一张主人必读卡:
  - UHS/健康: subprocess 调用 unified-health-score.py (存在时)
  - 价值: 调 north-star-weekly.py --json 取 trend 与 readiness
  - 债务: 扫 .omo/debt/items/*.yaml 统计 open/proposed 计数 + MDEAD 提案标题
  - 决策: import generate-brief 的 scan_decision_inbox

输出三模式:
  --json        机器可读 JSON
  --card        终端富文本卡 (rich 可选, plain 兜底)
  --post-inbox  写入 .omo/_control/cockpit-inbox/weekly-review-latest.json 并打印路径

每次运行末尾写心跳: .omo/state/heartbeats/weekly-review.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
HEARTBEAT_DIR = WORKSPACE / ".omo" / "state" / "heartbeats"
HEARTBEAT_FILE = HEARTBEAT_DIR / "weekly-review.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _import_by_path(path: Path, module_name: str):
    """Import a Python file by path (handles hyphenated filenames)."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── Source 1: Health ──────────────────────────────────────────────────────────

def fetch_health(ws: Path) -> dict:
    """Fetch UHS health score via subprocess. Returns {'score': int|str}."""
    uhs_path = ws / "bin" / "gac" / "unified-health-score.py"
    if not uhs_path.is_file():
        return {"score": "n/a"}
    try:
        r = subprocess.run(
            ["python3", str(uhs_path), "--json"],
            cwd=ws, capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            data = json.loads(r.stdout)
            return {"score": data.get("uhs", data.get("score", data.get("health_score", "n/a")))}
    except Exception:
        pass
    return {"score": "n/a"}


# ── Source 2: Value (North Star) ──────────────────────────────────────────────

def fetch_value(ws: Path) -> dict:
    """Fetch North Star weekly value metrics via subprocess."""
    meter_path = ws / "bin" / "bc-os" / "north_star_meter_v2.py"
    ns_path = ws / "bin" / "ssot" / "north-star-weekly.py"
    if meter_path.is_file():
        import os
        principal = os.environ.get("OMO_PRINCIPAL_ID", "xiamingxing")
        try:
            r = subprocess.run(
                ["python3", str(meter_path), "--json", "--principal-id", principal],
                cwd=ws, capture_output=True, text=True, timeout=60,
            )
            if r.returncode == 0:
                data = json.loads(r.stdout)
                return {
                    "readiness": data.get("status") or data.get("readiness", "unknown"),
                    "total_episodes": data.get("total_episodes", 0),
                    "progress_pct": data.get("progress_pct", 0),
                    "four_week_value_gate": data.get("four_week_value_gate", "unknown"),
                }
        except Exception:
            pass
    # fallback to north-star-weekly
    ns_path = ws / "bin" / "ssot" / "north-star-weekly.py"
    if ns_path.is_file():
        try:
            r = subprocess.run(
                ["python3", str(ns_path), "--json"],
                cwd=ws, capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                data = json.loads(r.stdout)
                return {
                    "readiness": data.get("readiness", "unknown"),
                    "total_episodes": data.get("total_episodes", 0),
                    "progress_pct": data.get("progress_pct", 0),
                }
        except Exception:
            pass
    return {"readiness": "unknown", "error": "no source available"}


# ── Source 3: Debt ────────────────────────────────────────────────────────────

def scan_debt_counts(ws: Path) -> dict:
    """Scan .omo/debt/items/*.yaml for open/proposed counts and MDEAD titles."""
    import yaml

    items_dir = ws / ".omo" / "debt" / "items"
    result = {"open_count": 0, "proposed_count": 0, "total": 0, "mdead_titles": []}

    if not items_dir.is_dir():
        return result

    for p in sorted(items_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        state = str(data.get("lifecycle_state", "")).lower()
        if state == "open":
            result["open_count"] += 1
        elif state == "proposed":
            result["proposed_count"] += 1
        # Collect MDEAD titles regardless of state
        item_id = str(data.get("id", ""))
        if item_id.startswith("MDEAD"):
            title = data.get("title") or data.get("desc") or item_id
            result["mdead_titles"].append(title)

    result["total"] = result["open_count"] + result["proposed_count"]
    return result


# ── Source 4: Decisions ───────────────────────────────────────────────────────

def collect_decisions(ws: Path) -> list[dict]:
    """Collect decision inbox items via generate-brief's scan_decision_inbox."""
    brief_path = ws / "bin" / "mof" / "generate-brief.py"
    if not brief_path.is_file():
        return []
    try:
        mod = _import_by_path(brief_path, "generate_brief")
        return mod.scan_decision_inbox()
    except Exception:
        return []


# ── Aggregation ───────────────────────────────────────────────────────────────

def build_card(ws: Path) -> dict:
    """Aggregate all four sources into a single card dict."""
    return {
        "generated_at": _now_iso(),
        "health": fetch_health(ws),
        "value": fetch_value(ws),
        "debt": scan_debt_counts(ws),
        "decisions": collect_decisions(ws),
    }


# ── Heartbeat ─────────────────────────────────────────────────────────────────

def write_heartbeat(ws: Path) -> None:
    """Write heartbeat to .omo/state/heartbeats/weekly-review.json."""
    hb_dir = ws / ".omo" / "state" / "heartbeats"
    hb_dir.mkdir(parents=True, exist_ok=True)
    hb_file = hb_dir / "weekly-review.json"
    hb_file.write_text(
        json.dumps({"generated_at": _now_iso(), "ok": True}, ensure_ascii=False),
        encoding="utf-8",
    )


# ── Renderers ─────────────────────────────────────────────────────────────────

def render_card_plain(card: dict) -> str:
    """Render card as plain terminal text (fallback when rich unavailable)."""
    lines = []
    lines.append("=" * 60)
    lines.append("  📋 主人必读周报 (Weekly Review)")
    lines.append("=" * 60)
    lines.append(f"  生成时间: {card['generated_at']}")
    lines.append("")

    # Health
    h = card["health"]
    lines.append(f"  🏥 健康分: {h['score']}")
    lines.append("")

    # Value
    v = card["value"]
    lines.append(f"  📈 价值就绪度: {v.get('readiness', '?')}")
    lines.append(f"     总 episodes: {v.get('total_episodes', 0)}")
    lines.append(f"     进度: {v.get('progress_pct', 0)}%")
    lines.append(f"     4周门禁: {v.get('four_week_value_gate', '?')}")
    lines.append("")

    # Debt
    d = card["debt"]
    lines.append(f"  💳 债务: {d['total']} 项 (open={d['open_count']}, proposed={d['proposed_count']})")
    if d["mdead_titles"]:
        lines.append("     MDEAD 提案:")
        for t in d["mdead_titles"]:
            lines.append(f"       - {t}")
    lines.append("")

    # Decisions
    decs = card["decisions"]
    lines.append(f"  📥 待决策: {len(decs)} 项")
    for d_item in decs[:5]:
        lines.append(f"       - [{d_item.get('source', '?')}] {d_item.get('title', '?')}")
    if len(decs) > 5:
        lines.append(f"       ... 及其他 {len(decs) - 5} 项")
    lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def render_card_rich(card: dict) -> str:
    """Render card using rich library (if available)."""
    try:
        from rich.console import Console
        from rich.table import Table
        from io import StringIO

        console = Console(file=StringIO(), width=72)
        console.print("[bold cyan]📋 主人必读周报 (Weekly Review)[/bold cyan]")
        console.print(f"  生成时间: {card['generated_at']}")
        console.print()

        # Health
        h = card["health"]
        score = h["score"]
        color = "green" if isinstance(score, (int, float)) and score >= 90 else "yellow"
        console.print(f"  🏥 健康分: [{color}]{score}[/{color}]")
        console.print()

        # Value
        v = card["value"]
        console.print(f"  📈 价值就绪度: [cyan]{v.get('readiness', '?')}[/cyan]")
        console.print(f"     总 episodes: {v.get('total_episodes', 0)} | 进度: {v.get('progress_pct', 0)}%")
        console.print(f"     4周门禁: {v.get('four_week_value_gate', '?')}")
        console.print()

        # Debt
        d = card["debt"]
        console.print(f"  💳 债务: [yellow]{d['total']}[/yellow] 项 (open={d['open_count']}, proposed={d['proposed_count']})")
        if d["mdead_titles"]:
            for t in d["mdead_titles"]:
                console.print(f"       [red]•[/red] {t}")
        console.print()

        # Decisions
        decs = card["decisions"]
        console.print(f"  📥 待决策: [yellow]{len(decs)}[/yellow] 项")
        for d_item in decs[:5]:
            console.print(f"       [dim]•[/dim] [{d_item.get('source', '?')}] {d_item.get('title', '?')}")
        if len(decs) > 5:
            console.print(f"       [dim]... 及其他 {len(decs) - 5} 项[/dim]")

        return console.file.getvalue()
    except ImportError:
        return render_card_plain(card)


# ── Main ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="JSON 机器输出")
    ap.add_argument("--card", action="store_true", help="终端富文本卡")
    ap.add_argument("--post-inbox", action="store_true",
                    help="写入 cockpit-inbox 并打印路径")
    args = ap.parse_args(argv)

    card = build_card(WORKSPACE)
    write_heartbeat(WORKSPACE)

    if args.json:
        print(json.dumps(card, ensure_ascii=False, indent=2))
    elif args.post_inbox:
        inbox_dir = WORKSPACE / ".omo" / "_control" / "cockpit-inbox"
        inbox_file = inbox_dir / "weekly-review-latest.json"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        inbox_file.write_text(
            json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(str(inbox_file))
    elif args.card:
        print(render_card_rich(card))
    else:
        # Default: card mode
        print(render_card_rich(card))

    return 0


if __name__ == "__main__":
    sys.exit(main())
