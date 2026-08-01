#!/usr/bin/env python3
"""Fail-closed, content-free preflight for the KEMS production lane."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse

SOURCE_PATTERNS = (
    "*-auto-seeyon-oa-pending.md",
    "*-auto-netease-mailmaster.md",
    "*-auto-apple-mail.md",
    "*-auto-iphone-sms.md",
)
SOURCE_SCOPE_ID = "kems.private-source-review.v1"
ALL_AUTO_SOURCE_PATTERN = "*-auto-*.md"
FORBIDDEN_KEYS = {"body", "content", "ocr_text", "raw_text", "text"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
APPROVED_STATUSES = {"approved", "dispatched", "executing", "verified", "closed"}
MODEL_ACCEPTANCE_SCHEMA = "kems.model-acceptance.v1"


@dataclass(frozen=True)
class Check:
    check_id: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {"id": self.check_id, "ok": self.ok, "detail": self.detail}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomically(payload: dict[str, object], output: Path) -> None:
    """Persist only redacted gate evidence, without leaving a partial artifact."""
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(output)
        output.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def _source_files(docs_root: Path) -> list[Path]:
    inbox = docs_root / "_inbox"
    return sorted(
        {
            path
            for pattern in SOURCE_PATTERNS
            for path in inbox.glob(pattern)
            if path.is_file()
        }
    )


def _source_scope_metadata(docs_root: Path, sources: list[Path]) -> dict[str, object]:
    """Expose controlled scope and explicit exclusions without hashing excluded content."""
    inbox = docs_root / "_inbox"
    controlled = {path.resolve() for path in sources}
    excluded = sorted(
        {
            path.name
            for path in inbox.glob(ALL_AUTO_SOURCE_PATTERN)
            if path.is_file() and path.resolve() not in controlled
        }
    )
    return {
        "scope_id": SOURCE_SCOPE_ID,
        "controlled_patterns": list(SOURCE_PATTERNS),
        "excluded_auto_sources": [
            {"name": name, "reason": "outside_controlled_scope"} for name in excluded
        ],
    }


def _source_inventory(sources: list[Path]) -> tuple[list[dict[str, object]], str]:
    inventory = [
        {"name": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in sources
    ]
    canonical = json.dumps(
        inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return inventory, hashlib.sha256(canonical).hexdigest()


def _contains_forbidden_key(value: object) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                return str(key)
            found = _contains_forbidden_key(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _contains_forbidden_key(child)
            if found:
                return found
    return None


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON metadata: {type(exc).__name__}") from exc


def _evaluation_check(
    path: Path | None, sources: list[Path], *, bind_sources: bool
) -> Check:
    if path is None:
        return Check("evaluation_manifest", False, "missing evaluation manifest path")
    if not path.is_file():
        return Check("evaluation_manifest", False, "evaluation manifest is unavailable")
    try:
        payload = _load_json(path)
    except ValueError as exc:
        return Check("evaluation_manifest", False, str(exc))
    if not isinstance(payload, dict):
        return Check("evaluation_manifest", False, "manifest must be an object")
    if payload.get("schema_version") != "kems.evaluation-manifest.v1":
        return Check("evaluation_manifest", False, "unsupported manifest schema")
    if payload.get("redaction_status") != "verified":
        return Check("evaluation_manifest", False, "manifest is not redaction-verified")
    for field in ("dataset_id", "dataset_version"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            return Check("evaluation_manifest", False, f"{field} is missing")
    samples = payload.get("samples")
    if not isinstance(samples, list) or not samples:
        return Check("evaluation_manifest", False, "manifest has no samples")
    sample_ids: set[str] = set()
    source_inventory = {
        f"vault://redacted/{source.name}": _sha256(source) for source in sources
    }
    for sample in samples:
        if not isinstance(sample, dict):
            return Check("evaluation_manifest", False, "sample must be an object")
        forbidden = _contains_forbidden_key(sample)
        if forbidden:
            return Check("evaluation_manifest", False, "raw content key is forbidden")
        sample_id = sample.get("sample_id")
        source_sha256 = sample.get("source_sha256")
        source_ref = sample.get("source_ref")
        if not isinstance(sample_id, str) or not sample_id or sample_id in sample_ids:
            return Check(
                "evaluation_manifest", False, "sample IDs must be non-empty and unique"
            )
        if not isinstance(source_sha256, str) or not SHA256.fullmatch(source_sha256):
            return Check(
                "evaluation_manifest", False, "sample source_sha256 is invalid"
            )
        if not isinstance(source_ref, str) or not source_ref.startswith(
            "vault://redacted/"
        ):
            return Check(
                "evaluation_manifest", False, "sample source_ref is not redacted"
            )
        if sample.get("annotation_status") != "adjudicated":
            return Check(
                "evaluation_manifest", False, "all samples must be adjudicated"
            )
        if not isinstance(sample.get("labels"), dict) or not sample["labels"]:
            return Check("evaluation_manifest", False, "all samples require labels")
        if (
            not isinstance(sample.get("annotation_version"), str)
            or not sample["annotation_version"].strip()
        ):
            return Check(
                "evaluation_manifest", False, "all samples require annotation_version"
            )
        if bind_sources:
            expected_sha256 = source_inventory.get(source_ref)
            if expected_sha256 is None:
                return Check(
                    "evaluation_manifest",
                    False,
                    "manifest source_ref is not present in the current source inventory",
                )
            if source_sha256 != expected_sha256:
                return Check(
                    "evaluation_manifest",
                    False,
                    "manifest source_sha256 does not match the current source inventory",
                )
        sample_ids.add(sample_id)
    detail = f"verified adjudicated samples={len(samples)}"
    if bind_sources:
        detail += "; source hashes match current inventory"
    return Check("evaluation_manifest", True, detail)


def _adjudication_check(
    database_path: Path | None, evaluation_manifest: Path | None
) -> Check:
    """Bind every manifest row to the persisted, independently adjudicated record."""
    if database_path is None:
        return Check(
            "adjudication_persistence",
            False,
            "missing adjudication database path",
        )
    if evaluation_manifest is None or not evaluation_manifest.is_file():
        return Check(
            "adjudication_persistence",
            False,
            "evaluation manifest is required to bind adjudication records",
        )
    if not database_path.is_file():
        return Check(
            "adjudication_persistence",
            False,
            "adjudication database is unavailable",
        )
    try:
        manifest = _load_json(evaluation_manifest)
        samples = manifest.get("samples") if isinstance(manifest, dict) else None
        if not isinstance(samples, list) or not samples:
            return Check(
                "adjudication_persistence",
                False,
                "evaluation manifest has no samples to bind",
            )
        uri = f"file:{quote(str(database_path.resolve()), safe='/')}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            for sample in samples:
                if not isinstance(sample, dict):
                    return Check(
                        "adjudication_persistence",
                        False,
                        "manifest sample is not an object",
                    )
                sample_id = sample.get("sample_id")
                if not isinstance(sample_id, str) or not sample_id:
                    return Check(
                        "adjudication_persistence",
                        False,
                        "manifest sample_id is invalid",
                    )
                row = connection.execute(
                    "SELECT annotation_status, source_sha256, source_ref, labels_json, "
                    "annotation_version, adjudicator FROM adjudication_queue WHERE sample_id=?",
                    (sample_id,),
                ).fetchone()
                if row is None:
                    return Check(
                        "adjudication_persistence",
                        False,
                        "manifest sample is absent from adjudication database",
                    )
                if row["annotation_status"] != "adjudicated":
                    return Check(
                        "adjudication_persistence",
                        False,
                        "manifest sample is not adjudicated in persistent store",
                    )
                if row["source_sha256"] != sample.get("source_sha256") or row[
                    "source_ref"
                ] != sample.get("source_ref"):
                    return Check(
                        "adjudication_persistence",
                        False,
                        "persistent adjudication source identity differs from manifest",
                    )
                if row["annotation_version"] != sample.get("annotation_version"):
                    return Check(
                        "adjudication_persistence",
                        False,
                        "persistent annotation version differs from manifest",
                    )
                try:
                    persisted_labels = json.loads(str(row["labels_json"]))
                except json.JSONDecodeError:
                    return Check(
                        "adjudication_persistence",
                        False,
                        "persistent adjudication labels are invalid",
                    )
                if persisted_labels != sample.get("labels"):
                    return Check(
                        "adjudication_persistence",
                        False,
                        "persistent adjudication labels differ from manifest",
                    )
                if not str(row["adjudicator"] or "").strip():
                    return Check(
                        "adjudication_persistence",
                        False,
                        "persistent adjudication has no adjudicator",
                    )
                annotation_count = connection.execute(
                    "SELECT COUNT(*) FROM adjudication_annotations WHERE sample_id=?",
                    (sample_id,),
                ).fetchone()[0]
                if annotation_count < 2:
                    return Check(
                        "adjudication_persistence",
                        False,
                        "persistent adjudication lacks two independent annotations",
                    )
    except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
        return Check(
            "adjudication_persistence",
            False,
            f"invalid adjudication database metadata: {type(exc).__name__}",
        )
    return Check(
        "adjudication_persistence",
        True,
        f"persisted independently adjudicated samples={len(samples)}",
    )


def _model_acceptance_check(
    path: Path | None, evaluation_manifest: Path | None
) -> Check:
    """Require a passing, manifest-bound candidate-model shadow report."""
    if path is None:
        return Check("model_acceptance", False, "missing model acceptance report path")
    if not path.is_file():
        return Check(
            "model_acceptance", False, "model acceptance report is unavailable"
        )
    if evaluation_manifest is None or not evaluation_manifest.is_file():
        return Check(
            "model_acceptance",
            False,
            "evaluation manifest is required to bind model acceptance",
        )
    try:
        payload = _load_json(path)
        manifest = _load_json(evaluation_manifest)
    except ValueError as exc:
        return Check("model_acceptance", False, str(exc))
    if not isinstance(payload, dict):
        return Check(
            "model_acceptance", False, "model acceptance report must be an object"
        )
    if not isinstance(manifest, dict):
        return Check("model_acceptance", False, "evaluation manifest must be an object")
    forbidden = _contains_forbidden_key(payload)
    if forbidden:
        return Check("model_acceptance", False, "raw content key is forbidden")
    if payload.get("schema_version") != MODEL_ACCEPTANCE_SCHEMA:
        return Check("model_acceptance", False, "unsupported model acceptance schema")
    if payload.get("status") != "shadow_pass":
        return Check(
            "model_acceptance", False, "candidate model did not pass shadow evaluation"
        )
    if payload.get("promotion") != "blocked_until_omo_approval":
        return Check(
            "model_acceptance", False, "model acceptance cannot authorize promotion"
        )
    for field in ("candidate_model_id", "baseline_model_id"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            return Check("model_acceptance", False, f"{field} is missing")
    for field in ("dataset_id", "dataset_version", "evaluation_manifest_sha256"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            return Check("model_acceptance", False, f"{field} is missing")
    if payload["dataset_id"] != manifest.get("dataset_id"):
        return Check(
            "model_acceptance",
            False,
            "model acceptance dataset_id does not match manifest",
        )
    if payload["dataset_version"] != manifest.get("dataset_version"):
        return Check(
            "model_acceptance",
            False,
            "model acceptance dataset_version does not match manifest",
        )
    if payload["evaluation_manifest_sha256"] != _sha256(evaluation_manifest):
        return Check(
            "model_acceptance",
            False,
            "model acceptance is bound to a different manifest",
        )
    samples = manifest.get("samples")
    try:
        dataset_sample_count = int(payload["dataset_sample_count"])
    except (KeyError, TypeError, ValueError):
        return Check(
            "model_acceptance",
            False,
            "model acceptance dataset sample count is invalid",
        )
    if not isinstance(samples, list) or dataset_sample_count != len(samples):
        return Check(
            "model_acceptance",
            False,
            "model acceptance sample count does not match manifest",
        )

    try:
        case_count = int(payload["case_count"])
        min_cases = int(payload["min_cases"])
        model_mae = float(payload["model_mae"])
        baseline_mae = float(payload["baseline_mae"])
        relative_improvement = float(payload["relative_improvement"])
        min_relative_improvement = float(payload["min_relative_improvement"])
    except (KeyError, TypeError, ValueError):
        return Check("model_acceptance", False, "model acceptance metrics are invalid")
    if (
        case_count < min_cases
        or min_cases <= 0
        or not all(
            math.isfinite(value)
            for value in (
                model_mae,
                baseline_mae,
                relative_improvement,
                min_relative_improvement,
            )
        )
        or model_mae > baseline_mae * (1.0 - min_relative_improvement)
    ):
        return Check(
            "model_acceptance",
            False,
            "model acceptance metrics do not satisfy thresholds",
        )
    return Check(
        "model_acceptance",
        True,
        f"shadow_pass model={payload['candidate_model_id']} cases={case_count}",
    )


def _omo_check(omo_root: Path, task_id: str | None) -> Check:
    if not task_id:
        return Check("omo_approval", False, "missing approved OMO task id")
    task_path = _omo_task_path(omo_root, task_id)
    if task_path is None:
        return Check("omo_approval", False, "approved OMO task is unavailable")
    try:
        import yaml
    except ImportError as exc:
        return Check(
            "omo_approval", False, f"invalid OMO task metadata: {type(exc).__name__}"
        )
    try:
        payload = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        return Check(
            "omo_approval", False, f"invalid OMO task metadata: {type(exc).__name__}"
        )
    if not isinstance(payload, dict):
        return Check("omo_approval", False, "OMO task metadata must be an object")
    if payload.get("status") not in APPROVED_STATUSES:
        return Check("omo_approval", False, "OMO task is not approved")
    approval_ref = payload.get("approval_ref")
    if payload.get("id") not in {None, task_id}:
        return Check("omo_approval", False, "OMO task id does not match task path")
    if not isinstance(approval_ref, str) or not approval_ref.endswith(".yaml"):
        return Check(
            "omo_approval", False, "OMO task approval_ref is missing or invalid"
        )

    root = omo_root.resolve().parent
    approval_path = _resolve_omo_ref(omo_root, approval_ref)
    if root not in approval_path.parents or not approval_path.is_file():
        return Check("omo_approval", False, "OMO approval artifact is unavailable")
    try:
        approval = yaml.safe_load(approval_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        return Check(
            "omo_approval",
            False,
            f"invalid OMO approval metadata: {type(exc).__name__}",
        )
    if not isinstance(approval, dict):
        return Check("omo_approval", False, "OMO approval metadata must be an object")
    task_ref = str(Path(".omo") / task_path.resolve().relative_to(omo_root.resolve()))
    if (
        approval.get("task_id") != task_id
        or approval.get("approval_status") != "granted"
        or approval.get("approval_scope") != "task.promote_apply"
        or approval.get("refs", {}).get("task_ref") != task_ref
    ):
        return Check(
            "omo_approval",
            False,
            "OMO promotion approval is missing, ungranted, or mismatched",
        )
    return Check("omo_approval", True, "official OMO promotion approval confirmed")


def _omo_task_path(omo_root: Path, task_id: str) -> Path | None:
    candidates = (
        omo_root / "tasks" / "active" / f"{task_id}.yaml",
        omo_root / "tasks" / "planned" / f"{task_id}.yaml",
        omo_root / "tasks" / "completed" / f"{task_id}.yaml",
    )
    return next((path for path in candidates if path.is_file()), None)


def _resolve_omo_ref(omo_root: Path, reference: str) -> Path:
    """Resolve a repo-relative `.omo/...` ref against the supplied OMO root."""
    root = omo_root.resolve().parent
    prefix = f"{omo_root.name}/"
    if reference.startswith(prefix):
        return (root / reference).resolve()
    if reference.startswith(".omo/"):
        return (omo_root / reference.removeprefix(".omo/")).resolve()
    return (root / reference).resolve()


def _evaluation_metadata(path: Path | None) -> dict[str, object]:
    if path is None or not path.is_file():
        return {"available": False}
    try:
        payload = _load_json(path)
    except ValueError:
        return {"available": False}
    if not isinstance(payload, dict):
        return {"available": False}
    samples = payload.get("samples")
    return {
        "available": True,
        "dataset_id": payload.get("dataset_id"),
        "dataset_version": payload.get("dataset_version"),
        "sample_count": len(samples) if isinstance(samples, list) else 0,
        "sha256": _sha256(path),
    }


def _adjudication_metadata(path: Path | None) -> dict[str, object]:
    if path is None or not path.is_file():
        return {"available": False}
    return {"available": True, "sha256": _sha256(path)}


def _model_acceptance_metadata(path: Path | None) -> dict[str, object]:
    if path is None or not path.is_file():
        return {"available": False}
    try:
        payload = _load_json(path)
    except ValueError:
        return {"available": False}
    if not isinstance(payload, dict):
        return {"available": False}
    return {
        "available": True,
        "candidate_model_id": payload.get("candidate_model_id"),
        "status": payload.get("status"),
        "dataset_id": payload.get("dataset_id"),
        "dataset_version": payload.get("dataset_version"),
        "sha256": _sha256(path),
    }


def _omo_metadata(omo_root: Path, task_id: str | None) -> dict[str, object]:
    if not task_id:
        return {"available": False}
    task_path = _omo_task_path(omo_root, task_id)
    if task_path is None:
        return {"available": False, "task_id": task_id}
    try:
        import yaml
    except ImportError:
        return {"available": False, "task_id": task_id}
    try:
        payload = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, yaml.YAMLError):
        return {"available": False, "task_id": task_id}
    if not isinstance(payload, dict):
        return {"available": False, "task_id": task_id}
    approval_ref = payload.get("approval_ref")
    if not isinstance(approval_ref, str):
        return {"available": False, "task_id": task_id}
    root = omo_root.resolve().parent
    approval_path = _resolve_omo_ref(omo_root, approval_ref)
    if root not in approval_path.parents or not approval_path.is_file():
        return {"available": False, "task_id": task_id}
    try:
        approval = yaml.safe_load(approval_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, yaml.YAMLError):
        return {"available": False, "task_id": task_id}
    if not isinstance(approval, dict):
        return {"available": False, "task_id": task_id}
    return {
        "available": True,
        "task_id": task_id,
        "task_status": payload.get("status"),
        "approval_status": approval.get("approval_status"),
        "approval_scope": approval.get("approval_scope"),
        "approval_ref": approval_ref,
        "task_sha256": _sha256(task_path),
        "approval_sha256": _sha256(approval_path),
    }


def run_preflight(
    *,
    docs_root: Path,
    evaluation_manifest: Path | None,
    omo_root: Path,
    task_id: str | None,
    production: bool,
    evidence_output: Path | None = None,
    model_acceptance: Path | None = None,
    adjudication_database: Path | None = None,
) -> dict[str, object]:
    checks: list[Check] = []
    endpoint = os.environ.get("BOS_REACHBRIDGE_ENDPOINT", "").strip()
    token = os.environ.get("BOS_REACHBRIDGE_TOKEN", "").strip()
    parsed = urlparse(endpoint)
    endpoint_ok = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    checks.append(
        Check(
            "reachbridge_endpoint",
            endpoint_ok,
            "configured HTTP endpoint"
            if endpoint_ok
            else "HTTP endpoint is missing or invalid",
        )
    )
    checks.append(
        Check(
            "reachbridge_token",
            bool(token),
            "token configured" if token else "token is missing",
        )
    )
    checks.append(
        Check(
            "transport_mode",
            os.environ.get("BOS_REACHBRIDGE_MODE") != "local_hermes"
            if production
            else True,
            "enterprise transport required"
            if production
            else "non-production transport accepted",
        )
    )

    sources = _source_files(docs_root)
    source_ok = bool(sources)
    checks.append(
        Check(
            "source_inventory",
            source_ok,
            f"source files available={len(sources)}"
            if source_ok
            else "no controlled source files found",
        )
    )
    # Hashing proves inventory stability without placing private content in the report.
    inventory, inventory_sha256 = _source_inventory(sources)
    source_scope = _source_scope_metadata(docs_root, sources)

    checks.append(
        _evaluation_check(evaluation_manifest, sources, bind_sources=production)
    )
    checks.append(
        _adjudication_check(adjudication_database, evaluation_manifest)
        if production
        else Check("adjudication_persistence", True, "not required outside production")
    )
    checks.append(
        _model_acceptance_check(model_acceptance, evaluation_manifest)
        if production
        else Check("model_acceptance", True, "not required outside production")
    )
    checks.append(_omo_check(omo_root, task_id))
    ok = all(check.ok for check in checks)
    result = {
        "schema": "kems.production-preflight.v1",
        "status": "ready" if ok else "blocked",
        "production": production,
        "source_count": len(sources),
        "source_scope": source_scope,
        "checks": [check.as_dict() for check in checks],
    }
    if evidence_output is not None:
        evidence = {
            "schema": "kems.production-preflight-evidence.v1",
            "status": result["status"],
            "production": production,
            "run_id": os.environ.get("BOS_MESH_RUN_ID", "").strip() or None,
            "source_count": len(sources),
            "source_scope": source_scope,
            "source_inventory_sha256": inventory_sha256,
            "sources": inventory,
            "evaluation": _evaluation_metadata(evaluation_manifest),
            "adjudication": _adjudication_metadata(adjudication_database),
            "model_acceptance": _model_acceptance_metadata(model_acceptance),
            "omo": _omo_metadata(omo_root, task_id),
            "checks": result["checks"],
        }
        _write_json_atomically(evidence, evidence_output.expanduser().resolve())
        result["evidence_output"] = str(evidence_output.expanduser().resolve())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path(os.environ.get("BOS_DOCS_ROOT", "/Users/xiamingxing/Documents")),
    )
    parser.add_argument(
        "--evaluation-manifest",
        type=Path,
        default=Path(os.environ["KEMS_EVALUATION_MANIFEST"])
        if os.environ.get("KEMS_EVALUATION_MANIFEST")
        else None,
    )
    parser.add_argument(
        "--model-acceptance",
        type=Path,
        default=Path(os.environ["KEMS_MODEL_ACCEPTANCE_REPORT"])
        if os.environ.get("KEMS_MODEL_ACCEPTANCE_REPORT")
        else None,
        help="redacted candidate-model shadow acceptance report",
    )
    parser.add_argument(
        "--adjudication-database",
        type=Path,
        default=Path(os.environ["KEMS_ADJUDICATION_DB"])
        if os.environ.get("KEMS_ADJUDICATION_DB")
        else None,
        help="read-only persistent adjudication SQLite database",
    )
    parser.add_argument(
        "--omo-root",
        type=Path,
        default=Path(
            os.environ.get("KEMS_OMO_ROOT", "/Users/xiamingxing/Workspace/.omo")
        ),
    )
    parser.add_argument("--task-id", default=os.environ.get("KEMS_OMO_TASK_ID"))
    parser.add_argument(
        "--evidence-output",
        type=Path,
        default=Path(os.environ["KEMS_PREFLIGHT_EVIDENCE_OUTPUT"])
        if os.environ.get("KEMS_PREFLIGHT_EVIDENCE_OUTPUT")
        else None,
        help="atomically write redacted preflight evidence JSON",
    )
    parser.add_argument(
        "--production", action="store_true", help="require enterprise HTTP transport"
    )
    args = parser.parse_args()
    result = run_preflight(
        docs_root=args.docs_root.expanduser().resolve(),
        evaluation_manifest=args.evaluation_manifest.expanduser().resolve()
        if args.evaluation_manifest
        else None,
        model_acceptance=args.model_acceptance.expanduser().resolve()
        if args.model_acceptance
        else None,
        adjudication_database=args.adjudication_database.expanduser().resolve()
        if args.adjudication_database
        else None,
        omo_root=args.omo_root.expanduser().resolve(),
        task_id=args.task_id,
        production=args.production,
        evidence_output=args.evidence_output,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
