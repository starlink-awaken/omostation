#!/usr/bin/env python3
"""Project and optionally observe dynamically discovered external resources.

The default command is a read-only bridge from Agora's discovery boundary to
human surfaces. ``--observe`` sends the safe projection through OMO's CLI
broker for append-only persistence; it never invokes provider business methods
or accepts credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA = "external-resource-catalog/v1"
DIRECTORY_SCHEMA = "external-resource-directory/v1"
CONNECTION_PLAN_SCHEMA = "external-resource-connection-plan/v1"
REFRESH_PLAN_SCHEMA = "external-resource-refresh-plan/v1"

DEFAULT_REFRESH_INTERVALS_SECONDS = {
    "knowledge_source": 86400,
    "data_source": 21600,
    "resource_provider": 3600,
    "method_pack": 604800,
    "tool_capability": 86400,
    "channel": 3600,
    "model_provider": 21600,
}


class ExternalResourceCatalogInputError(ValueError):
    """Raised when the catalog projection cannot be built safely."""


_OMO_COMMAND_TIMEOUT_SECONDS = 15
DEFAULT_CATALOG_TTL_SECONDS = 3600


def _canonical_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _directory_next_step(resource: Mapping[str, Any]) -> str:
    """Return a deterministic expansion action without mutating lifecycle state."""
    availability = str(resource.get("availability") or "").strip().lower()
    lifecycle = str(resource.get("lifecycle") or "").strip().lower()
    mode = str(resource.get("mode") or "").strip().lower()
    health = resource.get("health")
    health_status = str(health.get("status") or "").strip().lower() if isinstance(health, Mapping) else ""

    if availability in {"unavailable", "stale"} or health_status in {"unhealthy", "unknown", ""}:
        return "health_probe"
    if availability == "proposal_only" or mode == "proposal_only":
        return "proposal_or_evaluation"
    if lifecycle == "discovered":
        return "sandbox"
    if lifecycle == "sandbox":
        return "scene_card_and_permission_review"
    if lifecycle == "admitted":
        return "activation_review"
    if lifecycle == "degraded":
        return "health_recovery_or_quarantine"
    if lifecycle == "quarantined":
        return "quarantine_review"
    if lifecycle == "retired":
        return "retired"
    return "route_evaluation"


def build_external_resource_directory_snapshot(
    catalog: Mapping[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    """Build a capability-oriented, read-only projection from one catalog.

    The catalog remains the discovery truth. This projection only answers which
    capabilities are represented, their current safe availability, and the next
    governed expansion step; it never loads providers or changes lifecycle.
    """
    if catalog.get("schema") != SCHEMA:
        raise ExternalResourceCatalogInputError("directory requires an external-resource catalog")
    raw_resources = catalog.get("resources", [])
    if not isinstance(raw_resources, list):
        raise ExternalResourceCatalogInputError("catalog resources must be a list")

    resources: list[dict[str, Any]] = []
    capability_index: dict[str, dict[str, list[str]]] = {}
    kind_index: dict[str, list[str]] = {}
    next_steps: list[dict[str, str]] = []
    for item in raw_resources:
        if not isinstance(item, Mapping):
            raise ExternalResourceCatalogInputError("catalog resource must be an object")
        resource_id = str(item.get("id") or "").strip()
        if not resource_id:
            raise ExternalResourceCatalogInputError("catalog resource is missing id")
        capabilities = sorted(
            {str(capability).strip() for capability in item.get("capabilities", []) if str(capability).strip()}
        )
        availability = str(item.get("availability") or "unavailable").strip().lower()
        health = item.get("health") if isinstance(item.get("health"), Mapping) else {}
        resource = {
            "id": resource_id,
            "kind": str(item.get("kind") or "unknown"),
            "provider": str(item.get("provider") or "unknown"),
            "owner": str(item.get("owner") or ""),
            "capabilities": capabilities,
            "lifecycle": str(item.get("lifecycle") or "unknown"),
            "availability": availability,
            "mode": str(item.get("mode") or ""),
            "data_classification": str(item.get("data_classification") or ""),
            "permission_ref": str(item.get("permission_ref") or ""),
            "health": {
                "status": str(health.get("status") or "unknown"),
                "observed_at": health.get("observed_at"),
                "source": health.get("source"),
            },
            "reason_codes": sorted(
                {str(reason).strip() for reason in item.get("reason_codes", []) if str(reason).strip()}
            ),
            "next_step": _directory_next_step(item),
        }
        resources.append(resource)
        kind_index.setdefault(resource["kind"], []).append(resource_id)
        for capability in capabilities:
            bucket = capability_index.setdefault(
                capability, {"resource_ids": [], "available_resource_ids": []}
            )
            bucket["resource_ids"].append(resource_id)
            if availability == "available":
                bucket["available_resource_ids"].append(resource_id)
        next_steps.append({"resource_id": resource_id, "next_step": resource["next_step"]})

    for bucket in capability_index.values():
        bucket["resource_ids"].sort()
        bucket["available_resource_ids"].sort()
    for resource_ids in kind_index.values():
        resource_ids.sort()
    catalog_state = dict(catalog)
    catalog_state.pop("observed_at", None)
    directory = {
        "schema": DIRECTORY_SCHEMA,
        "mode": "read_only_projection",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": False,
        "admission_mutation": False,
        "observed_at": (now or datetime.now(UTC)).isoformat(),
        "catalog_digest": str(catalog.get("catalog_digest") or _canonical_digest(catalog_state)),
        "resources": resources,
        "capability_index": capability_index,
        "kind_index": kind_index,
        "next_steps": sorted(next_steps, key=lambda item: item["resource_id"]),
        "summary": {
            "resource_count": len(resources),
            "capability_count": len(capability_index),
            "kind_count": len(kind_index),
            "available_count": sum(item["availability"] == "available" for item in resources),
            "proposal_only_count": sum(item["availability"] == "proposal_only" for item in resources),
            "unavailable_count": sum(item["availability"] in {"unavailable", "stale"} for item in resources),
            "next_step_counts": {
                step: sum(item["next_step"] == step for item in next_steps)
                for step in sorted({item["next_step"] for item in next_steps})
            },
        },
        "catalog_errors": list(catalog.get("errors", [])) if isinstance(catalog.get("errors"), list) else [],
        "changes": catalog.get("changes") if isinstance(catalog.get("changes"), Mapping) else None,
        "policy": {
            "source": "external-resource-catalog/v1",
            "side_effects": "disabled",
            "next_step_semantics": "human_or_governed_review_only",
        },
    }
    digest_state = dict(directory)
    digest_state.pop("observed_at", None)
    directory["directory_digest"] = _canonical_digest(digest_state)
    return directory


def _connection_plan_item(resource: Mapping[str, Any]) -> dict[str, Any]:
    """Translate one directory item into a safe, deterministic connection step."""
    next_step = str(resource.get("next_step") or "route_evaluation")
    availability = str(resource.get("availability") or "unavailable")
    lifecycle = str(resource.get("lifecycle") or "unknown")
    blockers: list[str] = []
    required_inputs: list[str] = []
    if next_step == "health_probe":
        blockers.append("health_observation_required")
        required_inputs.append("health_probe")
    elif next_step in {"proposal_or_evaluation", "route_evaluation"}:
        blockers.extend(["scene_card_required", "policy_evaluation_required"])
        required_inputs.extend(["scene_card", "policy_evaluation"])
    elif next_step in {"sandbox", "scene_card_and_permission_review"}:
        blockers.extend(["scene_card_required", "permission_review_required"])
        required_inputs.extend(["scene_card", "permission_ref", "rollback_plan"])
    elif next_step == "activation_review":
        blockers.extend(["human_activation_review_required", "outcome_metric_required"])
        required_inputs.extend(["approver_ref", "outcome_metric", "rollback_plan"])
    elif next_step == "health_recovery_or_quarantine":
        blockers.append("health_recovery_or_quarantine_review_required")
        required_inputs.extend(["health_probe", "owner_ref", "rollback_plan"])
    elif next_step == "quarantine_review":
        blockers.append("quarantine_disposition_required")
        required_inputs.extend(["owner_ref", "review_ref"])
    elif next_step == "retired":
        blockers.append("retired_resource_is_not_routable")

    reviewable_steps = {
        "proposal_or_evaluation",
        "route_evaluation",
        "sandbox",
        "scene_card_and_permission_review",
        "activation_review",
    }
    status = (
        "ready_for_review"
        if availability == "available" and next_step in reviewable_steps
        else "blocked"
    )
    return {
        "resource_id": str(resource.get("id") or ""),
        "kind": str(resource.get("kind") or "unknown"),
        "provider": str(resource.get("provider") or "unknown"),
        "lifecycle": lifecycle,
        "availability": availability,
        "next_step": next_step,
        "status": status,
        "blockers": sorted(set(blockers)),
        "required_inputs": sorted(set(required_inputs)),
        "owner_ref": str(resource.get("owner") or ""),
        "permission_ref": str(resource.get("permission_ref") or ""),
    }


def build_external_resource_connection_plan(
    directory: Mapping[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    """Build a read-only connection plan from the capability directory.

    The plan makes extension work actionable without pretending that a
    connector is approved or executable. It contains only safe metadata and
    required evidence; OMO remains the sole owner of admission and runtime
    state.
    """
    if directory.get("schema") != DIRECTORY_SCHEMA:
        raise ExternalResourceCatalogInputError(
            "connection plan requires an external-resource directory"
        )
    raw_resources = directory.get("resources", [])
    if not isinstance(raw_resources, list):
        raise ExternalResourceCatalogInputError("directory resources must be a list")
    plan = [
        _connection_plan_item(item)
        for item in raw_resources
        if isinstance(item, Mapping)
    ]
    if len(plan) != len(raw_resources):
        raise ExternalResourceCatalogInputError("directory resource must be an object")
    plan.sort(key=lambda item: item["resource_id"])
    plan_state = {
        "schema": CONNECTION_PLAN_SCHEMA,
        "mode": "read_only_projection",
        "directory_digest": str(directory.get("directory_digest") or ""),
        "items": plan,
    }
    payload = {
        **plan_state,
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": False,
        "admission_mutation": False,
        "observed_at": (now or datetime.now(UTC)).isoformat(),
        "summary": {
            "resource_count": len(plan),
            "blocked_count": sum(item["status"] == "blocked" for item in plan),
            "ready_for_review_count": sum(
                item["status"] == "ready_for_review" for item in plan
            ),
            "next_step_counts": {
                step: sum(item["next_step"] == step for item in plan)
                for step in sorted({item["next_step"] for item in plan})
            },
        },
        "policy": {
            "source": DIRECTORY_SCHEMA,
            "side_effects": "disabled",
            "semantics": "evidence_collection_and_human_or_governed_review_only",
        },
    }
    digest_state = dict(payload)
    digest_state.pop("observed_at", None)
    payload["plan_digest"] = _canonical_digest(digest_state)
    return payload


def _parse_refresh_time(value: Any, *, field_name: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ExternalResourceCatalogInputError(f"refresh plan requires {field_name}")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExternalResourceCatalogInputError(
            f"refresh plan has invalid {field_name}"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def build_external_resource_refresh_plan(
    catalog: Mapping[str, Any],
    *,
    now: datetime | None = None,
    force: bool = False,
    intervals_seconds: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Build a read-only schedule for the next governed catalog observation.

    The plan controls observation cadence only. It never invokes a provider,
    queues a WorkflowRun, changes admission, or writes OMO state.
    """
    if catalog.get("schema") != SCHEMA:
        raise ExternalResourceCatalogInputError(
            "refresh plan requires an external-resource catalog"
        )
    raw_resources = catalog.get("resources", [])
    if not isinstance(raw_resources, list):
        raise ExternalResourceCatalogInputError("catalog resources must be a list")
    current = (now or datetime.now(UTC)).astimezone(UTC)
    policy = dict(DEFAULT_REFRESH_INTERVALS_SECONDS)
    if intervals_seconds is not None:
        for kind, interval in intervals_seconds.items():
            if kind not in policy:
                raise ExternalResourceCatalogInputError(
                    f"refresh plan has unknown resource kind: {kind}"
                )
            if not isinstance(interval, int) or isinstance(interval, bool) or interval <= 0:
                raise ExternalResourceCatalogInputError(
                    f"refresh plan interval must be positive: {kind}"
                )
            policy[kind] = interval

    items: list[dict[str, Any]] = []
    for item in raw_resources:
        if not isinstance(item, Mapping):
            raise ExternalResourceCatalogInputError("catalog resource must be an object")
        resource_id = str(item.get("id") or "").strip()
        if not resource_id:
            raise ExternalResourceCatalogInputError("catalog resource is missing id")
        kind = str(item.get("kind") or "").strip()
        interval = policy.get(kind, DEFAULT_REFRESH_INTERVALS_SECONDS["resource_provider"])
        health = item.get("health") if isinstance(item.get("health"), Mapping) else {}
        health_status = str(health.get("status") or "unknown").strip().lower()
        reason_codes = {
            str(reason).strip()
            for reason in item.get("reason_codes", [])
            if str(reason).strip()
        }
        last_observed_raw = health.get("observed_at") or catalog.get("observed_at")
        last_observed = _parse_refresh_time(
            last_observed_raw, field_name="observed_at"
        )
        next_due = last_observed + timedelta(seconds=interval)
        deadline_due = False
        invalid_deadline = False
        for field_name in ("expires_at", "review_at"):
            deadline = item.get(field_name)
            if not deadline:
                continue
            try:
                deadline_due = deadline_due or _parse_refresh_time(
                    deadline, field_name=field_name
                ) <= current
            except ExternalResourceCatalogInputError:
                invalid_deadline = True
        unhealthy = health_status in {"unknown", "unhealthy"} or any(
            reason in reason_codes
            for reason in ("health_stale", "provider_probe_failed")
        )
        if unhealthy:
            status = "due"
            priority = "urgent"
            action = "health_probe"
            reasons = sorted(reason_codes | {"health_recovery_due"})
        elif force:
            status = "due"
            priority = "normal"
            action = "catalog_refresh"
            reasons = sorted(reason_codes | {"forced_refresh"})
        elif invalid_deadline or deadline_due:
            status = "due"
            priority = "high"
            action = "human_review"
            reasons = sorted(reason_codes | ({"invalid_descriptor_deadline"} if invalid_deadline else {"descriptor_deadline_due"}))
        elif current >= next_due:
            status = "due"
            priority = "normal"
            action = "catalog_refresh"
            reasons = sorted(reason_codes | {"schedule_due"})
        else:
            status = "scheduled"
            priority = "low"
            action = "catalog_refresh"
            reasons = sorted(reason_codes)
        items.append(
            {
                "resource_id": resource_id,
                "kind": kind or "unknown",
                "provider": str(item.get("provider") or "unknown"),
                "status": status,
                "priority": priority,
                "action": action,
                "reason_codes": reasons,
                "last_observed_at": last_observed.isoformat(),
                "next_due_at": next_due.isoformat(),
                "interval_seconds": interval,
                "health_status": health_status,
                "availability": str(item.get("availability") or "unavailable"),
            }
        )
    items.sort(key=lambda item: (item["status"] != "due", item["priority"], item["resource_id"]))
    catalog_state = dict(catalog)
    catalog_state.pop("observed_at", None)
    catalog_digest = str(catalog.get("catalog_digest") or _canonical_digest(catalog_state))
    state = {
        "schema": REFRESH_PLAN_SCHEMA,
        "mode": "read_only_projection",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_creation": False,
        "admission_mutation": False,
        "worker_launch": False,
        "generated_at": current.isoformat(),
        "catalog_digest": catalog_digest,
        "force": force,
        "policy": {
            "intervals_seconds": dict(sorted(policy.items())),
            "unknown_kind_fallback_seconds": DEFAULT_REFRESH_INTERVALS_SECONDS["resource_provider"],
            "unhealthy_action": "health_probe",
            "deadline_action": "human_review",
        },
        "items": items,
        "summary": {
            "resource_count": len(items),
            "due_count": sum(item["status"] == "due" for item in items),
            "scheduled_count": sum(item["status"] == "scheduled" for item in items),
            "urgent_count": sum(item["priority"] == "urgent" for item in items),
            "high_count": sum(item["priority"] == "high" for item in items),
            "action_counts": {
                action: sum(item["action"] == action for item in items)
                for action in sorted({item["action"] for item in items})
            },
        },
        "policy_boundary": {
            "side_effects": "disabled",
            "scheduler": "caller_or_governed_observer_only",
            "automatic_activation": False,
        },
    }
    digest_state = dict(state)
    digest_state.pop("generated_at", None)
    state["plan_digest"] = _canonical_digest(digest_state)
    return state


