"""omo_ingress registry 基础设施 (从 God Module 拆出, SRP · P60+ 第二步).

_load_registry / _write_registry / _record_mutation / _register_ingress.
操作 .omo/_delivery/ingress/registry.yaml + change-log/mutations.jsonl.
被 omo_ingress.py (治理 broker 入口) 复用.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from omo.omo_io import AppendOnlyLog, write_yaml_atomic
from omo.omo_ingress_paths import (
    _load_yaml,
    _mutation_log_path,
    _registry_path,
    _utc_now,
)


def _load_registry(omo_dir: Path) -> dict[str, Any]:
    path = _registry_path(omo_dir)
    if not path.exists():
        return {
            "goals": {"by_id": {}, "by_source_ref": {}},
            "tasks": {"by_id": {}, "by_source_ref": {}},
            "debts": {"by_id": {}, "by_source_ref": {}},
            "capabilities": {"by_id": {}, "by_source_ref": {}},
        }
    data = _load_yaml(path)
    for key in ("goals", "tasks", "debts", "capabilities"):
        data.setdefault(key, {})
        data[key].setdefault("by_id", {})
        data[key].setdefault("by_source_ref", {})
    return data


def _write_registry(omo_dir: Path, registry: dict[str, Any]) -> None:
    write_yaml_atomic(_registry_path(omo_dir), registry)


def _record_mutation(
    omo_dir: Path,
    *,
    actor: str,
    action: str,
    target: str,
    artifact_ref: str,
    source_ref: str,
    broker_ref: str = "projects/omo/src/omo/omo_ingress.py",
    created_at: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    record: dict[str, Any] = {
        "created_at": created_at or _utc_now(),
        "actor": actor,
        "action": action,
        "target": target,
        "artifact_ref": artifact_ref,
        "source_ref": source_ref,
        "broker_ref": broker_ref,
        "result": "committed",
    }
    if extra:
        record.update(deepcopy(extra))
    AppendOnlyLog(_mutation_log_path(omo_dir)).append(record, sort_keys=False)


def _register_ingress(
    registry: dict[str, Any],
    *,
    kind: str,
    item_id: str,
    source_ref: str,
    artifact_ref: str,
    fingerprint: dict[str, Any],
    created_at: str,
) -> None:
    bucket = registry[kind]
    bucket["by_id"][item_id] = {
        "source_ref": source_ref,
        "artifact_ref": artifact_ref,
        "fingerprint": deepcopy(fingerprint),
        "created_at": created_at,
    }
    if source_ref:
        bucket["by_source_ref"][source_ref] = item_id
