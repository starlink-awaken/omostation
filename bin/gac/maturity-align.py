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
            [sys.executable, str(script), "--json"],
            cwd=ws_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
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
    out["dimensions"] = data.get("scores") or {}
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
    values = [v for v in (c_norm, s_norm, l_norm) if v is not None]

    drift_detected = False
    warnings: list[str] = []
    if values:
        spread = max(values) - min(values)
        # > 30 points spread on a 0-100 scale = meaningful disagreement
        if spread > 30:
            drift_detected = True
            warnings.append(
                f"score spread = {spread:.0f} (compass {c_norm}, scorecard {s_norm}, ledger {l_norm})"
            )

    # Reconciliation = 100 - spread (perfect = 100, max disagreement = 0)
    if values:
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

    return {
        "drift_detected": drift_detected,
        "reconciliation_score": reconciliation_score,
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
            for dim, score in (scorecard.get("dimensions") or {}).items():
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