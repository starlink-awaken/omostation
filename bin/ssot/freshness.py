#!/usr/bin/env python3
"""Canonical freshness-based health projection (W0-03).

Replaces stale static ``health`` text in signal-sources.yaml with a
deterministic derivation from **real source timestamps** and
**availability** (poller state).

Health states (deterministic, total order: healthy > degraded > unreachable > unknown):

    healthy     — source reachable AND last evidence within freshness window
    degraded    — source reachable BUT evidence is stale (beyond freshness window)
                  OR source reachable but no evidence ever recorded
    unreachable — poller reports source path unreachable / error
    unknown     — source never polled, no state to derive from

Freshness window = 2 × poll_interval (per signal-sources.yaml schema_contract).
This enforces the existing ``health_must_not`` contract:
    "healthy when last_signal_at is null or older than 2x poll_interval" = VIOLATION

Consumes data from existing surfaces — does NOT duplicate polling/scanning:
    - signal-sources.yaml (source config: poll_interval, last_signal_at)
    - signal-poller-state.json (availability: hash or "unreachable"/"error")
    - workflow-health.py output (CI workflow health)
    - project_health_check.py output (project governance health)

Usage:
    python3 bin/ssot/freshness.py [--json]
    python3 bin/ssot/freshness.py --source apple_mail_inbox
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from _shared import ROOT, load_yaml, utc_now

SIGNAL_SOURCES = ROOT / ".omo" / "_truth" / "registry" / "signal-sources.yaml"
POLLER_STATE = ROOT / ".omo" / "state" / "signal-poller-state.json"

# Freshness multiplier: 2x poll_interval per schema_contract.health_must_not
FRESHNESS_MULTIPLIER = 2

HealthStatus = Literal["healthy", "degraded", "unreachable", "unknown"]

# Poller hash values that indicate unreachability
_UNREACHABLE_HASHES = frozenset({"unreachable", "error"})


@dataclass
class HealthProjection:
    """Single-source health derivation result."""

    source_id: str
    status: HealthStatus
    last_signal_at: str | None
    age_seconds: float | None
    poll_interval_s: int
    freshness_window_s: int
    poller_hash: str | None
    reason: str
    derived_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_iso_timestamp(ts: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp (with Z or +00:00) to aware datetime."""
    if not ts:
        return None
    try:
        # Handle 'Z' suffix
        clean = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def _parse_duration(duration_str: str) -> int:
    """Parse duration like '300s', '60s', '1h', '24h' into seconds."""
    if not duration_str:
        return 300  # sensible default
    s = duration_str.strip().lower()
    for unit, multiplier in [("h", 3600), ("m", 60), ("s", 1)]:
        if s.endswith(unit):
            try:
                return int(s[:-1]) * multiplier
            except ValueError:
                pass
    # Bare number = seconds
    try:
        return int(s)
    except ValueError:
        return 300


