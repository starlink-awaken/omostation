#!/usr/bin/env python3
"""Proposal to ADR — 进化提案→ADR草稿自动转换 (T2).

读 evolution-proposals/ 最新提案 JSON → 用ADR模板生成草稿 → 写入 decisions/.
复用 bin/adr/next-adr-id.py 获取编号.

Usage:
  python3 bin/ssot/proposal-to-adr.py              # 转换最新提案
  python3 bin/ssot/proposal-to-adr.py --dry-run    # 预览不写入
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from _shared import ROOT

PROPOSALS_DIR = ROOT / ".omo" / "_knowledge" / "evolution-proposals"
DECISIONS_DIR = ROOT / ".omo" / "_knowledge" / "decisions"
NEXT_ADR_TOOL = ROOT / "bin" / "adr" / "next-adr-id.py"


def _latest_proposal() -> dict | None:
    """Load the most recent evolution proposal."""
    if not PROPOSALS_DIR.is_dir():
        return None
    files = sorted(PROPOSALS_DIR.glob("proposal-*.json"), reverse=True)
    if not files:
        return None
    return json.loads(files[0].read_text(encoding="utf-8"))


def _next_adr_id() -> str:
    """Get next ADR number from bin/adr/next-adr-id.py."""
    try:
        result = subprocess.run(
            ["python3", str(NEXT_ADR_TOOL)], capture_output=True, text=True, timeout=5, check=False,
        )
        return result.stdout.strip() or "ADR-0401"
    except Exception:
        return "ADR-0401"


def _generate_adr_draft(adr_id: str, proposal: dict) -> str:
    """Generate ADR markdown from proposal."""
    ts = datetime.now(UTC).strftime("%Y-%m-%d")
    proposals = proposal.get("proposals", [])

    # Pick the highest-priority proposal for the ADR title
    best = max(proposals, key=lambda p: {"P0": 4, "P1": 3, "P2": 2, "P3": 1}.get(p.get("priority", str(p.get("level", "P3"))), 0)) if proposals else {}

    title = best.get("proposal", "Evolution proposal")[:120]
    source = best.get("source", "unknown")
    level = best.get("level", "S3")

    body = f"""# {adr_id}: {title}

- status: draft
- date: {ts}
- owner: evolution-agent
- source: evolution-proposal ({proposal.get("generated_at", "")[:10]})
- risk_level: {level}

---

## Context

Auto-generated from evolution proposal. Source: `{source}`.

Total proposals in batch: {len(proposals)}

## Proposal Details

"""
    for p in proposals:
        body += f"### [{p.get('level', '?')}] {p.get('source', '?')}\n"
        body += f"**{p.get('proposal', '')}**\n"
        body += f"- Action: `{p.get('action', '')}`\n"
        body += f"- Severity: {p.get('severity', '?')}\n\n"

    body += """## Decision

_Pending human review. Auto-generated draft — do not merge without review._

## Consequences

- TBD (reviewer to fill)

## Follow-ups

- [ ] Human review
- [ ] Decision (accept/reject/defer)
"""
    return body


def convert(*, dry_run: bool = False) -> dict:
    """Convert latest proposal to ADR draft."""
    proposal = _latest_proposal()
    if not proposal:
        return {"status": "noop", "reason": "no proposals found"}

    adr_id = _next_adr_id()
    draft = _generate_adr_draft(adr_id, proposal)

    # Slugify title for filename
    proposals = proposal.get("proposals", [])
    slug = "evolution-batch"
    if proposals:
        first_word = proposals[0].get("type", "proposal").replace("_", "-")[:30]
        slug = first_word

    filename = f"{adr_id.lower().replace('adr-', '')}-{slug}.md"
    out_path = DECISIONS_DIR / filename

    if dry_run:
        return {
            "status": "dry_run",
            "adr_id": adr_id,
            "target_path": str(out_path.relative_to(ROOT)),
            "proposals_count": len(proposals),
            "preview": draft[:500],
        }

    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(draft, encoding="utf-8")
    return {
        "status": "created",
        "adr_id": adr_id,
        "path": str(out_path.relative_to(ROOT)),
        "proposals_count": len(proposals),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    result = convert(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
