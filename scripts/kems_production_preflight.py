#!/usr/bin/env python3
"""Fail-closed, content-free preflight for the KEMS production lane."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

SOURCE_PATTERNS = (
    "*-auto-seeyon-oa-pending.md",
    "*-auto-netease-mailmaster.md",
    "*-auto-apple-mail.md",
    "*-auto-iphone-sms.md",
)
FORBIDDEN_KEYS = {"body", "content", "ocr_text", "raw_text", "text"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
APPROVED_STATUSES = {"approved", "dispatched", "executing", "verified", "closed"}


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


def _evaluation_check(path: Path | None) -> Check:
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
    samples = payload.get("samples")
    if not isinstance(samples, list) or not samples:
        return Check("evaluation_manifest", False, "manifest has no samples")
    sample_ids: set[str] = set()
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
        sample_ids.add(sample_id)
    return Check(
        "evaluation_manifest", True, f"verified adjudicated samples={len(samples)}"
    )


def _omo_check(omo_root: Path, task_id: str | None) -> Check:
    if not task_id:
        return Check("omo_approval", False, "missing approved OMO task id")
    candidates = (
        omo_root / "tasks" / "active" / f"{task_id}.yaml",
        omo_root / "tasks" / "planned" / f"{task_id}.yaml",
        omo_root / "tasks" / "completed" / f"{task_id}.yaml",
    )
    task_path = next((path for path in candidates if path.is_file()), None)
    if task_path is None:
        return Check("omo_approval", False, "approved OMO task is unavailable")
    try:
        import yaml

        payload = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        return Check(
            "omo_approval", False, f"invalid OMO task metadata: {type(exc).__name__}"
        )
    if not isinstance(payload, dict):
        return Check("omo_approval", False, "OMO task metadata must be an object")
    status = str(payload.get("status", ""))
    approval_ref = payload.get("approval_ref")
    approval_state = payload.get("approval_state")
    if (
        status not in APPROVED_STATUSES
        or not approval_ref
        or approval_state not in {"approved", "granted"}
    ):
        return Check("omo_approval", False, "OMO task is not approved for production")
    return Check("omo_approval", True, "approved OMO task metadata confirmed")


def run_preflight(
    *,
    docs_root: Path,
    evaluation_manifest: Path | None,
    omo_root: Path,
    task_id: str | None,
    production: bool,
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
    if sources:
        _ = [_sha256(path) for path in sources]

    checks.append(_evaluation_check(evaluation_manifest))
    checks.append(_omo_check(omo_root, task_id))
    ok = all(check.ok for check in checks)
    return {
        "schema": "kems.production-preflight.v1",
        "status": "ready" if ok else "blocked",
        "production": production,
        "source_count": len(sources),
        "checks": [check.as_dict() for check in checks],
    }


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
        "--omo-root",
        type=Path,
        default=Path(
            os.environ.get("KEMS_OMO_ROOT", "/Users/xiamingxing/Workspace/.omo")
        ),
    )
    parser.add_argument("--task-id", default=os.environ.get("KEMS_OMO_TASK_ID"))
    parser.add_argument(
        "--production", action="store_true", help="require enterprise HTTP transport"
    )
    args = parser.parse_args()
    result = run_preflight(
        docs_root=args.docs_root.expanduser().resolve(),
        evaluation_manifest=args.evaluation_manifest.expanduser().resolve()
        if args.evaluation_manifest
        else None,
        omo_root=args.omo_root.expanduser().resolve(),
        task_id=args.task_id,
        production=args.production,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
