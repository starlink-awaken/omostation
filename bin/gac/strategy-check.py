#!/usr/bin/env python3
"""strategy-check: 9 维战略一致性矩阵验证器 (project-strategy-v1 §10 落地)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

WS_ROOT = Path(__file__).resolve().parent.parent.parent
SCENES_DIR = WS_ROOT / "docs" / "scene-cards"
JOURNEYS_DIR = WS_ROOT / "docs" / "journey-specs"


def _run(cmd: list[str], cwd: Path = WS_ROOT, timeout: int = 30) -> tuple[int, str, str]:
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout)
        return res.returncode, (res.stdout or ""), (res.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, "", f"subprocess error: {e}"


def _scene_lifecycle_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    if not SCENES_DIR.is_dir():
        return counts
    for p in SCENES_DIR.glob("*.yaml"):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r"^lifecycle:\s*(\w+)\s*$", text, re.MULTILINE)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def _maturity_overall() -> float | None:
    rc, out, _ = _run([sys.executable, str(WS_ROOT / "bin" / "gac" / "maturity-scorecard.py"), "--json"], timeout=180)
    if rc != 0:
        return None
    try:
        data = json.loads(out)
        return float(data.get("overall"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _journey_status_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    if not JOURNEYS_DIR.is_dir():
        return counts
    for p in JOURNEYS_DIR.glob("*.yaml"):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r"^status:\s*(\w+)\s*$", text, re.MULTILINE)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def _bcos_north_star_status() -> dict:
    """BCOS north_star status — includes 3-axis BC + 4-axis advisory (D axis)."""
    rc, out, _ = _run([sys.executable, str(WS_ROOT / "bin" / "bc-os" / "north_star_meter_v3.py"), "--json"])
    if rc != 0:
        return {"status": "unavailable", "composite": None, "composite_4axis": None, "axes": None}
    try:
        data = json.loads(out)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"status": "unknown", "composite": None, "composite_4axis": None, "axes": None}
    composite = (data.get("composite") or {}).get("score")
    composite_4axis = (data.get("composite_4axis") or {}).get("score")
    axes = data.get("axes") or {}
    return {
        "status": str(data.get("status") or "unknown"),
        "composite": composite,
        "composite_4axis": composite_4axis,
        "axes": {k: v.get("score") for k, v in axes.items() if isinstance(v, dict)},
    }


def _compass_health() -> dict[str, Any]:
    rc, out, _ = _run([sys.executable, str(WS_ROOT / "bin" / "compass_radar.py"), "--dry-run"], timeout=180)
    if rc != 0:
        return {"composite": None, "available": False}
    m = re.search(r"health_score \(composite\):\s*(\d+)/100", out)
    if not m:
        return {"composite": None, "available": False}
    return {"composite": int(m.group(1)), "available": True}


def _rot_defense_layers() -> dict[str, str]:
    p = WS_ROOT / "docs" / "architecture" / "rot-defense-pipeline-v1.md"
    if not p.is_file():
        return {}
    text = p.read_text(encoding="utf-8")
    return {
        "doc_present": "yes" if len(text) > 1000 else "minimal",
        "layers_described": str(text.count("L1") + text.count("L2") + text.count("L3")),
    }


def _bet_completion() -> dict[str, Any]:
    rc, out, _ = _run([sys.executable, str(WS_ROOT / "bin" / "plan" / "bet-ledger.py"), "status"])
    if rc != 0:
        return {"available": False}
    total = re.search(r"总 bet:\s*(\d+)", out)
    done = re.search(r"done\s+(\d+)", out)
    candidate = re.search(r"candidate\s+(\d+)", out)
    return {
        "available": True,
        "total": int(total.group(1)) if total else 0,
        "done": int(done.group(1)) if done else 0,
        "candidate": int(candidate.group(1)) if candidate else 0,
        "completion_pct": round(100 * int(done.group(1)) / int(total.group(1)), 1) if total and done else 0,
    }


def _status_for_scene(counts: dict[str, int], target_3m_assisted: int) -> str:
    assisted = counts.get("assisted", 0) + counts.get("supervised", 0) + counts.get("routine", 0)
    shadow = counts.get("shadow", 0)
    if assisted >= target_3m_assisted:
        return "GREEN"
    if shadow > 0 and assisted > 0:
        return "YELLOW"
    if shadow > 0:
        return "RED"
    return "GREY"


def _status_for_maturity(overall: float | None, target_3m: float = 8.0) -> str:
    if overall is None:
        return "GREY"
    if overall >= target_3m:
        return "GREEN"
    if overall >= target_3m - 0.5:
        return "YELLOW"
    return "RED"


def _status_for_bcos(status: str) -> str:
    if status == "provable":
        return "GREEN"
    if status in {"partial", "degraded"}:
        return "YELLOW"
    return "RED"


def _status_for_health(composite: int | None) -> str:
    if composite is None:
        return "GREY"
    if composite >= 80:
        return "GREEN"
    if composite >= 65:
        return "YELLOW"
    return "RED"


def _status_for_dim4_experience(health: dict[str, Any], north_star: dict[str, Any]) -> str:
    """Dim 4 体验 — daemon-stable proxy.

    When compass_radar is available (daemon online), use its composite as the
    canonical reading. When the daemon is down (transient service_online_ratio
    false positive, see .omo/state/system.yaml:runtime_health_summary.source),
    fall back to north_star v3 advisory composite (5-axis → 4-axis → BC) which
    is derived entirely from on-disk telemetry and doesn't depend on any
    runtime daemon. The advisory composites are the closest on-disk proxy for
    "主人 ≤ 15min/日" since they read from the same evidence sources.

    This keeps dim 4 GREEN when the value proof is strong on-disk even if
    the runtime daemon is temporarily flaky, instead of flipping it to GREY.
    """
    compass = health.get("composite") if isinstance(health, dict) else None
    if isinstance(health, dict) and health.get("available") and compass is not None:
        return _status_for_health(compass)
    fallback = (
        north_star.get("composite_5axis") or north_star.get("composite_4axis") or north_star.get("composite")
        if isinstance(north_star, dict)
        else None
    )
    return _status_for_health(fallback)


def _status_for_bets(bet: dict[str, Any]) -> str:
    if not bet.get("available"):
        return "GREY"
    pct = bet.get("completion_pct", 0)
    if pct >= 95:
        return "GREEN"
    if pct >= 85:
        return "YELLOW"
    return "RED"


def _anti_pattern_status() -> dict[str, Any]:
    rc, out, _ = _run(
        [sys.executable, str(WS_ROOT / "bin" / "gac" / "anti-pattern-detector.py"), "--json"],
        timeout=120,
    )
    if rc != 0:
        return {"available": False, "detected_count": None}
    try:
        data = json.loads(out)
        return {
            "available": True,
            "detected_count": data.get("detected_count", 0),
            "total_patterns": data.get("total_patterns", 0),
            "status": data.get("status", "unknown"),
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"available": False, "detected_count": None}


def collect_dimensions() -> list[dict[str, Any]]:
    scene_counts = _scene_lifecycle_counts()
    overall = _maturity_overall()
    journey_counts = _journey_status_counts()
    north_star = _bcos_north_star_status()
    health = _compass_health()
    rot = _rot_defense_layers()
    bet = _bet_completion()
    anti_pattern = _anti_pattern_status()

    return [
        {
            "id": 1,
            "name": "场景",
            "target_3m": "≥3 张 shadow → assisted",
            "current": scene_counts,
            "status": _status_for_scene(scene_counts, target_3m_assisted=3),
        },
        {
            "id": 2,
            "name": "功能",
            "target_3m": "maturity ≥ 8.0",
            "current": {"overall": overall},
            "status": _status_for_maturity(overall, target_3m=8.0),
        },
        {
            "id": 3,
            "name": "旅程",
            "target_3m": "≥3 active journey",
            "current": journey_counts,
            "status": "GREEN"
            if sum(1 for k, v in journey_counts.items() if v > 0 and k != "stub") >= 3
            else "YELLOW"
            if sum(journey_counts.values()) > 0
            else "RED",
        },
        {
            "id": 4,
            "name": "体验",
            "target_3m": "主人 ≤ 15min/日 (proxy: max(compass_health, v3_5axis) ≥ 80)",
            "current": {
                "compass_composite": health.get("composite"),
                "compass_available": health.get("available", False),
                "v3_5axis": north_star.get("composite_5axis") if isinstance(north_star, dict) else None,
                "used": "compass" if health.get("available") else "v3_5axis_fallback",
            },
            "status": _status_for_dim4_experience(health, north_star),
        },
        {
            "id": 5,
            "name": "愿景 (BCOS)",
            "target_3m": "north_star = provable",
            "current": north_star,
            "status": _status_for_bcos(
                str(north_star.get("status") if isinstance(north_star, dict) else north_star or "unknown")
            ),
        },
        {
            "id": 6,
            "name": "长期运营",
            "target_3m": "weekly-review routine 化 (proxy: BET ≥ 95%)",
            "current": bet,
            "status": _status_for_bets(bet),
        },
        {
            "id": 7,
            "name": "运维",
            "target_3m": "L1 入口 6.5 → 8 (proxy: cockpit maturity)",
            "current": {"note": "proxy: maturity ≥ 8.0"},
            "status": _status_for_maturity(overall, target_3m=8.0),
        },
        {
            "id": 8,
            "name": "防腐",
            "target_3m": "G1/G2 接线缺口闭合",
            "current": rot,
            "status": "GREEN" if rot.get("doc_present") == "yes" else "GREY",
        },
        {
            "id": 9,
            "name": "约束",
            "target_3m": "5 反模式 → 0",
            "current": anti_pattern,
            "status": "GREEN"
            if anti_pattern.get("available") and anti_pattern.get("detected_count", 0) == 0
            else "YELLOW"
            if anti_pattern.get("available")
            else "GREY",
        },
    ]


def render_text(dims: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("9 维战略一致性矩阵 (project-strategy-v1 §10)")
    lines.append("=" * 72)
    now = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    lines.append(f"snapshot_ts: {now}")
    lines.append("")
    lines.append(f"{'#':<3} {'dim':<12} {'status':<8} {'target_3m':<48} current")
    lines.append("-" * 100)
    for d in dims:
        cur = str(d["current"])
        if len(cur) > 38:
            cur = cur[:35] + "..."
        tgt = d["target_3m"]
        if len(tgt) > 48:
            tgt = tgt[:45] + "..."
        lines.append(f"{d['id']:<3} {d['name']:<12} {d['status']:<8} {tgt:<48} {cur}")
    lines.append("")
    counts = {"GREEN": 0, "YELLOW": 0, "RED": 0, "GREY": 0}
    for d in dims:
        counts[d["status"]] = counts.get(d["status"], 0) + 1
    lines.append(
        f"summary: GREEN={counts.get('GREEN', 0)}  YELLOW={counts.get('YELLOW', 0)}  RED={counts.get('RED', 0)}  GREY={counts.get('GREY', 0)}  (of {len(dims)})"
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="9 维战略一致性矩阵验证器")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--strict", action="store_true", help="任一 RED 退出 1")
    args = parser.parse_args()
    dims = collect_dimensions()
    if args.json:
        out = {
            "snapshot_ts": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "dimensions": dims,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(render_text(dims))
    if args.strict and any(d["status"] == "RED" for d in dims):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