def derive_health(
    source_id: str,
    last_signal_at: str | None,
    poller_hash: str | None,
    poll_interval_s: int = 300,
    *,
    now: datetime | None = None,
) -> HealthProjection:
    """Derive health status from real timestamps and availability.

    This is the **canonical** derivation — all health projections must
    route through here. Deterministic: same inputs always produce same
    status.

    Args:
        source_id: signal source identifier
        last_signal_at: ISO-8601 timestamp of last real signal, or None
        poller_hash: hash from signal-poller-state.json
                     (actual hash = reachable, "unreachable"/"error" = down,
                      None = never polled)
        poll_interval_s: expected poll interval in seconds
        now: override current time (for testing)

    Returns:
        HealthProjection with deterministic status and human-readable reason

    Derivation rules (checked in order, first match wins):
        1. poller_hash in {"unreachable", "error"}  → unreachable
        2. poller_hash is None (never polled)       → unknown
        3. last_signal_at is None                   → degraded (reachable, no evidence)
        4. age <= freshness_window (2× poll_interval) → healthy
        5. age > freshness_window                    → degraded (stale evidence)
    """
    if now is None:
        now = datetime.now(UTC)

    freshness_window_s = poll_interval_s * FRESHNESS_MULTIPLIER
    derived_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    # Rule 1: poller explicitly reports unreachable/error
    if poller_hash in _UNREACHABLE_HASHES:
        return HealthProjection(
            source_id=source_id,
            status="unreachable",
            last_signal_at=last_signal_at,
            age_seconds=None,
            poll_interval_s=poll_interval_s,
            freshness_window_s=freshness_window_s,
            poller_hash=poller_hash,
            reason=f"poller reports '{poller_hash}' for source path",
            derived_at=derived_at,
        )

    # Rule 2: never polled — no data to derive from
    if poller_hash is None:
        return HealthProjection(
            source_id=source_id,
            status="unknown",
            last_signal_at=last_signal_at,
            age_seconds=None,
            poll_interval_s=poll_interval_s,
            freshness_window_s=freshness_window_s,
            poller_hash=poller_hash,
            reason="no poller state — source never polled",
            derived_at=derived_at,
        )

    # Source is reachable (poller_hash is a real hash).
    # Now check freshness of evidence.

    last_signal_dt = _parse_iso_timestamp(last_signal_at)
    if last_signal_dt is None:
        # Rule 3: reachable but no signal ever recorded
        return HealthProjection(
            source_id=source_id,
            status="degraded",
            last_signal_at=last_signal_at,
            age_seconds=None,
            poll_interval_s=poll_interval_s,
            freshness_window_s=freshness_window_s,
            poller_hash=poller_hash,
            reason="source reachable but no signal ever recorded (last_signal_at is null or unparseable)",
            derived_at=derived_at,
        )

    age_seconds = (now - last_signal_dt).total_seconds()

    # Rule 4: fresh evidence within window
    if age_seconds <= freshness_window_s:
        return HealthProjection(
            source_id=source_id,
            status="healthy",
            last_signal_at=last_signal_at,
            age_seconds=age_seconds,
            poll_interval_s=poll_interval_s,
            freshness_window_s=freshness_window_s,
            poller_hash=poller_hash,
            reason=f"fresh evidence: age {age_seconds:.0f}s <= window {freshness_window_s}s",
            derived_at=derived_at,
        )

    # Rule 5: stale evidence beyond window
    return HealthProjection(
        source_id=source_id,
        status="degraded",
        last_signal_at=last_signal_at,
        age_seconds=age_seconds,
        poll_interval_s=poll_interval_s,
        freshness_window_s=freshness_window_s,
        poller_hash=poller_hash,
        reason=f"stale evidence: age {age_seconds:.0f}s > window {freshness_window_s}s",
        derived_at=derived_at,
    )


