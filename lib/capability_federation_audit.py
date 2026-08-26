#!/usr/bin/env python3
"""Read-only graph audit across native capability authorities.

This is deliberately a federation *observer*, not another capability registry.
It reads the provider, worker, workflow, and generated-catalog surfaces and
reports their relationships without changing their authority or writing state.

Internal library entrypoint. The public CLI is ``bin/capability-sync.py
federation-audit`` so the federation observer does not create another active
``bin/`` command surface.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional

import yaml

SCHEMA = "capability-federation-audit/v1"
PROVIDERS_PATH = Path(".omo/_truth/registry/capability-providers.yaml")
WORKERS_PATH = Path(".omo/_truth/registry/workers.yaml")
WORKFLOW_ROOT_PATH = Path(".omo/_truth/registry/agent-workflows/_root.yaml")
WORKFLOW_DIRECTORY = Path(".omo/_truth/registry/agent-workflows/workflows")
WORKFLOW_LEGACY_PATH = Path(".omo/_truth/registry/agent-workflows.yaml")
WORKFLOW_PROJECTION_SCHEMA = "agent-workflow-compat-projection/v1"
WORKFLOW_PROJECTION_SOURCE = ".omo/_truth/registry/agent-workflows"
WORKFLOW_PROJECTION_WRITER = "bin/agent-workflow.py projection-sync"
PROJECTION_PATH = Path("docs/generated/capability-registry.yaml")
CONFORMANCE_FIELDS = (
    "transport_id",
    "backend_ref",
    "route_ref",
    "operation_level",
    "write_scope",
    "workspace_admission",
    "states",
)
# Keep this validator aligned with bin/plan/bet-ledger.py::load_provider_attempt_profiles.
CONFORMANCE_FIELD_SET = frozenset(CONFORMANCE_FIELDS)
CONFORMANCE_STATES = frozenset({"succeeded", "failed", "awaiting_human_action", "settled_observed"})
CONFORMANCE_OPERATION_LEVELS = frozenset({"L0", "L1"})
CONFORMANCE_WRITE_SCOPES = frozenset({"none", "bounded", "human_gated"})
CONFORMANCE_WORKSPACE_ADMISSIONS = frozenset({"not_required_read_only", "verified_independent_clone"})
CONFORMANCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,255}$")


def _relative(path: Path) -> str:
    return path.as_posix()


def _diagnostic(
    code: str,
    severity: str,
    subject: str,
    source: Path,
    detail: str,
    *,
    status: str = "reported",
) -> dict[str, str]:
    """Build a public, deterministic diagnostic without machine-local paths."""
    return {
        "code": code,
        "detail": detail,
        "severity": severity,
        "source": _relative(source),
        "status": status,
        "subject": subject,
    }


def _load_yaml(workspace: Path, relative: Path, diagnostics: list[dict[str, str]]) -> dict[str, Any]:
    path = workspace / relative
    if not path.is_file():
        diagnostics.append(
            _diagnostic(
                "CAP_FED_SOURCE_UNPROVABLE",
                "unprovable",
                _relative(relative),
                relative,
                "required source is unavailable; no retirement inference was made",
                status="unprovable",
            )
        )
        return {}
    try:
        documents = [item for item in yaml.safe_load_all(path.read_text(encoding="utf-8")) if item is not None]
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        diagnostics.append(
            _diagnostic(
                "CAP_FED_SOURCE_UNPROVABLE",
                "unprovable",
                _relative(relative),
                relative,
                f"required source cannot be safely read as YAML: {type(exc).__name__}",
                status="unprovable",
            )
        )
        return {}
    if not documents or not isinstance(documents[-1], dict):
        diagnostics.append(
            _diagnostic(
                "CAP_FED_SOURCE_UNPROVABLE",
                "unprovable",
                _relative(relative),
                relative,
                "required source has no mapping body",
                status="unprovable",
            )
        )
        return {}
    return documents[-1]


def _items(payload: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = payload.get(field)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _declared_backend_ids(payload: dict[str, Any], provider_ids: set[str]) -> set[str]:
    """Resolve provider and explicitly declared compute-plane backend identities."""
    backend_ids = set(provider_ids)
    compute_plane = payload.get("compute_plane")
    if not isinstance(compute_plane, dict):
        return backend_ids
    for field in ("runtime", "gateway"):
        value = compute_plane.get(field)
        if isinstance(value, str) and CONFORMANCE_ID_RE.fullmatch(value) is not None:
            backend_ids.add(value)
    return backend_ids


def _report_duplicate_ids(
    items: Iterable[dict[str, Any]],
    *,
    kind: str,
    source: Path,
    diagnostics: list[dict[str, str]],
) -> None:
    seen: set[str] = set()
    for item in items:
        identity = item.get("id")
        if not isinstance(identity, str) or not identity:
            continue
        if identity in seen:
            diagnostics.append(
                _diagnostic(
                    "CAP_FED_DUPLICATE_AUTHORITY_CLAIM",
                    "error",
                    f"{kind}:{identity}",
                    source,
                    "multiple records claim the same native authority identifier",
                )
            )
        seen.add(identity)


def _workflow_ids(payload: dict[str, Any]) -> list[str]:
    workflows = payload.get("workflows")
    if isinstance(workflows, dict):
        return sorted(str(key) for key in workflows if isinstance(key, str) and key)
    if isinstance(workflows, list):
        return sorted(
            item["id"]
            for item in workflows
            if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
        )
    return []


def _directory_workflow_ids(workspace: Path, diagnostics: list[dict[str, str]]) -> list[str]:
    directory = workspace / WORKFLOW_DIRECTORY
    if not directory.is_dir():
        diagnostics.append(
            _diagnostic(
                "CAP_FED_SOURCE_UNPROVABLE",
                "unprovable",
                _relative(WORKFLOW_DIRECTORY),
                WORKFLOW_DIRECTORY,
                "canonical workflow directory is unavailable; no workflow retirement inference was made",
                status="unprovable",
            )
        )
        return []
    ids: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        relative = path.relative_to(workspace)
        payload = _load_yaml(workspace, relative, diagnostics)
        identity = payload.get("id")
        if isinstance(identity, str) and identity:
            ids.append(identity)
    return sorted(ids)


def _workflow_source_digest(workspace: Path) -> str | None:
    source_directory = workspace / WORKFLOW_ROOT_PATH.parent
    if not source_directory.is_dir():
        return None
    files = sorted(path for path in source_directory.rglob("*.yaml") if path.is_file())
    if not files:
        return None
    digest = hashlib.sha256()
    try:
        for path in files:
            relative = path.relative_to(source_directory).as_posix().encode("utf-8")
            content = path.read_bytes()
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
    except OSError:
        return None
    return f"sha256:{digest.hexdigest()}"


def _workflow_projection_metadata_is_valid(workspace: Path, payload: dict[str, Any]) -> bool:
    metadata = payload.get("projection")
    digest = _workflow_source_digest(workspace)
    return digest is not None and isinstance(metadata, dict) and metadata == {
        "schema": WORKFLOW_PROJECTION_SCHEMA,
        "authority": "projection",
        "lifecycle": "read_only_generated_compatibility",
        "source": WORKFLOW_PROJECTION_SOURCE,
        "source_digest": digest,
        "writer": WORKFLOW_PROJECTION_WRITER,
    }


def _workflow_definitions(payload: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    workflows = payload.get("workflows")
    if not isinstance(workflows, list):
        return None
    definitions: dict[str, dict[str, Any]] = {}
    for item in workflows:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            return None
        workflow_id = item["id"]
        if workflow_id in definitions:
            return None
        definitions[workflow_id] = item
    return definitions


def _directory_workflow_definitions(workspace: Path) -> dict[str, dict[str, Any]] | None:
    directory = workspace / WORKFLOW_DIRECTORY
    definitions: dict[str, dict[str, Any]] = {}
    try:
        for path in sorted(directory.glob("*.yaml")):
            documents = [
                item for item in yaml.safe_load_all(path.read_text(encoding="utf-8")) if item is not None
            ]
            if not documents or not isinstance(documents[-1], dict):
                return None
            item = documents[-1]
            workflow_id = item.get("id")
            if not isinstance(workflow_id, str) or not workflow_id or workflow_id in definitions:
                return None
            definitions[workflow_id] = item
    except (OSError, UnicodeError, yaml.YAMLError):
        return None
    return definitions or None


def _projection_files(value: Any) -> Iterable[str]:
    """Yield relative static source references from the generated projection only."""
    if isinstance(value, dict):
        file_ref = value.get("file")
        if isinstance(file_ref, str):
            yield file_ref
        for nested in value.values():
            yield from _projection_files(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _projection_files(nested)


def _projection_entry_count(payload: dict[str, Any]) -> int:
    return sum(
        len(value)
        for value in payload.values()
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value)
    )


def _projection_header_claims_authority(workspace: Path) -> bool:
    """Detect a positive, rather than negated, SSOT claim in the comment header."""
    try:
        lines = (workspace / PROJECTION_PATH).read_text(encoding="utf-8").splitlines()[:24]
    except (OSError, UnicodeError):
        return False
    negations = ("not ssot", "not a ssot", "not an ssot", "不是 ssot", "不是ssot", "非 ssot", "非ssot")
    for line in lines:
        if not line.lstrip().startswith("#"):
            continue
        header = line.lstrip("#").strip().casefold()
        if "ssot" in header and not any(negation in header for negation in negations):
            return True
    return False


def _projection_report(workspace: Path, payload: dict[str, Any], diagnostics: list[dict[str, str]]) -> dict[str, Any]:
    authority_claim = payload.get("authority")
    writer = payload.get("writer")
    generator = payload.get("generator")
    expected_writer = "bin/ssot/gen-capability-registry.py"
    if authority_claim in {"ssot", "authoritative", "authority"} or _projection_header_claims_authority(workspace):
        diagnostics.append(
            _diagnostic(
                "CAP_FED_PROJECTION_AUTHORITY_CLAIM",
                "error",
                "generated-capability-registry",
                PROJECTION_PATH,
                "generated capability inventory may not claim SSOT authority",
            )
        )
    if writer != expected_writer and generator != expected_writer:
        diagnostics.append(
            _diagnostic(
                "CAP_FED_PROJECTION_PROVENANCE_UNPROVABLE",
                "unprovable",
                "generated-capability-registry",
                PROJECTION_PATH,
                "projection generator provenance is absent or unexpected",
                status="unprovable",
            )
        )

    for reference in sorted(set(_projection_files(payload))):
        candidate = Path(reference)
        if candidate.is_absolute() or ".." in candidate.parts or not (workspace / candidate).is_file():
            diagnostics.append(
                _diagnostic(
                    "CAP_FED_SOURCE_UNPROVABLE",
                    "unprovable",
                    f"projection-source:{reference if not candidate.is_absolute() else 'absolute'}",
                    PROJECTION_PATH,
                    "projection source is unavailable; no capability retirement inference was made",
                    status="unprovable",
                )
            )

    return {
        "admission_inference": "forbidden",
        "authority": "projection",
        "projected_entries": _projection_entry_count(payload),
        "source": _relative(PROJECTION_PATH),
    }


def _transport_diagnostics(
    worker: dict[str, Any],
    declared_backend_ids: set[str],
    conformance_transport_ids: dict[str, list[str]],
    diagnostics: list[dict[str, str]],
) -> list[str]:
    worker_id = str(worker.get("id", "unknown"))
    transports = worker.get("transports")
    if not isinstance(transports, dict):
        diagnostics.append(
            _diagnostic(
                "CAP_FED_ADMITTED_TRANSPORT_MISSING",
                "error",
                worker_id,
                WORKERS_PATH,
                "admitted worker has no transport mapping",
            )
        )
        return []
    transport_ids: list[str] = []
    for name in sorted(transports):
        config = transports[name]
        if not isinstance(name, str):
            continue
        transport_ids.append(name)
        if not isinstance(config, dict):
            diagnostics.append(
                _diagnostic(
                    "CAP_FED_ADMITTED_TRANSPORT_CONFORMANCE_INCOMPLETE",
                    "error",
                    f"{worker_id}:{name}",
                    WORKERS_PATH,
                    "transport configuration is not a mapping",
                )
            )
            continue
        ack = config.get("worker_ack_protocol")
        if not isinstance(ack, str) or not ack:
            diagnostics.append(
                _diagnostic(
                    "CAP_FED_ADMITTED_TRANSPORT_ACK_MISSING",
                    "error",
                    f"{worker_id}:{name}",
                    WORKERS_PATH,
                    "admitted transport lacks worker_ack_protocol",
                )
            )
        conformance = config.get("provider_conformance")
        missing = [
            field for field in CONFORMANCE_FIELDS if not isinstance(conformance, dict) or field not in conformance
        ]
        if missing:
            diagnostics.append(
                _diagnostic(
                    "CAP_FED_ADMITTED_TRANSPORT_CONFORMANCE_INCOMPLETE",
                    "error",
                    f"{worker_id}:{name}",
                    WORKERS_PATH,
                    f"missing provider_conformance fields: {','.join(missing)}",
                )
            )
            continue
        assert isinstance(conformance, dict)
        transport_id = conformance.get("transport_id")
        backend_ref = conformance.get("backend_ref")
        route_ref = conformance.get("route_ref")
        states = conformance.get("states")
        is_valid = (
            set(conformance) == CONFORMANCE_FIELD_SET
            and isinstance(transport_id, str)
            and CONFORMANCE_ID_RE.fullmatch(transport_id) is not None
            and isinstance(backend_ref, str)
            and CONFORMANCE_ID_RE.fullmatch(backend_ref) is not None
            and (route_ref is None or isinstance(route_ref, str) and route_ref.startswith("bos://"))
            and isinstance(states, list)
            and bool(states)
            and all(isinstance(state, str) and state in CONFORMANCE_STATES for state in states)
            and conformance.get("operation_level") in CONFORMANCE_OPERATION_LEVELS
            and conformance.get("write_scope") in CONFORMANCE_WRITE_SCOPES
            and conformance.get("workspace_admission") in CONFORMANCE_WORKSPACE_ADMISSIONS
        )
        if not is_valid:
            diagnostics.append(
                _diagnostic(
                    "CAP_FED_ADMITTED_TRANSPORT_CONFORMANCE_INVALID",
                    "error",
                    f"{worker_id}:{name}",
                    WORKERS_PATH,
                    "provider_conformance violates the provider-attempt profile contract",
                )
            )
            continue
        if backend_ref not in declared_backend_ids:
            diagnostics.append(
                _diagnostic(
                    "CAP_FED_ADMITTED_TRANSPORT_BACKEND_UNDECLARED",
                    "error",
                    f"{worker_id}:{name}",
                    WORKERS_PATH,
                    "provider_conformance backend_ref is not a declared provider or compute-plane backend",
                )
            )
        assert isinstance(transport_id, str)
        conformance_transport_ids.setdefault(transport_id, []).append(f"{worker_id}:{name}")
    return transport_ids


def _verdict(diagnostics: Iterable[dict[str, str]]) -> tuple[str, int]:
    severities = {item["severity"] for item in diagnostics}
    if "unprovable" in severities:
        return "UNPROVABLE", 2
    if "error" in severities:
        return "FAIL", 1
    if "warning" in severities:
        return "WARN", 0
    return "PASS", 0


def audit_workspace(workspace_root: Path) -> dict[str, Any]:
    """Read native sources and return a deterministic, sanitized federation graph."""
    workspace = workspace_root.resolve()
    diagnostics: list[dict[str, str]] = []
    providers_payload = _load_yaml(workspace, PROVIDERS_PATH, diagnostics)
    workers_payload = _load_yaml(workspace, WORKERS_PATH, diagnostics)
    workflow_root = _load_yaml(workspace, WORKFLOW_ROOT_PATH, diagnostics)
    projection_payload = _load_yaml(workspace, PROJECTION_PATH, diagnostics)
    directory_ids = _directory_workflow_ids(workspace, diagnostics)

    provider_items = _items(providers_payload, "providers")
    worker_items = _items(workers_payload, "workers")
    _report_duplicate_ids(provider_items, kind="provider", source=PROVIDERS_PATH, diagnostics=diagnostics)
    _report_duplicate_ids(worker_items, kind="worker", source=WORKERS_PATH, diagnostics=diagnostics)
    provider_ids = {item["id"] for item in provider_items if isinstance(item.get("id"), str) and item["id"]}
    backend_ids = _declared_backend_ids(providers_payload, provider_ids)
    conformance_transport_ids: dict[str, list[str]] = {}

    workers: list[dict[str, Any]] = []
    for worker in sorted(worker_items, key=lambda item: str(item.get("id", ""))):
        worker_id = worker.get("id")
        provider_ref = worker.get("provider_ref")
        state = worker.get("admission_state", "declared")
        if not isinstance(worker_id, str) or not worker_id:
            diagnostics.append(
                _diagnostic(
                    "CAP_FED_DUPLICATE_AUTHORITY_CLAIM",
                    "error",
                    "worker:missing-id",
                    WORKERS_PATH,
                    "worker record lacks a stable authority identifier",
                )
            )
            continue
        if not isinstance(provider_ref, str) or not provider_ref or provider_ref not in provider_ids:
            diagnostics.append(
                _diagnostic(
                    "CAP_FED_DANGLING_PROVIDER_REF",
                    "error",
                    worker_id,
                    WORKERS_PATH,
                    "worker provider_ref does not resolve in capability-providers",
                )
            )
        transports: list[str] = []
        if state == "admitted":
            transports = _transport_diagnostics(worker, backend_ids, conformance_transport_ids, diagnostics)
        else:
            configured = worker.get("transports")
            if isinstance(configured, dict):
                transports = sorted(str(name) for name in configured if isinstance(name, str))
        workers.append(
            {
                "id": worker_id,
                "provider_ref": provider_ref if isinstance(provider_ref, str) else None,
                "state": state if isinstance(state, str) else "declared",
                "transports": transports,
            }
        )

    for transport_id, subjects in sorted(conformance_transport_ids.items()):
        if len(subjects) > 1:
            diagnostics.append(
                _diagnostic(
                    "CAP_FED_ADMITTED_TRANSPORT_ID_DUPLICATE",
                    "error",
                    f"transport_id:{transport_id}",
                    WORKERS_PATH,
                    "provider_conformance transport_id is duplicated across admitted transports: "
                    + ",".join(sorted(subjects)),
                )
            )

    legacy_payload: dict[str, Any] | None = None
    legacy_path = workspace / WORKFLOW_LEGACY_PATH
    if legacy_path.is_file():
        legacy_payload = _load_yaml(workspace, WORKFLOW_LEGACY_PATH, diagnostics)
        if not _workflow_projection_metadata_is_valid(workspace, legacy_payload):
            diagnostics.append(
                _diagnostic(
                    "CAP_FED_WORKFLOW_DUAL_AUTHORITY",
                    "warning",
                    "agent-workflows",
                    WORKFLOW_LEGACY_PATH,
                    "legacy workflow view lacks valid read-only projection provenance; it must not become a second authority",
                )
            )
        canonical_ids = sorted(set(_workflow_ids(workflow_root)) | set(directory_ids))
        legacy_ids = _workflow_ids(legacy_payload)
        canonical_definitions = _directory_workflow_definitions(workspace)
        legacy_definitions = _workflow_definitions(legacy_payload)
        content_diverged = (
            canonical_definitions is not None
            and legacy_definitions is not None
            and canonical_definitions != legacy_definitions
        )
        if canonical_ids and (canonical_ids != legacy_ids or content_diverged):
            diagnostics.append(
                _diagnostic(
                    "CAP_FED_WORKFLOW_REGISTRY_DIVERGENCE",
                    "warning",
                    "agent-workflows",
                    WORKFLOW_LEGACY_PATH,
                    "canonical and legacy workflow identifiers or definitions diverge; legacy data is not used as an authority",
                )
            )
    else:
        diagnostics.append(
            _diagnostic(
                "CAP_FED_WORKFLOW_LEGACY_VIEW_MISSING",
                "warning",
                "agent-workflows",
                WORKFLOW_LEGACY_PATH,
                "legacy workflow view is unavailable; canonical directory remains the only inspected authority",
            )
        )

    projection = _projection_report(workspace, projection_payload, diagnostics)
    diagnostics = sorted(
        diagnostics,
        key=lambda item: (item["severity"], item["code"], item["source"], item["subject"], item["detail"]),
    )
    verdict, exit_code = _verdict(diagnostics)
    return {
        "authority": {
            "providers": _relative(PROVIDERS_PATH),
            "workers": _relative(WORKERS_PATH),
            "workflow_canonical_directory": _relative(WORKFLOW_DIRECTORY),
        },
        "diagnostics": diagnostics,
        "exit_code": exit_code,
        "projection": projection,
        "schema": SCHEMA,
        "state_model": {
            "admitted": "coordinator admission; not inferred from observation",
            "authorized": "permission decision; distinct from admission",
            "declared": "static native declaration",
            "discovered": "inventory discovery only",
            "evidenced": "eligible evidence recorded; not independent verification",
            "healthy": "health observation only",
            "invoked": "execution attempt observed",
            "observed": "runtime observation only",
            "fallback": "forbidden unless explicitly represented as a new governed attempt",
        },
        "verdict": verdict,
        "workers": workers,
        "workflows": {
            "canonical_directory_ids": directory_ids,
            "canonical_root_ids": _workflow_ids(workflow_root),
            "legacy_ids": _workflow_ids(legacy_payload) if legacy_payload is not None else [],
        },
    }


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:  # noqa: UP045
    parser = argparse.ArgumentParser(description="Read-only capability federation graph audit")
    parser.add_argument(
        "--workspace-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="workspace root to inspect (read-only)",
    )
    parser.add_argument("--json", action="store_true", help="emit canonical JSON (default)")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return non-zero when the read-only audit reports warnings",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:  # noqa: UP045
    args = parse_args(argv)
    report = audit_workspace(Path(args.workspace_root))
    exit_code = int(report["exit_code"])
    if args.strict and exit_code == 0 and report["verdict"] == "WARN":
        exit_code = 1
    report["exit_code"] = exit_code
    report["strict"] = bool(args.strict)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
