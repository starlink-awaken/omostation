#!/usr/bin/env python3
"""check-governance-ratio: enforce ADR-0249 40% governance cap.

Rolls a 30-day window over workflow start events and computes the
governance share. A run is classified governance when ANY of:

  - the run's `agent_profile` is governance / mof / state-sync /
    release / governance-agent
  - the run's lock targets include `.omo/`, `bin/gac/`,
    `bin/ssot/`, `projects/ecos/`, `projects/omo/`
  - the run's workflow_id is `governance-state-mutation`,
    `mof-model-change`, `governance-audit`,
    `governance-evolution`, `submodule-pointer-close`,
    `external-adapter-sync`, `state-sync`, `mof-state-bridge-audit`

Other runs default to `flex`. A run carries the new `track` key
explicitly in events.jsonl (G1.2 wiring) — the implementation
respects that override when present.

Output:
  - 30-day ratio (0.0 .. 1.0)
  - share of governance / flex / collaboration
  - 列出被分类为治理的 run ids

Exit:
  - 0: ok (<=40%) or warn-only (35..40%)
  - 1: blocking (>40% with no human-approval run)
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
LEDGER = WORKSPACE / ".omo/_delivery/agent-workflows/events.jsonl"

# ADR-0249 was formally approved on 2026-08-01. Runs before this
# date are grandfathered and do NOT count toward the governance
# ceiling. This prevents historical governance-heavy runs from
# poisoning the ratio before the policy took effect.
ENFORCED_FROM = datetime(2026, 8, 1, tzinfo=timezone.utc)

WINDOW_DAYS = 30
GOVERNANCE_CEILING = 0.40
WARN_THRESHOLD = 0.35

GOVERNANCE_PROFILES = {
    "governance-agent",
    "mof-agent",
    "state-sync-agent",
    "release-agent",
    "obs-agent",
}
GOVERNANCE_PATHS = (
    ".omo/",
    "bin/gac/",
    "bin/ssot/",
    "projects/ecos/",
    "projects/omo/",
    "projects/metaos/",
)
GOVERNANCE_WORKFLOWS = {
    "governance-state-mutation",
    "mof-model-change",
    "governance-audit",
    "governance-evolution",
    "submodule-pointer-close",
    "external-adapter-sync",
    "state-sync",
    "mof-state-bridge-audit",
    "c2g-spec-ingress",
}


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _classify(evt: dict) -> str:
    if evt.get("track") in {"governance", "collaboration", "flex"}:
        return evt["track"]
    if evt.get("agent_profile") in GOVERNANCE_PROFILES:
        return "governance"
    if evt.get("workflow_id") in GOVERNANCE_WORKFLOWS:
        return "governance"
    locks = evt.get("locks") or []
    for lock in locks:
        for pat in GOVERNANCE_PATHS:
            if pat in str(lock):
                return "governance"
    if "collaboration" in (evt.get("objective") or "").lower():
        return "collaboration"
    return "flex"


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--window-days", type=int, default=WINDOW_DAYS)
    args = parser.parse_args(argv)

    if not LEDGER.is_file():
        report = {
            "ok": True,
            "window_days": args.window_days,
            "ratio": 0.0,
            "message": "no ledger",
            "buckets": {"governance": 0, "collaboration": 0, "flex": 0},
            "governance_runs": [],
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("check-governance-ratio: PASS (no ledger)")
        return 0

    now = datetime.now(timezone.utc)
    # Events before ENFORCED_FROM are grandfathered (ADR-0249 not
    # yet in effect) and must not count toward the ratio.
    cutoff = max(now - timedelta(days=args.window_days), ENFORCED_FROM)

    events: list[dict] = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    starts: list[dict] = []
    for evt in events:
        if evt.get("event") != "agent_workflow_start":
            continue
        ts = _parse_ts(evt.get("ts") or "")
        if ts is None or ts < cutoff:
            continue
        starts.append(evt)

    buckets: collections.Counter = collections.Counter()
    governance_runs: list[dict] = []
    for evt in starts:
        kind = _classify(evt)
        buckets[kind] += 1
        if kind == "governance":
            governance_runs.append({
                "run_id": evt.get("run_id"),
                "ts": evt.get("ts"),
                "agent_profile": evt.get("agent_profile"),
                "workflow_id": evt.get("workflow_id"),
            })

    total = sum(buckets.values())
    ratio = (buckets["governance"] / total) if total else 0.0

    # Statistical guard: with too few runs the ratio is not a real
    # signal. The 40% ceiling only applies once we have a meaningful
    # sample (>= MIN_RUNS); otherwise surface as warn-only.
    MIN_RUNS = 10

    has_human_approval = any(
        (evt.get("objective") or "").startswith("[human]")
        for evt in starts
    )
    if total < MIN_RUNS:
        ok = True
        level = "warn"
        reason = f"sample_too_small (total={total} < {MIN_RUNS})"
    elif ratio > GOVERNANCE_CEILING and not has_human_approval:
        ok = False
        level = "blocking"
        reason = f"ratio {ratio:.1%} > ceiling {GOVERNANCE_CEILING:.0%}"
    elif ratio > WARN_THRESHOLD:
        ok = True
        level = "warn"
        reason = f"ratio {ratio:.1%} approaching ceiling {GOVERNANCE_CEILING:.0%}"
    else:
        ok = True
        level = "ok"
        reason = f"ratio {ratio:.1%} within budget"

    report = {
        "ok": ok,
        "level": level,
        "reason": reason,
        "window_days": args.window_days,
        "ratio": round(ratio, 4),
        "total_runs": total,
        "buckets": dict(buckets),
        "governance_runs": governance_runs,
        "ceiling": GOVERNANCE_CEILING,
        "has_human_approval": has_human_approval,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"check-governance-ratio: {'PASS' if ok else 'FAIL'} ({level})")
        print(
            f"  window={args.window_days}d total={total} "
            f"governance={buckets['governance']} collab={buckets['collaboration']} "
            f"flex={buckets['flex']} ratio={ratio:.1%} {reason}"
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
