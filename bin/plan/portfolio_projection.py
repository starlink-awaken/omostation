"""One-way Portfolio projections from Ledger truth (BET-Y1Q4-T1-08).

Computes canonical Goals / Markdown / control payloads sharing one Ledger
source digest. Repository Markdown may be applied directly. The two governed
``.omo`` destinations are broker-owned; this module never ``write_text``s them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

GOALS_REL = Path(".omo/goals/current.yaml")
CONTROL_REL = Path(".omo/_control/portfolio-status.json")
MARKDOWN_REL = Path("docs/plans/3Y-BET-PORTFOLIO.md")
LEDGER_REL = Path("docs/plans/3y-bet-ledger.yaml")
MUTATION_SURFACES_REL = Path(".omo/_truth/registry/mutation-surfaces.yaml")
REQUIRED_OMO_TARGETS = (str(GOALS_REL), str(CONTROL_REL))


@dataclass(frozen=True)
class ProjectionBundle:
    source_digest: str
    goals_bytes: bytes
    markdown_bytes: bytes
    control_bytes: bytes
    broker_ok: bool
    broker_reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_digest": self.source_digest,
            "broker_ok": self.broker_ok,
            "broker_reason": self.broker_reason,
            "goals_sha256": "sha256:" + hashlib.sha256(self.goals_bytes).hexdigest(),
            "markdown_sha256": "sha256:" + hashlib.sha256(self.markdown_bytes).hexdigest(),
            "control_sha256": "sha256:" + hashlib.sha256(self.control_bytes).hexdigest(),
        }


def source_digest(ledger_bytes: bytes) -> str:
    return "sha256:" + hashlib.sha256(ledger_bytes).hexdigest()


def discover_broker_targets(mutation_surfaces: dict[str, Any] | None) -> set[str]:
    """Return mutation_target paths declared as brokered in mutation-surfaces."""
    owned: set[str] = set()
    if not isinstance(mutation_surfaces, dict):
        return owned
    surfaces = (
        mutation_surfaces.get("surfaces")
        or mutation_surfaces.get("mutation_surfaces")
        or mutation_surfaces.get("entries")
        or []
    )
    for item in surfaces if isinstance(surfaces, list) else []:
        if not isinstance(item, dict):
            continue
        if not item.get("broker_ref"):
            continue
        if item.get("mode") not in {None, "brokered"}:
            continue
        target = item.get("mutation_target")
        if isinstance(target, str):
            for part in target.split("+"):
                owned.add(part.strip())
    return owned


def load_mutation_surfaces(workspace: Path) -> list[Any]:
    path = workspace / MUTATION_SURFACES_REL
    if not path.is_file():
        return []
    docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    return [d for d in docs if d is not None]


def broker_owns_portfolio_targets(workspace: Path) -> tuple[bool, str]:
    """Prove a registered broker owns BOTH governed .omo destinations."""
    owned: set[str] = set()
    for doc in load_mutation_surfaces(workspace):
        if isinstance(doc, list):
            owned |= discover_broker_targets({"surfaces": doc})
        elif isinstance(doc, dict):
            owned |= discover_broker_targets(doc)
            for key in ("surfaces", "mutation_surfaces", "entries", "items"):
                if isinstance(doc.get(key), list):
                    owned |= discover_broker_targets({"surfaces": doc[key]})
    missing = [t for t in REQUIRED_OMO_TARGETS if t not in owned]
    if missing:
        return False, f"PORTFOLIO_BROKER_OWNER_MISSING: missing={missing}"
    return True, "broker_ok"


def render_goals_payload(ledger: dict[str, Any], digest: str) -> bytes:
    objectives = ledger.get("objectives") or []
    milestones = ledger.get("milestones") or []
    campaigns = ledger.get("campaigns") or []
    vision = ledger.get("vision") if isinstance(ledger.get("vision"), dict) else {}
    payload = {
        "schema_version": "portfolio-goals-projection/v1",
        "source_digest": digest,
        "status": "projected",
        "vision_id": vision.get("id"),
        "objectives": [
            {
                "id": o.get("id"),
                "key_results": [
                    {"id": kr.get("id"), "status": kr.get("status")}
                    for kr in (o.get("key_results") or [])
                    if isinstance(kr, dict)
                ],
            }
            for o in objectives
            if isinstance(o, dict)
        ],
        "campaigns": [{"id": c.get("id")} for c in campaigns if isinstance(c, dict)],
        "milestones": [
            {
                "id": m.get("id"),
                "required_bets": list(m.get("required_bets") or []),
                "required_krs": list(m.get("required_krs") or []),
                "status": m.get("status"),
            }
            for m in milestones
            if isinstance(m, dict)
        ],
    }
    return yaml.safe_dump(payload, sort_keys=True, allow_unicode=True).encode("utf-8")


def render_control_payload(
    ledger: dict[str, Any],
    digest: str,
    *,
    broker_ok: bool,
    broker_reason: str,
) -> bytes:
    bets = ledger.get("bets") if isinstance(ledger.get("bets"), list) else []
    status_counts: dict[str, int] = {}
    for bet in bets:
        if not isinstance(bet, dict):
            continue
        st = str(bet.get("status") or "unknown")
        status_counts[st] = status_counts.get(st, 0) + 1
    payload: dict[str, Any] = {
        "schema_version": "portfolio-status-projection/v1",
        "source_digest": digest,
        "broker_ok": broker_ok,
        "status_counts": dict(sorted(status_counts.items())),
        "bet_count": len(bets),
        "vision_id": (ledger.get("vision") or {}).get("id") if isinstance(ledger.get("vision"), dict) else None,
    }
    if not broker_ok:
        payload["status"] = "unavailable"
        payload["unavailable_reason"] = broker_reason
        payload["targets"] = {
            str(GOALS_REL): "unavailable",
            str(CONTROL_REL): "unavailable",
        }
    else:
        payload["status"] = "projected"
        payload["targets"] = {
            str(GOALS_REL): "brokered",
            str(CONTROL_REL): "brokered",
        }
    return (json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def render_markdown(ledger: dict[str, Any], digest: str) -> bytes:
    vision = ledger.get("vision") if isinstance(ledger.get("vision"), dict) else {}
    lines = [
        "# 3Y BET Portfolio (projection)",
        "",
        f"<!-- source_digest: {digest} -->",
        "",
        "Generated one-way from `docs/plans/3y-bet-ledger.yaml`. Not a writer.",
        "",
        "## Vision",
        "",
        f"- id: `{vision.get('id')}`",
        "",
        "## Objectives / Key Results",
        "",
    ]
    for obj in ledger.get("objectives") or []:
        if not isinstance(obj, dict):
            continue
        lines.append(f"### {obj.get('id')}")
        lines.append("")
        for kr in obj.get("key_results") or []:
            if isinstance(kr, dict):
                lines.append(f"- `{kr.get('id')}` — status=`{kr.get('status')}`")
        lines.append("")
    lines.extend(["## Campaigns", ""])
    for c in ledger.get("campaigns") or []:
        if isinstance(c, dict):
            lines.append(f"- `{c.get('id')}`")
    lines.extend(["", "## Milestones", ""])
    for m in ledger.get("milestones") or []:
        if not isinstance(m, dict):
            continue
        lines.append(f"### {m.get('id')}")
        lines.append(f"- required_bets: {', '.join(m.get('required_bets') or [])}")
        lines.append(f"- required_krs: {', '.join(m.get('required_krs') or [])}")
        lines.append("")
    lines.extend(["## W0 Portfolio BETs", ""])
    w0 = {
        "BET-Y1Q4-T1-03",
        "BET-Y1Q4-T1-04",
        "BET-Y1Q4-T1-05",
        "BET-Y1Q4-T1-06",
        "BET-Y1Q4-T1-07",
        "BET-Y1Q4-T1-08",
        "BET-Y1Q4-T1-09",
        "BET-Y1Q4-T8-05",
    }
    for bet in ledger.get("bets") or []:
        if isinstance(bet, dict) and bet.get("id") in w0:
            lines.append(f"- `{bet.get('id')}` — `{bet.get('status')}` gate={bet.get('human_gate')}")
    lines.append("")
    return ("\n".join(lines)).encode("utf-8")


def build_bundle(ledger_bytes: bytes, workspace: Path) -> ProjectionBundle:
    ledger = yaml.safe_load(ledger_bytes)
    if not isinstance(ledger, dict):
        raise ValueError("PROJECTION_DRIFT: ledger must be a mapping")
    digest = source_digest(ledger_bytes)
    broker_ok, broker_reason = broker_owns_portfolio_targets(workspace)
    return ProjectionBundle(
        source_digest=digest,
        goals_bytes=render_goals_payload(ledger, digest),
        markdown_bytes=render_markdown(ledger, digest),
        control_bytes=render_control_payload(
            ledger, digest, broker_ok=broker_ok, broker_reason=broker_reason
        ),
        broker_ok=broker_ok,
        broker_reason=broker_reason,
    )


def assert_no_direct_omo_write(path: Path) -> None:
    """Raise if a caller attempts a direct write to governed .omo destinations."""
    rel = path.as_posix()
    for target in REQUIRED_OMO_TARGETS:
        if rel.endswith(target) or target in rel:
            raise PermissionError(f"PORTFOLIO_DIRECT_IO_FORBIDDEN: {target}")


def apply_markdown(workspace: Path, bundle: ProjectionBundle) -> Path:
    out = workspace / MARKDOWN_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bundle.markdown_bytes)
    return out


def apply_omo_via_broker(workspace: Path, bundle: ProjectionBundle) -> None:
    """Broker apply path. Halts when ownership is missing; never direct-writes."""
    if not bundle.broker_ok:
        raise SystemExit(bundle.broker_reason)
    # Ownership proven in a future amendment would invoke the broker here.
    raise SystemExit("PORTFOLIO_BROKER_APPLY_NOT_WIRED: ownership present but apply adapter not authorized in T1-08")


def check_bundle(workspace: Path, bundle: ProjectionBundle) -> list[str]:
    errors: list[str] = []
    # Markdown must match when present
    md = workspace / MARKDOWN_REL
    if md.is_file() and md.read_bytes() != bundle.markdown_bytes:
        errors.append("PROJECTION_DRIFT: markdown bytes differ")
    # Shared digest invariant across rendered payloads (always)
    digests = {
        yaml.safe_load(bundle.goals_bytes).get("source_digest"),
        json.loads(bundle.control_bytes).get("source_digest"),
    }
    if digests != {bundle.source_digest}:
        errors.append("PROJECTION_DRIFT: rendered payloads do not share source_digest")
    if f"source_digest: {bundle.source_digest}" not in bundle.markdown_bytes.decode("utf-8"):
        errors.append("PROJECTION_DRIFT: markdown missing source_digest")
    # Governed .omo destinations are only compared when broker ownership is proven.
    # Without ownership they remain unavailable; other ingress may own goals/current.yaml.
    if bundle.broker_ok:
        for rel, expected in (
            (GOALS_REL, bundle.goals_bytes),
            (CONTROL_REL, bundle.control_bytes),
        ):
            path = workspace / rel
            if path.is_file() and path.read_bytes() != expected:
                errors.append(f"PROJECTION_DRIFT: {rel} bytes differ")
    else:
        # portfolio-status.json must not be silently treated as healthy portfolio truth
        control = workspace / CONTROL_REL
        if control.is_file():
            try:
                payload = json.loads(control.read_text(encoding="utf-8"))
            except Exception:
                payload = None
            if isinstance(payload, dict) and payload.get("status") not in {None, "unavailable"}:
                if payload.get("source_digest") and payload.get("source_digest") != bundle.source_digest:
                    errors.append("PROJECTION_DRIFT: portfolio-status.json digest mismatch while broker missing")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portfolio one-way projections")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--ledger", default=str(LEDGER_REL))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--apply-markdown", action="store_true")
    parser.add_argument("--apply-omo", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    workspace = Path(args.workspace).resolve()
    ledger_path = workspace / args.ledger
    if not ledger_path.is_file():
        print("unavailable: ledger missing", file=sys.stderr)
        return 2
    ledger_bytes = ledger_path.read_bytes()
    bundle = build_bundle(ledger_bytes, workspace)

    if args.apply_omo:
        apply_omo_via_broker(workspace, bundle)

    if args.apply_markdown:
        apply_markdown(workspace, bundle)

    if args.check:
        errors = check_bundle(workspace, bundle)
        if errors:
            for e in errors:
                print(e)
            return 1
        if args.json:
            print(json.dumps({"ok": True, **bundle.as_dict()}, sort_keys=True))
        else:
            print(f"OK -- portfolio projections check (digest={bundle.source_digest})")
            if not bundle.broker_ok:
                print(f"INFO  {bundle.broker_reason}")
        return 0

    # default: emit summary
    if args.json:
        print(json.dumps(bundle.as_dict(), sort_keys=True, ensure_ascii=False))
    else:
        print(f"digest={bundle.source_digest} broker_ok={bundle.broker_ok}")
        if not bundle.broker_ok:
            print(bundle.broker_reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
