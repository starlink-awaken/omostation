#!/usr/bin/env python3
"""Vision Audit — Vision 自评估 (EVO-03).

定期比对 VISION-ROADMAP.md 目标 vs 现状 → 产出 gap 分析报告.
让系统能自评估愿景达成度, 而非仅靠人工维护 vision.

Usage:
  python3 bin/ssot/vision-audit.py             # 产出 gap 分析
  python3 bin/ssot/vision-audit.py --json
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from _shared import ROOT, load_yaml, utc_now

VISION_PATH = ROOT / "docs" / "VISION-ROADMAP.md"
BET_LEDGER = ROOT / "docs" / "plans" / "3y-bet-ledger.yaml"
OUT_DIR = ROOT / ".omo" / "_knowledge" / "vision-audits"


def _load_bet_data() -> dict[str, Any]:
    return load_yaml(BET_LEDGER)


def _extract_vision_pillars(bet_data: dict[str, Any]) -> list[str]:
    """Extract implementation targets from bet ledger (真实可检测目标).

    从 3y-bet-ledger.yaml 的 bet title 提取目标, 而非 vision 章节标题
    (章节标题与实现信号不可匹配, 造成假 gap).
    """
    bets = bet_data.get("bets", []) if isinstance(bet_data, dict) else []
    if not isinstance(bets, list):
        return []
    # 只取目标性 title (非纯治理/纪律类), 前 12 个
    pillars = []
    for b in bets:
        if not isinstance(b, dict):
            continue
        title = str(b.get("title", "")).strip()
        if title and "纪律" not in title and "保护" not in title:
            pillars.append(title)
        if len(pillars) >= 12:
            break
    return pillars


def _load_bet_status(bet_data: dict[str, Any]) -> dict[str, Any]:
    """Load bet completion status from pre-parsed bet data (SSOT).

    返回 {total, done, done_rate}.
    反映 3Y 规划的真实推进度 — 作为 vision 现状的核心信号.
    """
    bets = bet_data.get("bets", []) if isinstance(bet_data, dict) else []
    if not isinstance(bets, list):
        return {"total": 0, "done": 0, "done_rate": 0.0}
    total = len(bets)
    done = sum(1 for b in bets if isinstance(b, dict) and b.get("status") == "done")
    return {
        "total": total,
        "done": done,
        "done_rate": round(done / total, 2) if total else 0.0,
    }


def _check_implementation(pillar: str) -> dict[str, Any]:
    """Heuristic: check if a vision pillar has corresponding implementation signals."""
    keyword = pillar.lower()
    signals: list[str] = []

    # Check docs exist
    doc_hits = {
        "architecture": ROOT / "docs" / "ARCHITECTURE.md",
        "journey": ROOT / "docs" / "journey-specs",
        "scene": ROOT / "docs" / "scene-cards",
        "governance": ROOT / ".omo" / "_truth" / "registry" / "governance-checks.yaml",
        "agent": ROOT / "bin" / "ssot",
    }
    for name, path in doc_hits.items():
        if name in keyword and path.exists():
            signals.append(f"docs:{name}")

    # Check tool presence
    if "自主" in pillar or "autonom" in keyword:
        if (ROOT / "bin/ssot/autoloop-controller.py").exists():
            signals.append("autoloop")
    if "进化" in pillar or "evolut" in keyword:
        if (ROOT / "bin/ssot/evolution-agent.py").exists():
            signals.append("evolution-agent")
    if "感知" in pillar or "percep" in keyword:
        if (ROOT / "bin/ssot/signal-poller.py").exists():
            signals.append("signal-poller")

    return {
        "pillar": pillar,
        "implementation_signals": signals,
        "coverage": "implemented" if signals else "gap",
    }


def audit_vision(root: Path | None = None) -> dict[str, Any]:
    root = root or ROOT
    bet_data = _load_bet_data()
    pillars = _extract_vision_pillars(bet_data)
    audits = [_check_implementation(p) for p in pillars]
    gaps = [a for a in audits if a["coverage"] == "gap"]
    implemented = [a for a in audits if a["coverage"] == "implemented"]
    bet = _load_bet_status(bet_data)

    result = {
        "schema": "vision-audit/v1",
        "generated_at": utc_now(),
        "pillars_found": len(pillars),
        "implemented": len(implemented),
        "gaps": len(gaps),
        "coverage_rate": round(len(implemented) / len(pillars), 2) if pillars else 0.0,
        "gap_pillars": [a["pillar"] for a in gaps],
        "bet_progress": bet,
        "detail": audits,
    }

    # Persist audit report
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    (OUT_DIR / f"audit-{ts}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    result = audit_vision(args.root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Vision Audit: {result['implemented']}/{result['pillars_found']} pillars "
              f"implemented (coverage {result['coverage_rate']:.0%})")
        print(f"  Bet 进度: {result['bet_progress'].get('done')}/{result['bet_progress'].get('total')} "
              f"done ({result['bet_progress'].get('done_rate', 0):.0%})")
        for a in result["detail"]:
            marker = "✅" if a["coverage"] == "implemented" else "⬜"
            print(f"  {marker} {a['pillar']}: {a['implementation_signals'] or 'GAP'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