def _load_agora(root: Path):
    agora_src = root / "projects/agora/src"
    if not agora_src.exists():
        raise ExternalResourceCatalogInputError(
            f"Agora source is unavailable: {agora_src}"
        )
    try:
        module_path = agora_src / "agora/external_connections.py"
        spec = importlib.util.spec_from_file_location(
            "agora_external_connections_projection", module_path
        )
        if spec is None or spec.loader is None:
            raise ImportError("cannot load Agora external connection boundary")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return (
            module.build_external_resource_catalog_snapshot,
            module.diff_external_resource_catalog_snapshots,
            module.discover_entry_points,
            module.evaluate_external_resource_catalog_snapshot,
        )
    except (ImportError, OSError) as exc:
        raise ExternalResourceCatalogInputError(
            "Agora external connection boundary is unavailable"
        ) from exc


def collect_external_resources(
    root: Path,
    *,
    entry_points: Iterable[Any] | None = None,
    now: datetime | None = None,
    health_ttl_seconds: int = 900,
    catalog_ttl_seconds: int = DEFAULT_CATALOG_TTL_SECONDS,
    probe: bool = True,
    previous_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect an external-resource snapshot through Agora's boundary."""
    root = root.resolve()
    build_snapshot, diff_snapshots, discover, _ = _load_agora(root)
    records = list(discover(entry_points, probe=probe, mark_unprobed=not probe))
    # iris 跨项目扫描: iris 连接器在 kairon 子模块注册 (21 个 external.resources),
    # 主仓库 omo/agora 环境装不到 iris → entry-point 发现断链;
    # 走 subprocess cd kairon + uv run 扫 external.resources (修复 iris↔catalog 断链, N1 解锁).
    records.extend(_load_iris_records(root))
    # BOS 能力目录: 总是加载 (修复回归: "if not records" 在 iris 进后跳过 bos 兜底,
    # 导致 catalog 丢 bos://capabilities). agora/iris 可能与 bos 重叠, 按 id 去重.
    records.extend(_load_capability_records(root))
    _seen_ids: set[str] = set()
    _deduped: list[Any] = []
    for _record in records:
        _rid = getattr(getattr(_record, "descriptor", None), "id", "") or ""
        if _rid and _rid in _seen_ids:
            continue
        if _rid:
            _seen_ids.add(_rid)
        _deduped.append(_record)
    records = _deduped
    snapshot = build_snapshot(
        records,
        now=now or datetime.now(UTC),
        health_ttl_seconds=health_ttl_seconds,
        catalog_ttl_seconds=catalog_ttl_seconds,
    )
    if snapshot.get("schema") != SCHEMA:
        raise ExternalResourceCatalogInputError("unexpected catalog schema")
    if previous_snapshot is not None:
        snapshot["changes"] = diff_snapshots(previous_snapshot, snapshot)
    return snapshot


def _load_iris_records(root: Path) -> list[Any]:
    """跨项目扫 iris external.resources (cd kairon + uv run), 转 DiscoveryRecord.

    iris 连接器在 kairon 子模块注册 (21 个 external.resources), 主仓库 omo/agora
    环境装不到 iris → metadata.entry_points() 发现断链. 走 subprocess 跨项目扫,
    修复 iris↔catalog 断链 (N1 document-review 激活卡点的根因).
    """
    kairon = root / "projects/kairon"
    if not kairon.exists():
        return []
    code = (
        "import importlib.metadata as m, json\n"
        "from datetime import datetime, timezone, timedelta\n"
        "for ep in m.entry_points(group='external.resources'):\n"
        "    if ep.name == 'agora-bos-capabilities':\n"
        "        continue\n"
        "    try:\n"
        "        inst = ep.load()()\n"
        "        desc = inst.external_descriptor()\n"
        "        try:\n"
        "            avail = inst.is_available()\n"
        "        except Exception:\n"
        "            avail = False\n"
        "        # iris health {available, details} → agora {status, observed_at, source}\n"
        "        # agora 要 status in {healthy, degraded, unhealthy} (不是 ok)\n"
        "        desc['health'] = {\n"
        "            'status': 'healthy' if avail else 'unhealthy',\n"
        "            'available': bool(avail),\n"
        "            'observed_at': datetime.now(timezone.utc).isoformat(),\n"
        "            'source': 'iris.is_available',\n"
        "        }\n"
        "        # agora 要 expires_at 或 review_at (否则 missing_expiry_or_review)\n"
        "        if not desc.get('expires_at') and not desc.get('review_at'):\n"
        "            desc['review_at'] = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()\n"
        "        # preflight 匹配 capability in resource.capabilities;\n"
        "        # scene capability_refs 用 resource id (iris:apple_mail), 加到 capabilities 让匹配\n"
        "        caps = list(desc.get('capabilities', []))\n"
        "        if desc.get('id') and desc['id'] not in caps:\n"
        "            caps.append(desc['id'])\n"
        "            desc['capabilities'] = caps\n"
        "        print(json.dumps(desc, ensure_ascii=False))\n"
        "    except Exception as e:\n"
        "        import sys; sys.stderr.write(f'iris skip {ep.name}: {e}\\n')\n"
    )
    try:
        result = subprocess.run(
            ["uv", "run", "--with", "pyyaml", "python", "-c", code],
            cwd=kairon,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(
            f"external-resource-catalog: iris scan unavailable: {exc}",
            file=sys.stderr,
        )
        return []
    from agora_external_connections_projection import (
        DiscoveryRecord as AgoraDiscoveryRecord,
    )
    from agora_external_connections_projection import ExternalResourceDescriptor

    records: list[Any] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            descriptor = json.loads(line)
            parsed = ExternalResourceDescriptor.from_mapping(descriptor)
            records.append(
                AgoraDiscoveryRecord(
                    descriptor=parsed,
                    entry_point=f"external.resources:{descriptor.get('id', 'iris')}",
                )
            )
        except (json.JSONDecodeError, ValueError, KeyError, AttributeError, TypeError) as exc:
            print(
                f"external-resource-catalog: iris descriptor skip: {exc}",
                file=sys.stderr,
            )
    return records


def _load_capability_records(root: Path) -> list[Any]:
    """importlib 加载 CapabilityProvider 并构造 DiscoveryRecord 列表。

    不依赖 agora 已安装 (entry-point 不可见时也能覆盖 BOS 能力目录)。
    """
    try:
        provider_path = (
            root
            / "projects/agora/src/agora/external_resources/capability_provider.py"
        )
        spec = importlib.util.spec_from_file_location(
            "agora_capability_provider_projection", provider_path
        )
        if spec is None or spec.loader is None:
            return []
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        descriptor = module.CapabilityProvider().external_descriptor()
        # bos health 适配 (agora availability 推导要 status/observed_at/source + review_at, 同 iris 模式)
        descriptor["health"] = {
            "status": "healthy",
            "observed_at": datetime.now(UTC).isoformat(),
            "source": "agora.capability_provider",
        }
        if not descriptor.get("expires_at") and not descriptor.get("review_at"):
            descriptor["review_at"] = (
                datetime.now(UTC) + timedelta(days=30)
            ).isoformat()
        # bos 能力目录 = BOS 服务聚合投影, 已 active (agora availability 要求 lifecycle in {active,degraded})
        descriptor["lifecycle"] = "active"
        # 复用 agora external_connections 的 DiscoveryRecord/解析 (已在 _load_agora 注册)
        from agora_external_connections_projection import (
            DiscoveryRecord as AgoraDiscoveryRecord,
        )
        from agora_external_connections_projection import (
            ExternalResourceDescriptor,
        )

        parsed = ExternalResourceDescriptor.from_mapping(descriptor)
        return [
            AgoraDiscoveryRecord(
                descriptor=parsed,
                entry_point="external.resources:agora-bos-capabilities",
            )
        ]
    except (ImportError, OSError, AttributeError) as exc:
        print(
            f"external-resource-catalog: capability fallback unavailable: {exc}",
            file=sys.stderr,
        )
        return []


def evaluate_external_resources(
    root: Path,
    snapshot: Mapping[str, Any],
    *,
    capability: str,
    scene_binding: Mapping[str, Any],
    trace_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate a safe catalog through Agora's shared decision contract."""
    root = root.resolve()
    _, _, _, evaluate_snapshot = _load_agora(root)
    return evaluate_snapshot(
        snapshot,
        capability,
        scene_binding,
        trace_id=trace_id,
        now=now or datetime.now(UTC),
    )


def _omo_command(root: Path, *args: str) -> list[str]:
    return [sys.executable, "-m", "omo.cli", *args]


def _omo_environment(root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    omo_src = str(root / "projects/omo/src")
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{omo_src}{os.pathsep}{existing}" if existing else omo_src
    )
    return environment


def _run_omo(
    root: Path, args: tuple[str, ...], *, input_text: str | None = None
) -> dict[str, Any]:
    completed = subprocess.run(
        _omo_command(root, *args),
        cwd=root,
        env=_omo_environment(root),
        input=input_text,
        capture_output=True,
        text=True,
        timeout=_OMO_COMMAND_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        raise ExternalResourceCatalogInputError(
            completed.stderr.strip() or "OMO external resource observer is unavailable"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ExternalResourceCatalogInputError(
            "OMO external resource observer returned invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise ExternalResourceCatalogInputError(
            "OMO external resource observer must return an object"
        )
    return payload


def observe_external_resources(
    root: Path,
    *,
    entry_points: Iterable[Any] | None = None,
    now: datetime | None = None,
    health_ttl_seconds: int = 900,
    catalog_ttl_seconds: int = DEFAULT_CATALOG_TTL_SECONDS,
    probe: bool = True,
    previous_snapshot: Mapping[str, Any] | None = None,
    actor: str = "external-resource-observer",
    source_ref: str = "root:external-resource-catalog:observe",
    run_id: str | None = None,
) -> dict[str, Any]:
    """Observe a safe catalog through OMO's brokered persistence boundary."""
    root = root.resolve()
    started_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    started_clock = time.perf_counter()
    if previous_snapshot is None:
        latest = _run_omo(root, ("external-resources", "latest", "--json"))
        previous_observation = latest.get("observation")
        if isinstance(previous_observation, Mapping):
            previous_snapshot = previous_observation.get("catalog")
    catalog = collect_external_resources(
        root,
        entry_points=entry_points,
        now=now,
        health_ttl_seconds=health_ttl_seconds,
        catalog_ttl_seconds=catalog_ttl_seconds,
        probe=probe,
        previous_snapshot=previous_snapshot,
    )
    result = _run_omo(
        root,
        (
            "external-resources",
            "observe",
            "--stdin",
            "--actor",
            actor,
            "--source-ref",
            source_ref,
        ),
        input_text=json.dumps(catalog, ensure_ascii=False, sort_keys=True),
    )
    observation = result.get("observation")
    if not isinstance(observation, Mapping):
        raise ExternalResourceCatalogInputError("OMO did not return an observation")
    resources = [item for item in catalog.get("resources", []) if isinstance(item, Mapping)]
    health_statuses = [
        str((item.get("health") or {}).get("status") or "").strip().lower()
        for item in resources
    ]
    availability = [str(item.get("availability") or "").strip().lower() for item in resources]
    probe_latencies = [
        float((item.get("health") or {}).get("latency_ms"))
        for item in resources
        if isinstance((item.get("health") or {}).get("latency_ms"), (int, float))
        and not isinstance((item.get("health") or {}).get("latency_ms"), bool)
    ]
    unavailable_count = sum(value in {"unavailable", "stale"} for value in availability)
    degraded_count = sum(
        value == "degraded" or health == "degraded"
        for value, health in zip(availability, health_statuses)
    )
    healthy_count = max(0, len(resources) - unavailable_count - degraded_count)
    errors = catalog.get("errors", [])
    error_count = len(errors) if isinstance(errors, list) else 0
    result_state = (
        "unavailable"
        if not resources
        else "degraded"
        if error_count or unavailable_count
        else "succeeded"
    )
    finished_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    catalog_digest = str(observation.get("catalog_digest") or "").strip()
    observation_run = _run_omo(
        root,
        ("external-resources", "record-observation-run", "--stdin"),
        input_text=json.dumps(
            {
                "schema": "external-resource-observation-run/v1",
                "run_id": run_id or f"external-observation-run:{catalog_digest[:32]}",
                "trace_id": f"external-observation:{catalog_digest[:24]}",
                "activation": "forbidden",
                "provider_business_invocation": False,
                "health_probe_invocation": probe,
                "started_at": started_at,
                "finished_at": finished_at,
                "catalog_observation_id": str(observation.get("observation_id") or ""),
                "catalog_digest": catalog_digest,
                "result_state": result_state,
                "summary": {
                    "resource_count": len(resources),
                    "healthy_count": healthy_count,
                    "degraded_count": degraded_count,
                    "unavailable_count": unavailable_count,
                    "error_count": error_count,
                    "probe_count": len(resources) if probe else 0,
                    "probe_failure_count": sum(
                        health in {"unhealthy", ""} or latency is None
                        for health, latency in zip(
                            health_statuses,
                            [
                                (item.get("health") or {}).get("latency_ms")
                                for item in resources
                            ],
                        )
                    )
                    if probe
                    else 0,
                },
                "latency": {
                    "duration_ms": round((time.perf_counter() - started_clock) * 1000, 3),
                    "probe_latency_ms_sum": round(sum(probe_latencies), 3) if probe_latencies else None,
                    "probe_latency_ms_max": round(max(probe_latencies), 3) if probe_latencies else None,
                },
                "cost": {
                    "state": "unmetered",
                    "amount": None,
                    "currency": "USD",
                    "basis": "catalog discovery and read-only health probes; provider billing not observed",
                },
                "actor": actor,
                "source_ref": source_ref,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
    return {
        "schema": "external-resource-observation-result/v1",
        "mode": "governed_observation",
        "catalog": catalog,
        "observation": observation,
        "observation_run": observation_run.get("receipt"),
        "status": result.get("status", "recorded"),
        "observation_run_status": observation_run.get("status", "recorded"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--health-ttl-seconds", type=int, default=900)
    parser.add_argument(
        "--catalog-ttl-seconds",
        type=int,
        default=DEFAULT_CATALOG_TTL_SECONDS,
        help="目录快照在进入 activation preflight 前的最大有效时长",
    )
    parser.add_argument(
        "--no-health-probe",
        action="store_true",
        help="只发现 descriptor，不调用显式只读 health_probe",
    )
    parser.add_argument(
        "--previous-snapshot",
        type=Path,
        help="读取上一份只读目录快照并附加变化报告，不写入任何状态",
    )
    parser.add_argument(
        "--observe",
        action="store_true",
        help="通过 OMO CLI broker 追加受治理观察记录",
    )
    parser.add_argument(
        "--directory",
        action="store_true",
        help="将只读目录转换为 capability directory，不执行观察或激活",
    )
    parser.add_argument(
        "--connection-plan",
        action="store_true",
        help="将 capability directory 转换为只读连接计划，不执行观察或激活",
    )
    parser.add_argument(
        "--refresh-plan",
        action="store_true",
        help="输出只读刷新计划，不执行观察、调度或激活",
    )
    parser.add_argument(
        "--force-refresh-plan",
        action="store_true",
        help="将所有资源标记为待刷新，仅影响只读计划输出",
    )
    parser.add_argument("--actor", default="external-resource-observer")
    parser.add_argument(
        "--source-ref", default="root:external-resource-catalog:observe"
    )
    parser.add_argument("--run-id", help="稳定的只读观察运行标识，用于重试幂等")
    args = parser.parse_args(argv)
    try:
        if args.observe and (args.directory or args.connection_plan or args.refresh_plan):
            raise ExternalResourceCatalogInputError(
                "projection flags cannot be combined with --observe"
            )
        if sum(bool(flag) for flag in (args.directory, args.connection_plan, args.refresh_plan)) > 1:
            raise ExternalResourceCatalogInputError(
                "--directory/--connection-plan/--refresh-plan are mutually exclusive"
            )
        previous_snapshot = None
        if args.previous_snapshot:
            try:
                previous_snapshot = json.loads(
                    args.previous_snapshot.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError) as exc:
                raise ExternalResourceCatalogInputError(
                    f"cannot read previous snapshot: {args.previous_snapshot}"
                ) from exc
        if args.observe:
            payload = observe_external_resources(
                args.root,
                health_ttl_seconds=args.health_ttl_seconds,
                catalog_ttl_seconds=args.catalog_ttl_seconds,
                probe=not args.no_health_probe,
                previous_snapshot=previous_snapshot,
                actor=args.actor,
                source_ref=args.source_ref,
                run_id=args.run_id,
            )
        else:
            catalog = collect_external_resources(
                args.root,
                health_ttl_seconds=args.health_ttl_seconds,
                catalog_ttl_seconds=args.catalog_ttl_seconds,
                probe=not args.no_health_probe,
                previous_snapshot=previous_snapshot,
            )
            directory = build_external_resource_directory_snapshot(catalog) if args.directory or args.connection_plan else None
            payload = (
                build_external_resource_connection_plan(directory)
                if args.connection_plan and directory is not None
                else directory
                if directory is not None
                else build_external_resource_refresh_plan(
                    catalog, force=args.force_refresh_plan
                )
                if args.refresh_plan
                else catalog
            )
    except (ExternalResourceCatalogInputError, ValueError) as exc:
        print(f"external-resource-catalog: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
