#!/usr/bin/env python3
"""Read-only preflight for internal pipeline scene activation.

Mirrors external-activation-preflight.py but validates internal infrastructure
capabilities (make targets, project-registry) instead of external resource
catalog entries. Never writes OMO state, creates a WorkflowRun, loads a
provider, or changes admission.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "internal-activation-preflight/v1"
SCENE_CARD_SCHEMA = "scene-card/v1"
CAPABILITY_PREFIX = "ref://capability/"
EVIDENCE_PR_PATTERN = re.compile(r"evidence://github/pr/(\d+)")
INTERNAL_PERMISSION_PREFIX = "permission://internal/"


class PreflightInputError(ValueError):
    """Raised when input is unsafe or structurally invalid."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _check_make_target(root: Path, target_name: str) -> bool:
    """Check if a make target exists by reading the Makefile."""
    makefile = root / "Makefile"
    if not makefile.exists():
        return False
    try:
        content = makefile.read_text(encoding="utf-8")
    except OSError:
        return False
    # Match "target-name:" at line start (make target definition)
    pattern = re.compile(rf"^{re.escape(target_name)}\s*:", re.MULTILINE)
    return bool(pattern.search(content))


def _check_make_target_prefix(root: Path, name: str) -> str | None:
    """If exact target not found, check prefix match (e.g. 'agent-workflow' → 'agent-workflow-bootstrap')."""
    makefile = root / "Makefile"
    if not makefile.exists():
        return None
    try:
        content = makefile.read_text(encoding="utf-8")
    except OSError:
        return None
    prefix = name.split("-")[0] if "-" in name else name
    pattern = re.compile(rf"^({re.escape(prefix)}[\w-]*)\s*:", re.MULTILINE)
    match = pattern.search(content)
    return match.group(1) if match else None


def _verify_evidence_ref(root: Path, ref: str) -> dict[str, Any]:
    """Verify an evidence ref points to a real merged PR."""
    match = EVIDENCE_PR_PATTERN.search(ref)
    if not match:
        return {"ref": ref, "status": "unknown_format", "detail": "not evidence://github/pr/<N>"}
    pr_num = match.group(1)
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--all", "--grep", f"#{pr_num}"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.stdout.strip():
            return {"ref": ref, "status": "verified", "pr": pr_num, "detail": result.stdout.strip().split("\n")[0][:80]}
        return {"ref": ref, "status": "missing", "pr": pr_num, "detail": f"PR #{pr_num} not found in git log"}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ref": ref, "status": "error", "pr": pr_num, "detail": str(exc)[:100]}


def _verify_internal_permission(scene_card: dict[str, Any]) -> dict[str, Any]:
    """Verify permission_ref uses internal RBAC format with scope."""
    perm_ref = _text(scene_card.get("permission_ref"))
    scope = scene_card.get("permission_scope", [])
    if not perm_ref:
        return {"status": "missing", "detail": "permission_ref is empty"}
    if not perm_ref.startswith(INTERNAL_PERMISSION_PREFIX):
        return {"status": "invalid_format", "detail": f"expected {INTERNAL_PERMISSION_PREFIX} prefix"}
    if not isinstance(scope, list) or not scope:
        return {"status": "missing_scope", "detail": "permission_scope is empty or not a list"}
    return {"status": "valid", "scope": scope}


def _scene_card_check(scene_card: dict[str, Any]) -> dict[str, Any]:
    """Validate scene card fields (reuse intake module for base validation)."""
    missing: list[str] = []

    # Basic field presence check (same as external preflight)
    required_fields = (
        "scene_id", "journey_id", "goal", "trigger", "input_contract",
        "result_contract", "outcome_metric", "consumer", "approver", "owner",
        "failure_cost", "data_classification", "data_scope", "operator",
        "permission_ref", "rollback_plan",
    )
    for field in required_fields:
        if not _text(scene_card.get(field)):
            missing.append(field)

    sample_refs = scene_card.get("sample_refs", [])
    if not isinstance(sample_refs, list) or not 3 <= len(sample_refs) <= 10:
        missing.append("sample_refs:3-10")

    activation_refs = scene_card.get("activation_evidence_refs", [])
    if not isinstance(activation_refs, list) or not activation_refs:
        missing.append("activation_evidence_refs")

    required_capabilities = scene_card.get("required_capabilities", [])
    if not isinstance(required_capabilities, list) or not required_capabilities:
        missing.append("required_capabilities")

    scene_type = _text(scene_card.get("scene_type"))
    if scene_type != "internal_pipeline":
        missing.append("scene_type:must_be_internal_pipeline")

    # activation/lifecycle must stay locked (same fabric red line as external)
    if scene_card.get("activation") not in {None, "forbidden"}:
        missing.append("activation_must_be_forbidden")
    if scene_card.get("lifecycle") not in {None, "proposal_only"}:
        missing.append("lifecycle_must_be_proposal_only")

    return {
        "missing_fields": sorted(set(missing)),
        "sample_ref_count": len(sample_refs) if isinstance(sample_refs, list) else 0,
        "activation_evidence_ref_count": len(activation_refs) if isinstance(activation_refs, list) else 0,
        "required_capabilities": required_capabilities if isinstance(required_capabilities, list) else [],
        "scene_type": scene_type,
    }


