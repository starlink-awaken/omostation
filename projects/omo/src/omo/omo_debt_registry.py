from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DebtItem:
    id: str
    title: str
    dimension: str
    subdimension: str
    domain: str
    scope: str
    severity: str
    weight: float
    entropy_class: str
    lifecycle_state: str
    owner: str
    affected_roots: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    mitigation_refs: tuple[str, ...]
    opened_at: str
    last_reviewed_at: str | None
    next_review_at: str | None
    gate_level: str
    history: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class DebtLedger:
    registry_ref: str
    dashboard_ref: str
    review_pack_ref: str
    review_queue_ref: str
    action_packet_ref: str
    owner_routing_ref: str
    dispatch_ref: str
    campaign_ref: str
    reporting_ref: str
    items: tuple[DebtItem, ...]


def load_debt_ledger(omo_dir: Path) -> DebtLedger:
    registry_path = omo_dir / "debt" / "registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))

    items: list[DebtItem] = []
    for item_ref in registry["seed_items"]:
        payload = yaml.safe_load(
            (omo_dir.parent / item_ref).read_text(encoding="utf-8")
        )
        items.append(
            DebtItem(
                id=payload["id"],
                title=payload["title"],
                dimension=payload["dimension"],
                subdimension=payload["subdimension"],
                domain=payload["domain"],
                scope=payload["scope"],
                severity=payload["severity"],
                weight=float(payload["weight"]),
                entropy_class=payload["entropy_class"],
                lifecycle_state=payload["lifecycle_state"],
                owner=payload["owner"],
                affected_roots=tuple(payload["affected_roots"]),
                evidence_refs=tuple(payload["evidence_refs"]),
                mitigation_refs=tuple(payload["mitigation_refs"]),
                opened_at=payload["opened_at"],
                last_reviewed_at=payload.get("last_reviewed_at"),
                next_review_at=payload.get("next_review_at"),
                gate_level=payload["gate_level"],
                history=tuple(payload.get("history", [])),
            )
        )

    return DebtLedger(
        registry_ref=".omo/debt/registry.yaml",
        dashboard_ref=registry["dashboard_ref"],
        review_pack_ref=registry["review_pack_ref"],
        review_queue_ref=registry["review_queue_ref"],
        action_packet_ref=registry["action_packet_ref"],
        owner_routing_ref=registry["owner_routing_ref"],
        dispatch_ref=registry["dispatch_ref"],
        campaign_ref=registry["campaign_ref"],
        reporting_ref=registry["reporting_ref"],
        items=tuple(items),
    )
