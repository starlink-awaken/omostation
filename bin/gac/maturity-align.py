#!/usr/bin/env python3
"""maturity-align: 三方成熟度口径对齐 (BET-Y1Q3-T10-10).

Single-source-of-truth reconciliation for "how mature are we?" across the
three independent measurement systems:

  1. compass_radar.health_score         — composite 0-100 (governance+runtime+freshness+drift+staleness)
  2. maturity-scorecard                 — 6 dims × 1-10, overall avg (target 9.0)
  3. bet-ledger completion              — 141 bets × 3 axes (engineering/operational/value) → done/candidate/blocked

The three systems use different scales, different denominators, and
different evidence sources, so a naive "70 vs 7.8 vs 89%" comparison is
meaningless. This tool produces a side-by-side view, computes a
reconciliation score, and surfaces drift between the three.

输出 (JSON or human-readable):

  {
    "compass_radar":   {"health_score": 70, "freshness_score": 100, ...},
    "maturity_scorecard": {"overall": 7.8, "dimensions": {...}},
    "bet_ledger":      {"total": 141, "done": 126, "candidate": 13, "blocked": 2, "completion_pct": 89.4},
    "alignment": {
      "drift_detected": true,
      "high_dimension": "...",
      "low_dimension": "...",
      "reconciliation_score": 78,    # 0-100, how aligned the three are
      "warnings": ["..."]
    }
  }

Reconciliation score:
  - normalise each scale to 0-100
  - compute weighted distance (1 - avg_pair_diff)
  - 100 = perfectly aligned, 0 = maximum drift

Usage:
  python bin/gac/maturity-align.py             # human output
  python bin/gac/maturity-align.py --json     # JSON
  python bin/gac/maturity-align.py --strict    # exit 1 on drift > 30
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

WS_ROOT = Path(__file__).resolve().parent.parent.parent


def _read_yaml_field(yaml_path: Path, field: str) -> str | None:
    """Tiny YAML field reader (no PyYAML needed) — single-line scalars only.

    Avoids adding pyyaml to bin/gac dependencies. Used for compass_radar's
    single-line `health_score: 70` block.
    """
    if not yaml_path.is_file():
        return None
    pattern = re.compile(rf"^{re.escape(field)}\s*:\s*(.+?)\s*$")
    for line in yaml_path.read_text(encoding="utf-8").splitlines():
        stripped = line.split("#", 1)[0].rstrip()
        m = pattern.match(stripped)
        if m:
            value = m.group(1).strip()
            # strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            return value
    return None


def collect_compass_radar(ws_root: Path) -> dict[str, Any]:
    """Read .omo/state/health.yaml for the ISC-3 composite score."""
    health_yaml = ws_root / ".omo" / "state" / "health.yaml"
    fields = ("health_score", "governance_anomaly_score", "freshness_score", "drift_score", "staleness_score")
    out: dict[str, Any] = {"source": "compass_radar", "path": str(health_yaml)}
    for field in fields:
        raw = _read_yaml_field(health_yaml, field)
        if raw is None:
            out[field] = None
            continue
        try:
            out[field] = int(raw)
        except ValueError:
            out[field] = raw  # may be "unavailable"
    return out


def collect_maturity_scorecard(ws_root: Path) -> dict:
    """Subprocess bin/gac/maturity-scorecard.py --json (real audit, no mock)."""
    script = ws_root / "bin" / "gac" / "maturity-scorecard.py"
    out: dict[str, Any] = {"source": "maturity-scorecard", "path": str(script)}
    if not script.is_file():
        out["available"] = False
        return out
    out["available"] = True
    try:
        res = subprocess.run(
            [sys.executable, str(script), "--json", "--skip-observable"],
            cwd=ws_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        out["error"] = f"subprocess: {str(exc)[:120]}"
        return out
    stdout = (res.stdout or "").strip()
    if not stdout.startswith("{"):
        out["error"] = f"exit={res.returncode} empty-stdout"
        return out
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        out["error"] = f"json: {str(exc)[:120]}"
        return out
    out["overall"] = data.get("overall")
    out["target"] = data.get("target")
    out["gap"] = data.get("gap")
    out["dimensions"] = data.get("dimensions") or data.get("scores") or {}
    if out["overall"] is None and out["dimensions"]:
        scores = [d.get("score", 0) for d in out["dimensions"] if isinstance(d, dict)]
        if scores:
            out["overall"] = round(sum(scores) / len(scores), 1)
    out["raw"] = data
    return out


def collect_bet_ledger(ws_root: Path) -> dict[str, Any]:
    """Parse `bin/plan/bet-ledger.py status` output for total/done/candidate/blocked."""
    script = ws_root / "bin" / "plan" / "bet-ledger.py"
    out: dict[str, Any] = {"source": "bet-ledger", "path": str(script)}
    if not script.is_file():
        out["available"] = False
        return out
    out["available"] = True
    try:
        res = subprocess.run(
            [sys.executable, str(script), "status"],
            cwd=ws_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        out["error"] = f"subprocess: {str(exc)[:120]}"
        return out
    stdout = res.stdout or ""
    counts: dict[str, int] = {}
    for key in ("done", "candidate", "blocked"):
        m = re.search(rf"^\s*{key}\s+(\d+)\s*$", stdout, re.MULTILINE)
        if m:
            counts[key] = int(m.group(1))
    m_total = re.search(r"^总 bet:\s*(\d+)\s*$", stdout, re.MULTILINE)
    out["counts"] = counts
    out["total"] = int(m_total.group(1)) if m_total else None
    if out["total"]:
        out["completion_pct"] = round(100 * counts.get("done", 0) / out["total"], 1)
    else:
        out["completion_pct"] = None
    return out


def normalise_to_100(value: float | None, scale_max: float) -> float | None:
    """Convert arbitrary scale to 0-100 for comparison."""
    if value is None:
        return None
    return max(0.0, min(100.0, 100.0 * value / scale_max))


def compute_reconciliation(
    compass: dict, scorecard: dict, ledger: dict
) -> dict:
    """Build the alignment view from the three independent collections.

    Reconciliation score (0-100) measures how *consistent* the three
    normalised views are. Two systems disagreeing is more dangerous than
    one system being low.
    """
    # Normalise each to 0-100 (best-case anchors per system)
    c_norm = normalise_to_100(compass.get("health_score"), 100)
    s_norm = normalise_to_100(scorecard.get("overall"), 10)
    l_norm = normalise_to_100(ledger.get("completion_pct"), 100)

    # 同口径 (2026-09-19 修正): reconciliation 只用**回答同一问题的**两个来源 ——
    # compass_radar.health_score 与 maturity_scorecard 都答"我们现在多成熟/多健康"。
    # 而 bet_ledger 答的是"计划做完没有", 是**不同的问题**。
    #
    # 把 l_norm 计入 spread 会造成两个可证的恶果 (2026-09-19 实测):
    #   ① **自指**: 计划全闭 (ledger=100) 时 spread = 100 - compass,
    #      于是 reconciliation 恒等于 compass_health —— 而 alignment 以 0.1 权重
    #      进健康分 (health_composite_breakdown.weights.alignment), 即健康分部分
    #      由自己算出。
    #   ② **反向激励**: compass 固定 70 时, ledger 50→100 (把计划做完) 会让
    #      reconciliation 从 80 掉到 70 —— 完成计划反而压低健康分。
    #
    # 修正后: reconciliation 只衡量**同口径一致性**; 跨口径的比较不丢, 而是落在
    # declaration_execution_gap (见下), **报告但不加权进健康分**。
    state_values = [v for v in (c_norm, s_norm) if v is not None]

    drift_detected = False
    warnings: list[str] = []
    if state_values:
        spread = max(state_values) - min(state_values)
        # > 30 points spread on a 0-100 scale = meaningful disagreement
        if spread > 30:
            drift_detected = True
            warnings.append(
                f"same-scope score spread = {spread:.0f} "
                f"(compass {c_norm}, scorecard {s_norm})"
            )

    # Reconciliation = 100 - spread (perfect = 100, max disagreement = 0)
    if state_values:
        reconciliation_score = round(100.0 - spread, 1)
    else:
        reconciliation_score = None

    # Pick the highest / lowest dimension for actionable insight
    pairs: list[tuple[str, float]] = []
    if c_norm is not None:
        pairs.append(("compass_radar", c_norm))
    if s_norm is not None:
        pairs.append(("maturity_scorecard", s_norm))
    if l_norm is not None:
        pairs.append(("bet_ledger", l_norm))
    pairs.sort(key=lambda kv: kv[1], reverse=True)
    high = pairs[0] if pairs else (None, None)
    low = pairs[-1] if pairs else (None, None)

    scorecard_gap = scorecard.get("gap")
    if scorecard_gap is not None and isinstance(scorecard_gap, (int, float)) and scorecard_gap > 2:
        warnings.append(
            f"maturity scorecard gap = {scorecard_gap:.1f} (target 9.0); below 80% of target"
        )

    # 声明/执行鸿沟的显式命名 (2026-09-19)。
    # 背景: 三个来源答的是**不同的问题** —— compass_radar = 系统当前状态,
    # maturity_scorecard = 能力成熟度, bet_ledger = **计划完成度**。前两者同口径
    # (都答"现在多成熟"), 而 bet_ledger 答的是"计划做完没有"。
    # 工具的设计前提是"计划是通往成熟的路径, 故 100% 完成应伴随成熟" —— 因此
    # ledger 显著高于系统状态时, 其含义不是"某个系统算错了", 而是
    # **"计划做完了, 却未转化为系统状态"** (仓库内登记的 critical 债务
    # DECL_EXEC_GAP 即此)。原先只报 "score spread = N", 读者需自行推断语义;
    # 此处把该差距**显式命名**并给出解释, 使其可行动。
    declaration_execution_gap = None
    if c_norm is not None and l_norm is not None:
        gap = round(l_norm - c_norm, 1)
        declaration_execution_gap = {
            "value": gap,
            "ledger_completion": l_norm,
            "compass_health": c_norm,
            "meaning": (
                "计划完成度与系统状态之差 = 声明/执行鸿沟: 计划做完了但未转化为"
                "系统状态" if gap > 0 else
                "系统状态高于计划完成度 (计划未完成但状态良好; 少见, 值得核查口径)"
                if gap < 0 else "计划完成度与系统状态一致"
            ),
        }
        if gap >= 30:
            warnings.append(
                f"声明/执行鸿沟 = {gap:.0f} (计划完成度 {l_norm:.0f} vs 系统状态 "
                f"{c_norm:.0f}) —— 计划已做完但未转化为系统状态; 这不是口径冲突, "
                f"是**闭环未产生价值**的信号 (见 debt item DECL_EXEC_GAP)"
            )

    return {
        "drift_detected": drift_detected,
        "reconciliation_score": reconciliation_score,
        "declaration_execution_gap": declaration_execution_gap,
        "normalised": {
            "compass_radar": c_norm,
            "maturity_scorecard": s_norm,
            "bet_ledger": l_norm,
        },
        "high_dimension": high[0],
        "low_dimension": low[0],
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="三方成熟度口径对齐 (BET-Y1Q3-T10-10)"
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="reconciliation_score < 70 → exit 1",
    )
    args = parser.parse_args()

    ws_root = WS_ROOT
    compass = collect_compass_radar(ws_root)
    scorecard = collect_maturity_scorecard(ws_root)
    ledger = collect_bet_ledger(ws_root)
    alignment = compute_reconciliation(compass, scorecard, ledger)

    if args.json:
        result = {
            "compass_radar": compass,
            "maturity_scorecard": scorecard,
            "bet_ledger": ledger,
            "alignment": alignment,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 72)
        print("三方成熟度口径对齐 (BET-Y1Q3-T10-10)")
        print("=" * 72)
        print()
        print("1. compass_radar (复合健康分, ISC-3, 0-100):")
        for k in ("health_score", "governance_anomaly_score", "freshness_score", "drift_score", "staleness_score"):
            v = compass.get(k)
            print(f"   {k:<28} {v if v is not None else 'unavailable'}")
        print()
        print("2. maturity-scorecard (6 维度 × 1-10, target 9.0):")
        if scorecard.get("available"):
            print(f"   overall                         {scorecard.get('overall')}/10 (target {scorecard.get('target')}, gap {scorecard.get('gap')})")
            dims = scorecard.get("dimensions") or []
            if isinstance(dims, list):
                for d in dims:
                    if isinstance(d, dict):
                        print(f"   - {d.get('dimension', '?'):<28} {d.get('score', '?')}/10")
            elif isinstance(dims, dict):
                for dim, score in dims.items():
                    print(f"   - {dim:<28} {score}/10")
        else:
            print("   unavailable:", scorecard.get("error", "tool missing"))
        print()
        print("3. bet-ledger (3Y BET 完工率):")
        if ledger.get("available"):
            print(f"   total: {ledger.get('total')}  done: {ledger.get('counts', {}).get('done')}  candidate: {ledger.get('counts', {}).get('candidate')}  blocked: {ledger.get('counts', {}).get('blocked')}")
            print(f"   completion_pct:                 {ledger.get('completion_pct')}%")
        else:
            print("   unavailable:", ledger.get("error", "tool missing"))
        print()
        print("=" * 72)
        print(f"对齐结果:  reconciliation_score = {alignment['reconciliation_score']}/100")
        if alignment["drift_detected"]:
            print(f"⚠️  DRIFT DETECTED — {len(alignment['warnings'])} warning(s):")
            for w in alignment["warnings"]:
                print(f"   - {w}")
        else:
            print("✅ 三方口径一致 (drift < 30)")
        if alignment["high_dimension"] and alignment["low_dimension"]:
            print(f"   high: {alignment['high_dimension']}  |  low: {alignment['low_dimension']}")
        print("=" * 72)

    if args.strict and alignment["reconciliation_score"] is not None and alignment["reconciliation_score"] < 70:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())