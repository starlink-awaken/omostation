#!/usr/bin/env python3
"""Value-Proof Debt Registry — scan done BETs for unproven value axis (BET-Y1Q4-T4-05).

Scans docs/plans/3y-bet-ledger.yaml for BETs where:
  - status = done
  - value_indicator_policy = false
  - completion_evidence.axes.value.status in (NOT_PROVEN, REJECTED, ACCEPTED with no attestation)

Outputs a registry report listing each BET's:
  - bet_id, track, title
  - vip (value_indicator_policy)
  - value axis status
  - suggested action (backfill / written exemption / no-action)

Circuit breaker: when attestation/signed evidence is unavailable, leave
NOT_PROVEN as the official status rather than forging ACCEPTED. This
prevents "已 done" from being misread as "愿景已证明".

Usage:
    python3 bin/plan/value-proof-debt-registry.py --json
    python3 bin/plan/value-proof-debt-registry.py --output docs/reports/2026-MM-DD-registry.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs" / "plans" / "3y-bet-ledger.yaml"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def scan_debt(ledger_path: Path = LEDGER) -> dict[str, Any]:
    """Scan ledger for done BETs with unproven value axis.

    Returns registry dict with stats, entries, and provenance.
    """
    if not ledger_path.is_file():
        return {"ok": False, "error": "ledger-not-found", "ledger": str(ledger_path)}

    data = yaml.safe_load(ledger_path.read_text())
    bets = data.get("bets", [])

    entries: list[dict[str, Any]] = []
    for b in bets:
        if b.get("status") != "done":
            continue

        vip = b.get("value_indicator_policy", True)
        ce = b.get("completion_evidence")
        if not isinstance(ce, dict):
            continue
        axes = ce.get("axes", {})
        value_axis = axes.get("value", {})
        value_status = value_axis.get("status")

        # Filter: VIP=false AND value status unproven
        if vip is False and value_status in ("NOT_PROVEN", "REJECTED"):
            evidence = value_axis.get("evidence") or {}
            attestation = evidence.get("attestation") if isinstance(evidence, dict) else None

            suggested_action = "backfill-or-written-exemption"
            if value_status == "REJECTED":
                suggested_action = "decision-needed-rejected-status"

            entries.append({
                "bet_id": b["id"],
                "track": b.get("track"),
                "title": b.get("title"),
                "vip": vip,
                "value_status": value_status,
                "done_at": str(b.get("done_at") or ""),
                "has_attestation": bool(attestation),
                "suggested_action": suggested_action,
            })

    stats = {
        "total": len(entries),
        "not_proven": sum(1 for e in entries if e["value_status"] == "NOT_PROVEN"),
        "rejected": sum(1 for e in entries if e["value_status"] == "REJECTED"),
        "with_attestation": sum(1 for e in entries if e["has_attestation"]),
    }

    return {
        "ok": True,
        "schema_version": "value-proof-debt-registry/v1",
        "observed_at": _utc_now(),
        "ledger": str(ledger_path.relative_to(ROOT)),
        "stats": stats,
        "entries": entries,
    }


def render_markdown(reg: dict[str, Any]) -> str:
    """Render registry as markdown report."""
    lines = [
        "---",
        "schema_version: receipt/v1",
        "type: report",
        "title: Value-Proof Debt Registry — Spine done BETs",
        "status: archived",
        "lifecycle: contract",
        "owner: governance-agent",
        f"created: {datetime.now(timezone.utc).date().isoformat()}",
        f"last_updated: {datetime.now(timezone.utc).date().isoformat()}",
        "---",
        "",
        "# Value-Proof Debt Registry",
        "",
        f"**Observed**: {reg['observed_at']}  ",
        f"**Ledger**: `{reg['ledger']}`  ",
        f"**Entries**: {reg['stats']['total']} (NOT_PROVEN={reg['stats']['not_proven']}, REJECTED={reg['stats']['rejected']})  ",
        f"**With attestation**: {reg['stats']['with_attestation']}",
        "",
        "## Circuit Breaker",
        "",
        "Per BET-Y1Q4-T4-05 design: when attestation/signed evidence is unavailable,",
        "leave `NOT_PROVEN` as the official status rather than forging `ACCEPTED`.",
        "This prevents \"已 done\" from being misread as \"愿景已证明\".",
        "",
        "## Methodology",
        "",
        "Scan `docs/plans/3y-bet-ledger.yaml` for BETs where:",
        "1. `status == done`",
        "2. `value_indicator_policy == false`",
        "3. `completion_evidence.axes.value.status` ∈ {`NOT_PROVEN`, `REJECTED`}",
        "",
        "## Entries",
        "",
    ]

    if not reg["entries"]:
        lines.append("_No debt entries found._")
    else:
        lines.append("| BET ID | Track | VIP | Value Status | Has Attestation | Suggested Action |")
        lines.append("|--------|-------|-----|--------------|-----------------|-------------------|")
        for e in reg["entries"]:
            attestation = "yes" if e["has_attestation"] else "no"
            lines.append(
                f"| {e['bet_id']} | {e['track']} | {e['vip']} | {e['value_status']} | "
                f"{attestation} | {e['suggested_action']} |"
            )

    lines.extend([
        "",
        "## References",
        "",
        "- `docs/superpowers/specs/2026-09-05-bet-y1q4-t4-05-value-proof-debt-registry-design.md`",
        "- `KR-VALUE-JOURNEY-COMPLETION`, `KR-VALUE-WEEKLY-ADOPTION`, `KR-VALUE-REVISION-RATE`",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Value-Proof Debt Registry (BET-Y1Q4-T4-05)"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--output", type=str, default="", help="Write markdown report to path")
    parser.add_argument("--ledger", type=str, default=str(LEDGER), help="Path to ledger")
    args = parser.parse_args()

    reg = scan_debt(Path(args.ledger))
    if not reg["ok"]:
        print(f"ERROR: {reg['error']}")
        return 1

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_markdown(reg), encoding="utf-8")
        reg["output_path"] = str(out_path)

    if args.json:
        print(json.dumps(reg, ensure_ascii=False, indent=2))
    else:
        print(f"Value-Proof Debt Registry: {reg['stats']['total']} entries")
        print(f"  NOT_PROVEN: {reg['stats']['not_proven']}")
        print(f"  REJECTED: {reg['stats']['rejected']}")
        print(f"  With attestation: {reg['stats']['with_attestation']}")
        if reg.get("output_path"):
            print(f"  Wrote: {reg['output_path']}")
        if reg["entries"]:
            print("\nEntries:")
            for e in reg["entries"][:10]:
                print(f"  {e['bet_id']:30} vip={e['vip']} value={e['value_status']} action={e['suggested_action']}")
            if len(reg["entries"]) > 10:
                print(f"  ... and {len(reg['entries']) - 10} more")

    return 0


if __name__ == "__main__":
    sys.exit(main())