"""Read-only External Connection Fabric projection for Cockpit."""

from __future__ import annotations

import datetime
import importlib.util
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi import APIRouter

_REPO_ROOT = Path(__file__).resolve().parents[5]
_OMO_SRC = _REPO_ROOT / "projects" / "omo" / "src"
if str(_OMO_SRC) not in sys.path:
    sys.path.insert(0, str(_OMO_SRC))

try:
    from omo.omo_external_resources import read_latest_external_resource_observation
except Exception as exc:  # OMO is optional while Cockpit is being bootstrapped.
    read_latest_external_resource_observation = None  # type: ignore[assignment]
    _OMO_IMPORT_ERROR: Exception | None = exc
else:
    _OMO_IMPORT_ERROR = None


def _load_catalog_module() -> Any:
    module_path = _REPO_ROOT / "bin" / "ssot" / "external-resource-catalog.py"
    spec = importlib.util.spec_from_file_location(
        "cockpit_external_resource_catalog_projection", module_path
    )
    if spec is None or spec.loader is None:
        raise ImportError("external resource catalog projection is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    _catalog_module = _load_catalog_module()
    collect_external_resources = _catalog_module.collect_external_resources
except Exception as exc:  # Discovery is allowed to degrade independently.
    collect_external_resources = None  # type: ignore[assignment]
    _CATALOG_IMPORT_ERROR: Exception | None = exc
else:
    _CATALOG_IMPORT_ERROR = None


router = APIRouter(prefix="/api/external-resources", tags=["external-resources"])


def _unavailable_projection(error_type: str, next_action: str) -> dict[str, Any]:
    now_iso = datetime.datetime.now(datetime.UTC).isoformat()
    return {
        "schema": "external-resource-catalog/v1",
        "mode": "read_only_projection",
        "activation": "forbidden",
        "raw_content_policy": "never_read_or_export",
        "observed_at": now_iso,
        "health_ttl_seconds": 900,
        "policy_digest": "external-connection-fabric/v1",
        "resources": [],
        "errors": [{"entry_point": "cockpit", "status": "unavailable", "error": error_type}],
        "summary": {
            "resource_count": 0,
            "unavailable_count": 0,
            "error_count": 1,
            "by_kind": {},
            "by_availability": {},
        },
        "status": "unavailable",
        "next_action": next_action,
    }


def _latest_catalog() -> dict[str, Any] | None:
    if read_latest_external_resource_observation is None:
        return None
    observation = read_latest_external_resource_observation(_REPO_ROOT / ".omo")
    if not isinstance(observation, Mapping):
        return None
    catalog = observation.get("catalog")
    if not isinstance(catalog, Mapping):
        return None
    if catalog.get("schema") != "external-resource-catalog/v1":
        return None
    if catalog.get("activation") != "forbidden":
        return None
    return dict(catalog)


def _projection_status(projection: Mapping[str, Any]) -> str:
    return "degraded" if projection.get("errors") else "live"


@router.get("")
async def get_external_resources() -> dict[str, Any]:
    """Expose a governed observation, or a safe discovery fallback.

    This route never persists observations and never calls provider business
    methods. A missing OMO observation may trigger only the provider contract's
    explicit read-only health probe while building a fresh projection.
    """
    try:
        latest = _latest_catalog()
    except (OSError, ValueError, TypeError):
        latest = None
    if latest is not None:
        return {
            "ok": True,
            "status": _projection_status(latest),
            "source": "omo.external_resource_observation",
            "projection": latest,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }

    if collect_external_resources is None:
        projection = _unavailable_projection(
            type(_CATALOG_IMPORT_ERROR or _OMO_IMPORT_ERROR).__name__,
            "先运行 external-resource-catalog observe 建立受治理观察，再刷新 Cockpit。",
        )
        return {
            "ok": False,
            "status": "unavailable",
            "source": "cockpit.external_resource_catalog",
            "projection": projection,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    try:
        projection = collect_external_resources(_REPO_ROOT, probe=True)
    except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
        projection = _unavailable_projection(
            type(exc).__name__,
            "检查 Agora 外部能力描述器和只读健康探针后重试。",
        )
        return {
            "ok": False,
            "status": "unavailable",
            "source": "cockpit.external_resource_catalog",
            "projection": projection,
            "external_side_effects": "disabled",
            "worker_launch": False,
        }
    return {
        "ok": True,
        "status": _projection_status(projection),
        "source": "agora.external_resource_discovery",
        "projection": projection,
        "external_side_effects": "disabled",
        "worker_launch": False,
    }
