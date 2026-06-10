from __future__ import annotations

import argparse
from pathlib import Path

from .omo_debt_registry import DebtItem

def append_history(
    payload: dict, action: str, note: str, actor: str = "", timestamp: str = ""
) -> None:
    entry: dict[str, str] = {
        "at": timestamp,
        "action": action,
        "note": note,
    }
    if actor:
        entry["actor"] = actor
    payload.setdefault("history", []).append(entry)


def register_item(args: argparse.Namespace, timestamp: str) -> dict:
    payload = {
        "id": args.id,
        "title": args.title,
        "dimension": args.dimension,
        "subdimension": args.subdimension,
        "domain": "workspace",
        "scope": "governance_kernel",
        "severity": args.severity,
        "weight": 0.05,
        "entropy_class": "classification",
        "lifecycle_state": "identified",
        "owner": args.owner,
        "affected_roots": [".omo"],
        "evidence_refs": [],
        "mitigation_refs": [],
        "opened_at": timestamp,
        "last_reviewed_at": None,
        "next_review_at": None,
        "gate_level": "none",
        "history": [],
        "x1_policy_ref": getattr(args, "x1_policy_ref", ""),
        "x2_freshness": getattr(args, "x2_freshness", ""),
        "x3_tier": getattr(args, "x3_tier", ""),
    }
    actor = getattr(args, "actor", "")
    append_history(
        payload, "register", f"Registered debt item {args.id}.", actor=actor, timestamp=timestamp
    )
    return payload


def append_registry_ref(omo_dir: Path, item_ref: str, _load_yaml, _write_yaml) -> None:
    registry_path = omo_dir / "_truth" / "registry" / "debt.yaml"
    registry = _load_yaml(registry_path)
    refs = list(registry.get("seed_items", []))
    if item_ref not in refs:
        refs.append(item_ref)
    registry["seed_items"] = refs
    _write_yaml(registry_path, registry)


def schedule_item(omo_dir: Path, item_id: str, next_review_at: str, _load_yaml, _write_yaml, timestamp: str) -> None:
    item_path = omo_dir / "debt" / "items" / f"{item_id}.yaml"
    payload = _load_yaml(item_path)
    payload["lifecycle_state"] = "scheduled"
    payload["next_review_at"] = next_review_at
    append_history(payload, "schedule", f"Next review set to {next_review_at}.", timestamp=timestamp)
    _write_yaml(item_path, payload)


def update_item(omo_dir: Path, item_id: str, _load_yaml) -> tuple[Path, dict]:
    item_path = omo_dir / "debt" / "items" / f"{item_id}.yaml"
    return item_path, _load_yaml(item_path)


def classify_review_sections(items: tuple[DebtItem, ...]) -> dict[str, list[str]]:
    sections = {
        "newly_registered": [],
        "closed": [],
        "drifted": [],
        "escalated": [],
        "reopened": [],
    }
    for item in items:
        actions = [entry["action"] for entry in item.history]
        if "register" in actions:
            sections["newly_registered"].append(item.id)
        if "close" in actions or item.lifecycle_state == "closed":
            sections["closed"].append(item.id)
        if (
            item.entropy_class in {"pointer", "time"}
            and item.lifecycle_state != "closed"
        ):
            sections["drifted"].append(item.id)
        if "escalate" in actions or item.gate_level == "gate":
            sections["escalated"].append(item.id)
        if "reopen" in actions:
            sections["reopened"].append(item.id)
    return sections
