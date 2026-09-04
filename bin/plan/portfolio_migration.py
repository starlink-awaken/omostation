"""Pure Portfolio v2 legacy-BET classification manifest (BET-Y1Q4-T1-07).

Read-only over Ledger bytes / in-memory objects. Never mutates the source
Ledger. ``--apply`` is unconditionally rejected in this delivery.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

DISPOSITIONS = frozenset({"reuse", "continue", "merge", "defer", "stop"})
TERMINAL = frozenset({"done", "failed"})
BLOCKED = frozenset({"blocked"})
W0_IDS = frozenset(
    {
        "BET-Y1Q4-T1-03",
        "BET-Y1Q4-T1-04",
        "BET-Y1Q4-T1-05",
        "BET-Y1Q4-T1-06",
        "BET-Y1Q4-T1-07",
        "BET-Y1Q4-T1-08",
        "BET-Y1Q4-T1-09",
        "BET-Y1Q4-T8-05",
    }
)


@dataclass(frozen=True)
class ClassificationRow:
    bet_id: str
    status: str | None
    disposition: str
    rationale: str
    source_digest: str


@dataclass(frozen=True)
class MigrationManifest:
    schema_version: str
    source_digest: str
    bet_count: int
    rows: tuple[ClassificationRow, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_digest": self.source_digest,
            "bet_count": self.bet_count,
            "rows": [asdict(r) for r in self.rows],
        }


def source_digest(ledger_bytes: bytes) -> str:
    return "sha256:" + hashlib.sha256(ledger_bytes).hexdigest()


def inventory(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    bets = ledger.get("bets")
    if not isinstance(bets, list):
        raise ValueError("MIGRATION_SCOPE_DRIFT: bets must be a list")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, bet in enumerate(bets):
        if not isinstance(bet, dict):
            raise ValueError(f"MIGRATION_SCOPE_DRIFT: bets[{idx}] not a mapping")
        bet_id = bet.get("id")
        if not isinstance(bet_id, str) or not bet_id:
            raise ValueError(f"MIGRATION_SCOPE_DRIFT: bets[{idx}] missing id")
        if bet_id in seen:
            raise ValueError(f"MIGRATION_SCOPE_DRIFT: duplicate id {bet_id}")
        seen.add(bet_id)
        out.append(bet)
    return out


def classify(entry: dict[str, Any]) -> tuple[str, str]:
    """Return (disposition, rationale) for one BET entry."""
    bet_id = str(entry.get("id") or "")
    status = entry.get("status")
    status_s = status if isinstance(status, str) else None

    if status_s in TERMINAL:
        return (
            "reuse",
            "terminal historical delivery retained as prerequisite reference; no rewrite",
        )
    if status_s in BLOCKED:
        return (
            "defer",
            "blocked object preserved unchanged; resume only under separate authorization",
        )
    if bet_id in W0_IDS:
        return (
            "continue",
            "active W0 Portfolio v2 child/parent; continue under campaign CMP-W0-PORTFOLIO-TRUTH",
        )
    # Default for other non-terminal: defer until funded Milestone mapping exists.
    if status_s in {"candidate", "pending", "in_progress", "review"}:
        return (
            "defer",
            "non-terminal outside W0 campaign; defer pending separately authorized Milestone mapping",
        )
    # Malformed / unknown status still receives exactly one disposition.
    return (
        "stop",
        "unrecognized or missing status; requires explicit closure review before any mutation",
    )


def render_manifest(entries: list[dict[str, Any]], digest: str) -> MigrationManifest:
    rows: list[ClassificationRow] = []
    for entry in entries:
        disposition, rationale = classify(entry)
        if disposition not in DISPOSITIONS:
            raise ValueError(f"MIGRATION_SCOPE_DRIFT: invalid disposition for {entry.get('id')}")
        rows.append(
            ClassificationRow(
                bet_id=str(entry["id"]),
                status=entry.get("status") if isinstance(entry.get("status"), str) else None,
                disposition=disposition,
                rationale=rationale,
                source_digest=digest,
            )
        )
    rows_sorted = tuple(sorted(rows, key=lambda r: r.bet_id))
    return MigrationManifest(
        schema_version="bet-portfolio-migration-manifest/v1",
        source_digest=digest,
        bet_count=len(rows_sorted),
        rows=rows_sorted,
    )


def build_manifest_from_bytes(ledger_bytes: bytes) -> MigrationManifest:
    ledger = yaml.safe_load(ledger_bytes)
    if not isinstance(ledger, dict):
        raise ValueError("MIGRATION_SCOPE_DRIFT: ledger must be a mapping")
    digest = source_digest(ledger_bytes)
    return render_manifest(inventory(ledger), digest)


def reject_apply() -> None:
    raise SystemExit("MIGRATION_APPLY_NOT_AUTHORIZED")


def reject_batch_size(n: int) -> None:
    if n > 8:
        raise SystemExit("MIGRATION_SCOPE_DRIFT: batch exceeds 8 objects")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portfolio v2 legacy BET migration manifest")
    parser.add_argument("--ledger", default="docs/plans/3y-bet-ledger.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Emit manifest; never mutate")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--yaml", action="store_true", dest="yaml_out", help="YAML output")
    parser.add_argument("--apply", action="store_true", help="Rejected in this delivery")
    parser.add_argument("--write-manifest", default="", help="Optional output path (dry-run only)")
    args = parser.parse_args(argv)

    if args.apply:
        reject_apply()

    if not args.dry_run and not args.write_manifest:
        # Default to dry-run semantics for safety.
        args.dry_run = True

    path = Path(args.ledger)
    ledger_bytes = path.read_bytes()
    before = ledger_bytes
    manifest = build_manifest_from_bytes(ledger_bytes)
    after = path.read_bytes()
    if after != before:
        raise SystemExit("PORTFOLIO_CONCURRENT_UPDATE: ledger mutated during dry-run")

    payload = manifest.to_dict()
    if args.yaml_out and not args.json:
        text = yaml.safe_dump(payload, sort_keys=True, allow_unicode=True)
    else:
        text = json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"

    if args.write_manifest:
        out = Path(args.write_manifest)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        # Re-check source unchanged
        if path.read_bytes() != before:
            raise SystemExit("PORTFOLIO_CONCURRENT_UPDATE: ledger mutated while writing manifest")

    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