def _load_poller_state() -> dict[str, str]:
    """Load signal-poller-state.json (availability data)."""
    if POLLER_STATE.exists():
        try:
            return json.loads(POLLER_STATE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def project_all_health(
    *,
    now: datetime | None = None,
    sources: list[dict[str, Any]] | None = None,
    poller_state: dict[str, str] | None = None,
) -> list[HealthProjection]:
    """Project health for ALL registered signal sources.

    Consumes:
        - signal-sources.yaml for source config (poll_interval, last_signal_at)
        - signal-poller-state.json for availability (hashes)

    Args:
        now: override current time (for testing)
        sources: inject source list (skip disk read; for testing)
        poller_state: inject poller state dict (skip disk read; for testing)

    Returns:
        List of HealthProjection, one per registered source.
    """
    if now is None:
        now = datetime.now(UTC)

    if sources is None:
        data = load_yaml(SIGNAL_SOURCES)
        sources = data.get("sources", [])
    if poller_state is None:
        poller_state = _load_poller_state()

    resolved_sources: list[dict[str, Any]] = sources or []
    resolved_state: dict[str, str] = poller_state or {}

    projections: list[HealthProjection] = []
    for src in resolved_sources:
        source_id = src.get("id", "?")
        poll_interval_s = _parse_duration(src.get("poll_interval", "300s"))
        last_signal_at = src.get("last_signal_at")
        # poller state key matches source_id
        poller_hash = resolved_state.get(source_id)

        proj = derive_health(
            source_id=source_id,
            last_signal_at=last_signal_at,
            poller_hash=poller_hash,
            poll_interval_s=poll_interval_s,
            now=now,
        )
        projections.append(proj)

    return projections


def validate_health_contract(
    projections: list[HealthProjection],
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check static health labels against derived health.

    Returns list of violations where the static ``health`` field in
    signal-sources.yaml disagrees with the freshness-derived status.

    A violation occurs when:
        - static says "healthy" but derived is NOT healthy
        - static says any status but derived differs (warning-level)
    """
    source_map = {s.get("id"): s for s in sources}
    violations: list[dict[str, Any]] = []

    for proj in projections:
        src = source_map.get(proj.source_id, {})
        static_health = src.get("health", "unknown")

        if static_health == "healthy" and proj.status != "healthy":
            violations.append({
                "source_id": proj.source_id,
                "static_health": static_health,
                "derived_health": proj.status,
                "severity": "critical",
                "rule": "health_must_not: healthy requires fresh evidence",
                "reason": proj.reason,
            })
        elif static_health != proj.status and static_health != "unknown":
            violations.append({
                "source_id": proj.source_id,
                "static_health": static_health,
                "derived_health": proj.status,
                "severity": "warning",
                "rule": "health_label_drift",
                "reason": proj.reason,
            })

    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true",
        help="JSON output (for healthcheck consumption)",
    )
    parser.add_argument(
        "--source", type=str, default=None,
        help="Show health for a single source",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Validate static health labels against derived health",
    )
    args = parser.parse_args(argv)

    projections = project_all_health()

    if args.source:
        projections = [p for p in projections if p.source_id == args.source]
        if not projections:
            print(f"[ERROR] source not found: {args.source}", file=sys.stderr)
            return 1

    if args.validate:
        data = load_yaml(SIGNAL_SOURCES)
        sources = data.get("sources", [])
        violations = validate_health_contract(projections, sources)
        if args.json:
            print(json.dumps({
                "violations": len(violations),
                "data": violations,
            }, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            if not violations:
                print("✅ all static health labels match derived health")
            else:
                print(f"❌ {len(violations)} health label violations:\n")
                for v in violations:
                    icon = "🔴" if v["severity"] == "critical" else "🟡"
                    print(f"{icon} {v['source_id']}: static={v['static_health']} → derived={v['derived_health']}")
                    print(f"   {v['reason']}")
        return 1 if violations else 0

    if args.json:
        output = {
            "derived_at": utc_now(),
            "sources": [p.to_dict() for p in projections],
            "summary": {
                "total": len(projections),
                "healthy": sum(1 for p in projections if p.status == "healthy"),
                "degraded": sum(1 for p in projections if p.status == "degraded"),
                "unreachable": sum(1 for p in projections if p.status == "unreachable"),
                "unknown": sum(1 for p in projections if p.status == "unknown"),
            },
        }
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    # Human-readable table
    print(f"{'Source':<30} {'Status':<12} {'Age':<12} {'Reason'}")
    print("-" * 90)
    for p in projections:
        age_str = f"{p.age_seconds:.0f}s" if p.age_seconds is not None else "—"
        icon = {
            "healthy": "✅",
            "degraded": "⚠️ ",
            "unreachable": "🔴",
            "unknown": "❓",
        }.get(p.status, "  ")
        print(f"{p.source_id:<30} {icon}{p.status:<10} {age_str:<12} {p.reason}")

    print()
    summary = {
        "healthy": sum(1 for p in projections if p.status == "healthy"),
        "degraded": sum(1 for p in projections if p.status == "degraded"),
        "unreachable": sum(1 for p in projections if p.status == "unreachable"),
        "unknown": sum(1 for p in projections if p.status == "unknown"),
    }
    print(f"Summary: {summary['healthy']} healthy, {summary['degraded']} degraded, "
          f"{summary['unreachable']} unreachable, {summary['unknown']} unknown")

    # Exit 0: degraded health is not a command error, only real errors return nonzero.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
