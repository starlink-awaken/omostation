#!/usr/bin/env python3
"""Trust Adjuster — Trust动态调整 + 名单级别自适应 (T5).

PR审查结果(outcome)反馈到Trust + 名单动态调整:
  - PR approved+merged → capability_calibration success_rate↑
  - PR rejected → success_rate↓
  - 灰名单多次approved → 提升到白名单
  - 白名单多次rejected → 降级到灰名单

复用: MOSBeliefManager.record_capability_calibration()

Usage:
  python3 bin/ssot/trust-adjuster.py --show                 # 显示Trust状态
  python3 bin/ssot/trust-adjuster.py --outcome approved      # 记录PR approved
  python3 bin/ssot/trust-adjuster.py --outcome rejected      # 记录PR rejected
  python3 bin/ssot/trust-adjuster.py --check-promotion       # 检查名单级别调整
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _shared import ROOT, load_yaml

OMO_SRC = str(ROOT / "projects/omo/src")
PERMISSION_MATRIX = ROOT / ".omo/_truth/registry/action-permission-matrix.yaml"


def _get_manager():
    if OMO_SRC not in sys.path:
        sys.path.insert(0, OMO_SRC)
    from omo.omo_belief import MOSBeliefManager
    return MOSBeliefManager(root=ROOT)


def show_trust() -> dict[str, Any]:
    """Display current Trust state from MOS."""
    manager = _get_manager()
    state = manager._load_state()
    calibrations = state.get("capability_calibrations", [])
    if not calibrations:
        return {"trust_level": "cold_start", "calibrations": 0}

    avg_rate = sum(float(c.get("success_rate", 1.0)) for c in calibrations) / len(calibrations)
    recent = calibrations[-5:]
    recent_rate = sum(float(c.get("success_rate", 1.0)) for c in recent) / len(recent)

    return {
        "trust_level": "high" if avg_rate >= 0.8 else "medium" if avg_rate >= 0.5 else "low",
        "total_calibrations": len(calibrations),
        "avg_success_rate": round(avg_rate, 3),
        "recent_success_rate": round(recent_rate, 3),
        "last_calibration": calibrations[-1].get("capability_ref", "?"),
    }


def record_outcome(outcome: str, *, action_type: str = "autoloop", pr_number: int = 0) -> dict[str, Any]:
    """Record a PR outcome to Trust calibration."""
    manager = _get_manager()
    success_rate = 1.0 if outcome == "approved" else 0.0 if outcome == "rejected" else 0.5

    cc_id = manager.record_capability_calibration(
        capability_ref=f"autoloop:{action_type}",
        success_rate=success_rate,
        sample_size=1,
        last_run_id=f"pr-{pr_number}" if pr_number else None,
    )
    return {"status": "recorded", "calibration_id": cc_id, "success_rate": success_rate}


def check_promotion() -> dict[str, Any]:
    """Check if any graylist items should be promoted to whitelist (or demoted)."""
    matrix = load_yaml(PERMISSION_MATRIX)
    manager = _get_manager()
    state = manager._load_state()
    calibrations = state.get("capability_calibrations", [])

    promotions: list[dict] = []
    demotions: list[dict] = []

    for item in matrix.get("graylist", []):
        action_type = item.get("action_type", "")
        # Count consecutive approvals for this action
        action_calibs = [c for c in calibrations if action_type in str(c.get("capability_ref", ""))]
        recent_3 = action_calibs[-3:] if len(action_calibs) >= 3 else []
        if recent_3 and all(float(c.get("success_rate", 0)) >= 0.8 for c in recent_3):
            promotions.append({
                "action_type": action_type,
                "reason": f"3+ consecutive approvals (rate≥0.8)",
                "from": "graylist",
                "to": "whitelist",
            })

    for item in matrix.get("whitelist", []):
        action_type = item.get("action_type", "")
        action_calibs = [c for c in calibrations if action_type in str(c.get("capability_ref", ""))]
        recent_2 = action_calibs[-2:] if len(action_calibs) >= 2 else []
        if recent_2 and all(float(c.get("success_rate", 0)) < 0.5 for c in recent_2):
            demotions.append({
                "action_type": action_type,
                "reason": f"2+ consecutive rejections (rate<0.5)",
                "from": "whitelist",
                "to": "graylist",
            })

    return {
        "promotions": promotions,
        "demotions": demotions,
        "total_promotions": len(promotions),
        "total_demotions": len(demotions),
        "note": "promotions/demotions require --apply to modify permission matrix",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--outcome", choices=["approved", "rejected", "revised"], default=None)
    parser.add_argument("--action-type", default="autoloop")
    parser.add_argument("--pr", type=int, default=0)
    parser.add_argument("--check-promotion", action="store_true")
    args = parser.parse_args(argv)

    if args.show:
        result = show_trust()
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.outcome:
        result = record_outcome(args.outcome, action_type=args.action_type, pr_number=args.pr)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.check_promotion:
        result = check_promotion()
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    # Default: show
    result = show_trust()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
