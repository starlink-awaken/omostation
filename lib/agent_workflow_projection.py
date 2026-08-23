"""Deterministic legacy projection for the canonical workflow registry.

The split registry directory is the only writer authority.  This module only
materializes and checks the legacy single-file compatibility view; it never
loads that view as a fallback authority.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "agent-workflow-compat-projection/v1"
SOURCE_REF = ".omo/_truth/registry/agent-workflows"
WRITER = "bin/agent-workflow.py projection-sync"


class ProjectionError(RuntimeError):
    """Raised when the compatibility projection cannot be proven current."""


def source_digest(source_directory: Path) -> str:
    """Return a path-sensitive digest over every canonical YAML source file."""
    if not source_directory.is_dir():
        raise ProjectionError("WORKFLOW_PROJECTION_SOURCE_UNPROVABLE: canonical directory missing")
    files = sorted(path for path in source_directory.rglob("*.yaml") if path.is_file())
    if not files:
        raise ProjectionError("WORKFLOW_PROJECTION_SOURCE_UNPROVABLE: canonical YAML missing")
    digest = hashlib.sha256()
    for path in files:
        try:
            relative = path.relative_to(source_directory).as_posix().encode("utf-8")
            content = path.read_bytes()
        except (OSError, UnicodeError) as exc:
            raise ProjectionError(
                "WORKFLOW_PROJECTION_SOURCE_UNPROVABLE: canonical source unreadable"
            ) from exc
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return f"sha256:{digest.hexdigest()}"


def load_registry_snapshot(
    loader: Callable[[Path], dict[str, Any]], source_directory: Path
) -> tuple[dict[str, Any], str]:
    """Load one registry snapshot and prove its source bytes stayed stable."""
    before = source_digest(source_directory)
    registry = loader(source_directory)
    after = source_digest(source_directory)
    if before != after:
        raise ProjectionError("WORKFLOW_PROJECTION_SOURCE_RACED: canonical source changed during load")
    return registry, after


def _validated_workflows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    raw = registry.get("workflows")
    if not isinstance(raw, list) or not raw:
        raise ProjectionError("WORKFLOW_PROJECTION_SOURCE_INVALID: workflows must be a non-empty list")
    workflows: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ProjectionError("WORKFLOW_PROJECTION_SOURCE_INVALID: workflow must be a mapping")
        workflow_id = item.get("id")
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            raise ProjectionError("WORKFLOW_PROJECTION_SOURCE_INVALID: workflow id missing")
        if workflow_id in identifiers:
            raise ProjectionError(f"WORKFLOW_PROJECTION_SOURCE_INVALID: duplicate workflow id {workflow_id}")
        identifiers.add(workflow_id)
        workflows.append(dict(item))
    return sorted(workflows, key=lambda item: item["id"])


def render_projection(
    registry: dict[str, Any],
    source_directory: Path,
    *,
    source_digest_bound: str,
) -> bytes:
    """Render the complete merged registry as a deterministic read-only view."""
    if source_digest(source_directory) != source_digest_bound:
        raise ProjectionError("WORKFLOW_PROJECTION_SOURCE_RACED: canonical source changed after load")
    if "projection" in registry:
        raise ProjectionError("WORKFLOW_PROJECTION_SOURCE_INVALID: reserved projection metadata")
    payload = dict(registry)
    payload["workflows"] = _validated_workflows(registry)
    payload["projection"] = {
        "schema": SCHEMA,
        "authority": "projection",
        "lifecycle": "read_only_generated_compatibility",
        "source": SOURCE_REF,
        "source_digest": source_digest_bound,
        "writer": WRITER,
    }
    rendered = yaml.safe_dump(
        payload,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=True,
        width=1000,
    )
    return (
        "# GENERATED READ-ONLY COMPATIBILITY PROJECTION; NOT SSOT. DO NOT EDIT.\n" + rendered
    ).encode("utf-8")


def _validate_projection_target(source_directory: Path, projection_path: Path) -> None:
    try:
        source = source_directory.resolve(strict=True)
        target = projection_path.resolve(strict=False)
        target.relative_to(source)
    except FileNotFoundError as exc:
        raise ProjectionError("WORKFLOW_PROJECTION_SOURCE_UNPROVABLE: canonical directory missing") from exc
    except ValueError:
        return
    raise ProjectionError(
        "WORKFLOW_PROJECTION_TARGET_INVALID: compatibility projection cannot overwrite canonical sources"
    )


def check_projection(
    registry: dict[str, Any],
    source_directory: Path,
    projection_path: Path,
    *,
    source_digest_bound: str,
) -> dict[str, Any]:
    """Fail closed unless the on-disk projection exactly matches canonical sources."""
    _validate_projection_target(source_directory, projection_path)
    expected = render_projection(
        registry,
        source_directory,
        source_digest_bound=source_digest_bound,
    )
    expected_payload = yaml.safe_load(expected.decode("utf-8"))
    bound_digest = expected_payload["projection"]["source_digest"]
    try:
        actual = projection_path.read_bytes()
    except OSError as exc:
        raise ProjectionError("WORKFLOW_PROJECTION_UNPROVABLE: compatibility projection missing") from exc
    if actual != expected:
        raise ProjectionError("WORKFLOW_PROJECTION_DRIFT: compatibility projection is not current")
    if source_digest(source_directory) != bound_digest:
        raise ProjectionError("WORKFLOW_PROJECTION_SOURCE_RACED: canonical source changed during check")
    return {
        "ok": True,
        "reason": "projection_current",
        "source": SOURCE_REF,
        "source_digest": bound_digest,
        "workflow_ids": [item["id"] for item in _validated_workflows(registry)],
    }


def sync_projection(
    registry: dict[str, Any],
    source_directory: Path,
    projection_path: Path,
    *,
    source_digest_bound: str,
) -> dict[str, Any]:
    """Atomically materialize the legacy projection from canonical sources."""
    _validate_projection_target(source_directory, projection_path)
    expected = render_projection(
        registry,
        source_directory,
        source_digest_bound=source_digest_bound,
    )
    try:
        current = projection_path.read_bytes()
    except OSError:
        current = b""
    changed = current != expected
    if changed:
        projection_path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=projection_path.parent,
                prefix=f".{projection_path.name}.projection-",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(expected)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, projection_path)
            temporary = None
        except OSError as exc:
            raise ProjectionError("WORKFLOW_PROJECTION_WRITE_FAILED: atomic write failed") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    result = check_projection(
        registry,
        source_directory,
        projection_path,
        source_digest_bound=source_digest_bound,
    )
    result.update({"changed": changed, "reason": "projection_synced"})
    return result
