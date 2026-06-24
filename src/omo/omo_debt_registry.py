from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .omo_shared import load_yaml, load_yaml_required


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
    x1_policy_ref: str = ""
    x2_freshness: str = ""
    x3_tier: str = ""


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
    """Load debt ledger from the authoritative SSOT.

    P42 SSOT 同步纪元: `.omo/_truth/registry/debt.yaml` 是新 SSOT (authority),
    `.omo/debt/registry.yaml` 是历史兼容 fallback。优先读新 SSOT, fallback 老 SSOT。
    Missing item files 静默跳过 (不抛 FileNotFoundError),保持 ledger 韧性。
    """
    truth_registry = omo_dir / "_truth" / "registry" / "debt.yaml"
    legacy_registry = omo_dir / "debt" / "registry.yaml"

    if truth_registry.exists():
        registry_path = truth_registry
        registry_ref_str = ".omo/_truth/registry/debt.yaml"
    elif legacy_registry.exists():
        registry_path = legacy_registry
        registry_ref_str = ".omo/debt/registry.yaml"
    else:
        raise FileNotFoundError(
            f"No debt registry found at {truth_registry} or {legacy_registry}"
        )

    registry = load_yaml_required(registry_path)

    items: list[DebtItem] = []
    for item_ref in registry.get("seed_items", []):
        item_file = omo_dir.parent / item_ref
        if not item_file.exists():
            # 历史悬空引用: 跳过, 保持韧性
            continue
        payload = load_yaml(item_file)
        items.append(_parse_debt_item(payload))

    return DebtLedger(
        registry_ref=registry_ref_str,
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


def _as_tuple(value: object) -> tuple:
    """安全转 tuple: None→(), str→(str,), dict→keys, iterable→tuple, 标量→(value,)。"""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, dict):
        return tuple(value.keys())
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(value)
    return (value,)


def _parse_debt_item(payload: dict) -> DebtItem:
    """容错解析 debt item,兼容两套 schema:

    - 完整治理格式: dimension/subdimension/domain/scope/weight/entropy_class/...
    - 2026-06-08 简化格式: id/title/status/priority/category/...

    简化格式做字段映射(priority→severity, category→dimension, status→lifecycle_state,
    created/resolved→opened_at, affected_files→affected_roots),缺失字段给安全默认。
    单个脏/异构 item 不得崩掉整个健康同步(anti-fragile) —— 这正是 X-Plane 要根治的病。
    """
    severity = str(payload.get("severity") or payload.get("priority") or "P3")
    weight = payload.get("weight")
    return DebtItem(
        id=str(payload.get("id", "UNKNOWN")),
        title=str(payload.get("title", "")),
        dimension=str(payload.get("dimension") or payload.get("category") or "uncategorized"),
        subdimension=str(payload.get("subdimension", "")),
        domain=str(payload.get("domain") or payload.get("category") or ""),
        scope=str(payload.get("scope", "")),
        severity=severity,
        weight=float(weight) if weight is not None else 0.0,
        entropy_class=str(payload.get("entropy_class", "")),
        lifecycle_state=str(payload.get("lifecycle_state") or payload.get("status") or "active"),
        owner=str(payload.get("owner", "")),
        affected_roots=_as_tuple(payload.get("affected_roots") or payload.get("affected_files")),
        evidence_refs=_as_tuple(payload.get("evidence_refs")),
        mitigation_refs=_as_tuple(payload.get("mitigation_refs")),
        opened_at=str(payload.get("opened_at") or payload.get("created") or payload.get("resolved") or ""),
        last_reviewed_at=payload.get("last_reviewed_at"),
        next_review_at=payload.get("next_review_at"),
        gate_level=str(payload.get("gate_level", "")),
        history=_as_tuple(payload.get("history")),
        x1_policy_ref=str(payload.get("x1_policy_ref", "")),
        x2_freshness=str(payload.get("x2_freshness", "")),
        x3_tier=str(payload.get("x3_tier", "")),
    )
