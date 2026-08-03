from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .omo_io import write_text_atomic, write_text_if_changed
from .omo_shared import load_yaml


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_yaml(path: Path) -> dict[str, Any]:
    return load_yaml(path)


def build_governance_data(workspace_root: Path) -> dict[str, Any]:
    omo_dir = workspace_root / ".omo"
    system_path = omo_dir / "state" / "system.yaml"
    dashboard_path = omo_dir / "_control" / "debt-dashboard" / "current.yaml"
    if not system_path.exists():
        raise FileNotFoundError(f"missing system state: {system_path}")

    system_data = _load_yaml(system_path)
    dashboard_data = _load_yaml(dashboard_path) if dashboard_path.exists() else {}
    governance_data = {
        "version": "1.0",
        "generated_at": _now_iso(),
        "governance": {
            "health_score": system_data.get("health_score", 0),
            "health_score_raw": system_data.get("health_score_raw", 100),
            "debt_weight": system_data.get("debt_weight", 0),
            "debt_health": system_data.get("debt_metrics", {}).get("debt_health", 0),
        },
        "debt": {
            "resolved_count": system_data.get("debt_metrics", {}).get(
                "resolved_count", 0
            ),
            "unresolved_count": system_data.get("debt_metrics", {}).get(
                "unresolved_count", 0
            ),
            "total_count": (
                system_data.get("debt_metrics", {}).get("resolved_count", 0)
                + system_data.get("debt_metrics", {}).get("unresolved_count", 0)
            ),
            "resolution_rate": 0,
        },
        "categories": dashboard_data.get("debt_categories", {}),
        "trend": dashboard_data.get("health_trend", []),
        "projects": {
            "kairon": {"status": "healthy", "debt_count": 0},
            "gbrain": {"status": "healthy", "debt_count": 0},
            "metaos": {"status": "healthy", "debt_count": 0},
            "agora": {"status": "healthy", "debt_count": 0},
            "cockpit": {"status": "healthy", "debt_count": 0},
            "ecos": {"status": "healthy", "debt_count": 0},
            "omo": {"status": "healthy", "debt_count": 0},
            "runtime": {"status": "healthy", "debt_count": 0},
        },
    }
    total = governance_data["debt"]["total_count"]
    resolved = governance_data["debt"]["resolved_count"]
    governance_data["debt"]["resolution_rate"] = resolved / total if total > 0 else 0
    return governance_data


def serialize_governance_data(governance_data: dict[str, Any]) -> str:
    return json.dumps(governance_data, indent=2, ensure_ascii=False) + "\n"


def normalize_governance_data_json(payload: str) -> str:
    data = json.loads(payload)
    if isinstance(data, dict):
        data = dict(data)
        data.pop("generated_at", None)
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def write_governance_data(
    workspace_root: Path,
    governance_data: dict[str, Any],
    *,
    if_changed: bool = True,
) -> Path:
    output_path = workspace_root / ".omo" / "_control" / "governance-data.json"
    payload = serialize_governance_data(governance_data)
    if if_changed:
        write_text_if_changed(
            output_path,
            payload,
            normalize=normalize_governance_data_json,
        )
    else:
        write_text_atomic(output_path, payload)
    return output_path