def _capability_checks(required_capabilities: list[str], root: Path) -> list[dict[str, Any]]:
    """Check each required capability against make targets."""
    checks: list[dict[str, Any]] = []
    for capability in required_capabilities:
        if not capability.startswith(CAPABILITY_PREFIX):
            checks.append({
                "capability": capability,
                "status": "invalid_format",
                "detail": f"expected {CAPABILITY_PREFIX} prefix",
            })
            continue
        name = capability[len(CAPABILITY_PREFIX):]
        if _check_make_target(root, name):
            checks.append({
                "capability": capability,
                "make_target": name,
                "status": "available",
            })
        else:
            prefix_match = _check_make_target_prefix(root, name)
            if prefix_match:
                checks.append({
                    "capability": capability,
                    "make_target": prefix_match,
                    "status": "available",
                    "detail": f"prefix match: {name} → {prefix_match}",
                })
            else:
                checks.append({
                    "capability": capability,
                    "make_target": name,
                    "status": "unavailable",
                    "detail": f"make target '{name}' not found in Makefile",
                })
    return checks


def build_preflight(
    scene_card: dict[str, Any],
    *,
    root: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a deterministic, non-activating internal pipeline readiness projection."""
    observed_at = (now or datetime.now(UTC)).isoformat()

    schema = scene_card.get("schema")
    if schema is not None and schema != SCENE_CARD_SCHEMA:
        raise PreflightInputError(f"scene card must use {SCENE_CARD_SCHEMA}")

    scene_check = _scene_card_check(scene_card)
    capability_checks = _capability_checks(scene_check["required_capabilities"], root)

    # Verify sample_refs and activation_evidence_refs
    sample_refs = scene_card.get("sample_refs", [])
    evidence_checks = [_verify_evidence_ref(root, ref) for ref in sample_refs]
    activation_refs = scene_card.get("activation_evidence_refs", [])
    activation_evidence_checks = [_verify_evidence_ref(root, ref) for ref in activation_refs]

    permission_check = _verify_internal_permission(scene_card)

    # Aggregate missing
    missing = list(scene_check["missing_fields"])
    if any(c["status"] == "unavailable" or c["status"] == "invalid_format" for c in capability_checks):
        missing.append("internal_capability_availability")
    if any(e["status"] == "missing" for e in evidence_checks):
        missing.append("sample_evidence_verification")
    if any(e["status"] == "missing" for e in activation_evidence_checks):
        missing.append("activation_evidence_verification")
    if permission_check["status"] != "valid":
        missing.append(f"permission:{permission_check['status']}")

    if missing:
        status = "blocked"
        next_action = "resolve_missing_internal_capabilities_or_evidence"
    else:
        status = "ready_for_admission_preview"
        next_action = "submit_omo_admission_preview"

    return {
        "schema": SCHEMA,
        "mode": "read_only_preflight",
        "activation": "forbidden",
        "scene": {
            "scene_id": _text(scene_card.get("scene_id")),
            "journey_id": _text(scene_card.get("journey_id")),
            "outcome_metric": _text(scene_card.get("outcome_metric")),
            "scene_type": scene_check["scene_type"],
        },
        "status": status,
        "next_action": next_action,
        "missing_fields": sorted(set(missing)),
        "scene_card": scene_check,
        "capability_checks": capability_checks,
        "evidence_checks": evidence_checks,
        "activation_evidence_checks": activation_evidence_checks,
        "permission_check": permission_check,
        "observed_at": observed_at,
        "side_effects": {
            "omo_written": False,
            "provider_called": False,
            "workflow_created": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--scene-card", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        import yaml

        with open(args.scene_card, encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
        scene_card = docs[-1] if len(docs) > 1 else docs[0]
        if not isinstance(scene_card, dict):
            raise PreflightInputError("scene card YAML must produce an object")
    except (OSError, ValueError) as exc:
        print(f"internal-scene-preflight: {exc}", file=sys.stderr)
        return 2

    try:
        result = build_preflight(scene_card, root=args.root)
    except PreflightInputError as exc:
        print(f"internal-scene-preflight: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
