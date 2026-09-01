#!/usr/bin/env python3
"""Proposal intake — 进化提案→signal 草稿自动转换 (T2 / ADR-0443).

读 evolution-proposals/ 最新提案 JSON → 生成待人审 signal → 写入 signals/。
CLI 文件名保留兼容，但 draft 不再占 ADR 编号或写入 decisions/。

Usage:
  python3 bin/ssot/proposal-to-adr.py              # 转换最新提案
  python3 bin/ssot/proposal-to-adr.py --dry-run    # 预览不写入
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from _shared import ROOT

PROPOSALS_DIR = ROOT / ".omo" / "_knowledge" / "evolution-proposals"
# Compatibility boundary for callers/tests that still inspect the old target.
DECISIONS_DIR = ROOT / ".omo" / "_knowledge" / "decisions"
SIGNALS_DIR = ROOT / ".omo" / "_knowledge" / "signals"

# 提案采纳状态机 (BET-Y1Q3-T10-19): new → drafted → adopted → executed → verified
PROPOSAL_STATUSES = ["new", "drafted", "adopted", "executed", "verified"]
_PROPOSAL_RANK = {s: i for i, s in enumerate(PROPOSAL_STATUSES)}


def _read_status(proposal: dict) -> str:
    """读取提案状态; 历史无 status 字段视为 new."""
    status = proposal.get("status", "new")
    return status if status in _PROPOSAL_RANK else "new"


def _status_counts() -> dict[str, int]:
    """统计各状态提案数."""
    counts = {s: 0 for s in PROPOSAL_STATUSES}
    if not PROPOSALS_DIR.is_dir():
        return counts
    for path in PROPOSALS_DIR.glob("proposal-*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        counts[_read_status(data)] += 1
    return counts


def _latest_new_proposal() -> tuple[str, dict] | None:
    """返回 (filename_stem, proposal) 最新的 new 状态提案; 无则 None."""
    if not PROPOSALS_DIR.is_dir():
        return None
    for path in sorted(PROPOSALS_DIR.glob("proposal-*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if _read_status(data) == "new":
            return path.stem, data
    return None


def mark_status(proposal_id: str, status: str, *, dry_run: bool = False) -> dict:
    """推进指定提案状态 (枚举 + 迁移校验, 禁回退)."""
    if status not in _PROPOSAL_RANK:
        return {"status": "error", "reason": f"invalid status: {status} (allowed: {PROPOSAL_STATUSES})"}
    path = PROPOSALS_DIR / f"{proposal_id}.json"
    if not path.exists():
        return {"status": "error", "reason": f"proposal not found: {proposal_id}"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "error", "reason": f"unreadable proposal: {proposal_id}"}
    current = _read_status(data)
    if _PROPOSAL_RANK[status] < _PROPOSAL_RANK[current]:
        return {"status": "error", "reason": f"invalid transition {current}→{status} (no rewind)"}
    if dry_run:
        return {"status": "preview", "proposal_id": proposal_id, "from": current, "to": status}
    data["status"] = status
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {"status": "ok", "proposal_id": proposal_id, "from": current, "to": status}


def _latest_proposal() -> dict | None:
    """Load the most recent evolution proposal."""
    if not PROPOSALS_DIR.is_dir():
        return None
    files = sorted(PROPOSALS_DIR.glob("proposal-*.json"), reverse=True)
    if not files:
        return None
    return json.loads(files[0].read_text(encoding="utf-8"))


def _signal_id(proposal_id: str) -> str:
    safe = "-".join(part for part in proposal_id.lower().split("-") if part)
    return f"signal://evolution/{safe}"


def _generate_signal_draft(signal_id: str, proposal: dict) -> str:
    """Generate a non-decision signal draft from a proposal."""
    ts = datetime.now(UTC).strftime("%Y-%m-%d")
    proposals = proposal.get("proposals", [])

    # Pick the highest-priority proposal for the ADR title
    best = (
        max(
            proposals,
            key=lambda p: {"P0": 4, "P1": 3, "P2": 2, "P3": 1}.get(p.get("priority", str(p.get("level", "P3"))), 0),
        )
        if proposals
        else {}
    )

    title = best.get("proposal", "Evolution proposal")[:120]
    source = best.get("source", "unknown")
    level = best.get("level", "S3")

    body = f"""---
id: {signal_id}
status: draft
lifecycle: signal
owner: evolution-agent
last-reviewed: {ts}
---

# Signal: {title}

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

    body += """## Triage

_Pending human review. Auto-generated draft — do not merge without review._

## Consequences

- TBD (reviewer to fill)

## Follow-ups

- [ ] Human review
- [ ] Decision (accept/reject/defer)
"""
    return body


def convert(*, dry_run: bool = False) -> dict:
    """Convert latest `new` proposal to a signal draft, then mark it `drafted`."""
    found = _latest_new_proposal()
    if not found:
        return {"status": "noop", "reason": "no new proposals found", "status_counts": _status_counts()}
    proposal_id, proposal = found

    signal_id = _signal_id(proposal_id)
    draft = _generate_signal_draft(signal_id, proposal)

    # Slugify title for filename
    proposals = proposal.get("proposals", [])
    slug = "evolution-batch"
    if proposals:
        first_word = proposals[0].get("type", "proposal").replace("_", "-")[:30]
        slug = first_word

    filename = f"{proposal_id.lower()}-{slug}.md"
    out_path = SIGNALS_DIR / filename
    try:
        rel_path = str(out_path.relative_to(ROOT))
    except ValueError:
        rel_path = str(out_path)  # 测试/隔离路径下 fallback 绝对路径

    if dry_run:
        return {
            "status": "dry_run",
            "proposal_id": proposal_id,
            "signal_id": signal_id,
            "target_path": rel_path,
            "proposals_count": len(proposals),
            "preview": draft[:500],
            "status_counts": _status_counts(),
        }

    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(draft, encoding="utf-8")
    mark_status(proposal_id, "drafted")
    return {
        "status": "created",
        "proposal_id": proposal_id,
        "signal_id": signal_id,
        "path": rel_path,
        "proposals_count": len(proposals),
        "status_counts": _status_counts(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--mark-status",
        nargs=2,
        metavar=("PROPOSAL_ID", "STATUS"),
        help=f"推进指定提案状态 (allowed: {PROPOSAL_STATUSES})",
    )
    parser.add_argument("--list-status", action="store_true", help="打印各状态提案计数")
    args = parser.parse_args(argv)

    if args.list_status:
        result = {"status_counts": _status_counts()}
    elif args.mark_status:
        result = mark_status(args.mark_status[0], args.mark_status[1], dry_run=args.dry_run)
    else:
        result = convert(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
