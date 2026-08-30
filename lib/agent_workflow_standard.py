"""Agent Workflow Standardization — reduce concurrent conflicts by 50%.

Provides four mechanisms:
1. Range declaration — agents declare file ranges they intend to modify
2. Lock status checking — verify locks before modification
3. Modification verification — confirm changes are within declared ranges
4. Signature validation — verify agent identity and authorization

Backward compatible: existing workflows continue to work without changes.
New standardization is opt-in via --standard flag or STANDARD_MODE env var.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parents[1]
STANDARD_STATE_DIR = WORKSPACE / ".omo" / "state" / "agent-workflow-standard"
RANGE_DECLARATIONS_DIR = STANDARD_STATE_DIR / "range-declarations"
LOCK_STATUS_DIR = STANDARD_STATE_DIR / "lock-status"
MODIFICATION_LOG_DIR = STANDARD_STATE_DIR / "modification-log"
SIGNATURE_REGISTRY_PATH = STANDARD_STATE_DIR / "signatures.yaml"

# Environment variable to enable standard mode
STANDARD_MODE_ENV = "AGENT_WORKFLOW_STANDARD_MODE"

# Path pattern validation (allow glob chars `* ? [ ]` for range patterns)
SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_./*?\[\]-]+$")
MAX_RANGE_PATHS = 50
MAX_RANGE_DEPTH = 10

# Lock timeout
LOCK_TIMEOUT_SECONDS = 300  # 5 minutes
LOCK_HEARTBEAT_INTERVAL = 30  # 30 seconds

# Signature validation
SIGNATURE_ALGORITHM = "sha256"
MIN_SIGNATURE_LENGTH = 64


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class StandardError(RuntimeError):
    """Raised when workflow standardization check fails."""


class RangeDeclarationError(StandardError):
    """Raised when range declaration is invalid."""


class LockStatusError(StandardError):
    """Raised when lock status check fails."""


class ModificationVerificationError(StandardError):
    """Raised when modification verification fails."""


class SignatureValidationError(StandardError):
    """Raised when signature validation fails."""


# ---------------------------------------------------------------------------
# Range Declaration
# ---------------------------------------------------------------------------


def validate_range_path(path: str) -> bool:
    """Validate a path is safe for range declaration."""
    if not path or not isinstance(path, str):
        return False
    if not SAFE_PATH_RE.match(path):
        return False
    if ".." in path:
        return False
    if path.startswith("/"):
        return False
    depth = path.count("/")
    if depth > MAX_RANGE_DEPTH:
        return False
    return True


def normalize_range_path(path: str) -> str:
    """Normalize a range path for consistent comparison."""
    return path.strip().rstrip("/")


def create_range_declaration(
    run_id: str,
    agent_id: str,
    paths: list[str],
    *,
    workspace: Path = WORKSPACE,
) -> dict[str, Any]:
    """Create a range declaration for an agent workflow run.

    Args:
        run_id: The workflow run ID
        agent_id: The agent identifier
        paths: List of file paths or glob patterns the agent intends to modify
        workspace: Workspace root path

    Returns:
        Declaration record with metadata

    Raises:
        RangeDeclarationError: If declaration is invalid
    """
    if not run_id:
        raise RangeDeclarationError("RUN_ID_REQUIRED")
    if not agent_id:
        raise RangeDeclarationError("AGENT_ID_REQUIRED")
    if not paths:
        raise RangeDeclarationError("PATHS_REQUIRED")
    if len(paths) > MAX_RANGE_PATHS:
        raise RangeDeclarationError(f"TOO_MANY_PATHS: {len(paths)} > {MAX_RANGE_PATHS}")

    normalized_paths = []
    for path in paths:
        normalized = normalize_range_path(path)
        if not validate_range_path(normalized):
            raise RangeDeclarationError(f"INVALID_PATH: {path}")
        normalized_paths.append(normalized)

    declaration = {
        "run_id": run_id,
        "agent_id": agent_id,
        "paths": sorted(set(normalized_paths)),
        "created_at": datetime.now(UTC).isoformat(),
        "status": "active",
        "hash": _compute_declaration_hash(run_id, agent_id, normalized_paths),
    }

    # Write declaration to state directory
    decl_dir = workspace / RANGE_DECLARATIONS_DIR.relative_to(WORKSPACE)
    decl_dir.mkdir(parents=True, exist_ok=True)
    decl_path = decl_dir / f"{run_id}.yaml"

    with open(decl_path, "w", encoding="utf-8") as f:
        yaml.dump(declaration, f, default_flow_style=False, allow_unicode=True)

    return declaration


def read_range_declaration(
    run_id: str,
    *,
    workspace: Path = WORKSPACE,
) -> dict[str, Any] | None:
    """Read a range declaration for a run ID."""
    decl_path = workspace / RANGE_DECLARATIONS_DIR.relative_to(WORKSPACE) / f"{run_id}.yaml"
    if not decl_path.exists():
        return None
    try:
        with open(decl_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return None


def check_path_in_range(
    file_path: str,
    declared_paths: list[str],
) -> bool:
    """Check if a file path is within declared range paths.

    Supports glob patterns in declared paths.
    """
    import fnmatch

    normalized_file = normalize_range_path(file_path)
    for declared in declared_paths:
        normalized_declared = normalize_range_path(declared)
        # Exact match
        if normalized_file == normalized_declared:
            return True
        # Prefix match (directory-level)
        if normalized_file.startswith(normalized_declared.rstrip("/") + "/"):
            return True
        # Glob match
        if fnmatch.fnmatch(normalized_file, normalized_declared):
            return True
    return False


def _compute_declaration_hash(
    run_id: str,
    agent_id: str,
    paths: list[str],
) -> str:
    """Compute hash for declaration integrity."""
    content = json.dumps(
        {"run_id": run_id, "agent_id": agent_id, "paths": sorted(paths)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{SIGNATURE_ALGORITHM}:{hashlib.sha256(content.encode()).hexdigest()}"


# ---------------------------------------------------------------------------
# Lock Status Checking
# ---------------------------------------------------------------------------


def create_lock(
    run_id: str,
    agent_id: str,
    paths: list[str],
    *,
    workspace: Path = WORKSPACE,
    timeout_seconds: int = LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Create a lock for specified paths.

    Args:
        run_id: The workflow run ID
        agent_id: The agent identifier
        paths: Paths to lock
        workspace: Workspace root path
        timeout_seconds: Lock timeout in seconds

    Returns:
        Lock record

    Raises:
        LockStatusError: If lock cannot be acquired
    """
    if not run_id:
        raise LockStatusError("RUN_ID_REQUIRED")
    if not agent_id:
        raise LockStatusError("AGENT_ID_REQUIRED")
    if not paths:
        raise LockStatusError("PATHS_REQUIRED")

    lock_dir = workspace / LOCK_STATUS_DIR.relative_to(WORKSPACE)
    lock_dir.mkdir(parents=True, exist_ok=True)

    normalized_paths = [normalize_range_path(p) for p in paths]

    # Check for existing locks on overlapping paths
    for lock_file in lock_dir.glob("*.yaml"):
        try:
            existing = yaml.safe_load(lock_file.read_text(encoding="utf-8"))
            if not existing or existing.get("status") != "active":
                continue
            if existing.get("run_id") == run_id:
                continue

            # Check path overlap
            existing_paths = existing.get("paths", [])
            for new_path in normalized_paths:
                for existing_path in existing_paths:
                    if _paths_overlap(new_path, existing_path):
                        # Check if lock is expired
                        created_at = existing.get("created_at", "")
                        if created_at:
                            try:
                                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                                age = (datetime.now(UTC) - created_dt).total_seconds()
                                if age > timeout_seconds:
                                    continue  # Lock expired
                            except ValueError:
                                pass
                        raise LockStatusError(
                            f"PATH_LOCKED: {new_path} locked by {existing.get('agent_id')} "
                            f"(run: {existing.get('run_id')})"
                        )
        except (yaml.YAMLError, OSError):
            continue

    lock = {
        "run_id": run_id,
        "agent_id": agent_id,
        "paths": sorted(set(normalized_paths)),
        "created_at": datetime.now(UTC).isoformat(),
        "expires_at": (datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=timeout_seconds)).isoformat(),
        "status": "active",
        "last_heartbeat": datetime.now(UTC).isoformat(),
    }

    lock_path = lock_dir / f"{run_id}.lock.yaml"
    with open(lock_path, "w", encoding="utf-8") as f:
        yaml.dump(lock, f, default_flow_style=False, allow_unicode=True)

    return lock


def read_lock_status(
    run_id: str,
    *,
    workspace: Path = WORKSPACE,
) -> dict[str, Any] | None:
    """Read lock status for a run ID."""
    lock_path = workspace / LOCK_STATUS_DIR.relative_to(WORKSPACE) / f"{run_id}.lock.yaml"
    if not lock_path.exists():
        return None
    try:
        with open(lock_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return None


def release_lock(
    run_id: str,
    *,
    workspace: Path = WORKSPACE,
) -> bool:
    """Release a lock for a run ID."""
    lock_path = workspace / LOCK_STATUS_DIR.relative_to(WORKSPACE) / f"{run_id}.lock.yaml"
    if lock_path.exists():
        lock_path.unlink()
        return True
    return False


def check_lock_status(
    file_path: str,
    *,
    workspace: Path = WORKSPACE,
) -> dict[str, Any]:
    """Check if a file path is currently locked.

    Returns:
        Dict with 'locked' boolean and 'lock_info' if locked
    """
    lock_dir = workspace / LOCK_STATUS_DIR.relative_to(WORKSPACE)
    if not lock_dir.exists():
        return {"locked": False, "lock_info": None}

    normalized_file = normalize_range_path(file_path)

    for lock_file in lock_dir.glob("*.yaml"):
        try:
            lock = yaml.safe_load(lock_file.read_text(encoding="utf-8"))
            if not lock or lock.get("status") != "active":
                continue

            # Check if lock is expired
            created_at = lock.get("created_at", "")
            if created_at:
                try:
                    created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    age = (datetime.now(UTC) - created_dt).total_seconds()
                    if age > LOCK_TIMEOUT_SECONDS:
                        continue
                except ValueError:
                    pass

            lock_paths = lock.get("paths", [])
            for lock_path in lock_paths:
                if _paths_overlap(normalized_file, lock_path):
                    return {"locked": True, "lock_info": lock}
        except (yaml.YAMLError, OSError):
            continue

    return {"locked": False, "lock_info": None}


def _paths_overlap(path1: str, path2: str) -> bool:
    """Check if two paths overlap (one is prefix of other or they match)."""
    import fnmatch

    n1 = normalize_range_path(path1)
    n2 = normalize_range_path(path2)

    if n1 == n2:
        return True
    if n1.startswith(n2.rstrip("/") + "/"):
        return True
    if n2.startswith(n1.rstrip("/") + "/"):
        return True
    if fnmatch.fnmatch(n1, n2) or fnmatch.fnmatch(n2, n1):
        return True
    return False


# ---------------------------------------------------------------------------
# Modification Verification
# ---------------------------------------------------------------------------


def record_modification(
    run_id: str,
    agent_id: str,
    file_path: str,
    action: str,
    *,
    workspace: Path = WORKSPACE,
) -> dict[str, Any]:
    """Record a file modification for verification.

    Args:
        run_id: The workflow run ID
        agent_id: The agent identifier
        file_path: Path of modified file
        action: Type of modification (create, edit, delete)
        workspace: Workspace root path

    Returns:
        Modification record
    """
    if not run_id:
        raise ModificationVerificationError("RUN_ID_REQUIRED")
    if not file_path:
        raise ModificationVerificationError("FILE_PATH_REQUIRED")
    if action not in ("create", "edit", "delete"):
        raise ModificationVerificationError(f"INVALID_ACTION: {action}")

    mod_dir = workspace / MODIFICATION_LOG_DIR.relative_to(WORKSPACE)
    mod_dir.mkdir(parents=True, exist_ok=True)

    record = {
        "run_id": run_id,
        "agent_id": agent_id,
        "file_path": normalize_range_path(file_path),
        "action": action,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Append to modification log
    log_path = mod_dir / f"{run_id}.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def verify_modification(
    run_id: str,
    file_path: str,
    *,
    workspace: Path = WORKSPACE,
) -> dict[str, Any]:
    """Verify a modification is within declared range.

    Returns:
        Dict with 'valid' boolean and 'reason' if invalid
    """
    # Read range declaration
    declaration = read_range_declaration(run_id, workspace=workspace)
    if not declaration:
        return {
            "valid": False,
            "reason": "NO_RANGE_DECLARATION",
            "file_path": file_path,
        }

    declared_paths = declaration.get("paths", [])
    if not check_path_in_range(file_path, declared_paths):
        return {
            "valid": False,
            "reason": "OUTSIDE_DECLARED_RANGE",
            "file_path": file_path,
            "declared_paths": declared_paths,
        }

    return {"valid": True, "file_path": file_path}


def get_modification_log(
    run_id: str,
    *,
    workspace: Path = WORKSPACE,
) -> list[dict[str, Any]]:
    """Get modification log for a run ID."""
    log_path = workspace / MODIFICATION_LOG_DIR.relative_to(WORKSPACE) / f"{run_id}.jsonl"
    if not log_path.exists():
        return []

    records = []
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        pass
    return records


# ---------------------------------------------------------------------------
# Signature Validation
# ---------------------------------------------------------------------------


def validate_agent_signature(
    agent_id: str,
    run_id: str,
    signature: str,
    *,
    workspace: Path = WORKSPACE,
) -> dict[str, Any]:
    """Validate an agent's signature for a workflow run.

    Args:
        agent_id: The agent identifier
        run_id: The workflow run ID
        signature: The signature to validate
        workspace: Workspace root path

    Returns:
        Dict with 'valid' boolean and 'reason' if invalid
    """
    if not agent_id:
        return {"valid": False, "reason": "AGENT_ID_REQUIRED"}
    if not run_id:
        return {"valid": False, "reason": "RUN_ID_REQUIRED"}
    if not signature:
        return {"valid": False, "reason": "SIGNATURE_REQUIRED"}

    # Validate signature format
    if not signature.startswith(f"{SIGNATURE_ALGORITHM}:"):
        return {"valid": False, "reason": "INVALID_SIGNATURE_FORMAT"}

    hash_part = signature[len(SIGNATURE_ALGORITHM) + 1 :]
    if len(hash_part) < MIN_SIGNATURE_LENGTH:
        return {"valid": False, "reason": "SIGNATURE_TOO_SHORT"}

    if not all(c in "0123456789abcdef" for c in hash_part.lower()):
        return {"valid": False, "reason": "INVALID_SIGNATURE_CHARACTERS"}

    # Compute expected signature
    expected = compute_agent_signature(agent_id, run_id)
    if signature != expected:
        return {
            "valid": False,
            "reason": "SIGNATURE_MISMATCH",
            "expected": expected,
        }

    return {"valid": True, "agent_id": agent_id, "run_id": run_id}


def compute_agent_signature(
    agent_id: str,
    run_id: str,
) -> str:
    """Compute expected signature for an agent and run."""
    content = f"{agent_id}:{run_id}"
    hash_value = hashlib.sha256(content.encode()).hexdigest()
    return f"{SIGNATURE_ALGORITHM}:{hash_value}"


def register_agent_signature(
    agent_id: str,
    run_id: str,
    *,
    workspace: Path = WORKSPACE,
) -> dict[str, Any]:
    """Register an agent signature for a run.

    Returns:
        Registration record with signature
    """
    signature = compute_agent_signature(agent_id, run_id)

    sig_path = workspace / SIGNATURE_REGISTRY_PATH.relative_to(WORKSPACE)
    sig_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing signatures
    signatures: dict[str, Any] = {}
    if sig_path.exists():
        try:
            with open(sig_path, encoding="utf-8") as f:
                signatures = yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError):
            signatures = {}

    # Add new signature
    key = f"{run_id}:{agent_id}"
    signatures[key] = {
        "agent_id": agent_id,
        "run_id": run_id,
        "signature": signature,
        "registered_at": datetime.now(UTC).isoformat(),
    }

    with open(sig_path, "w", encoding="utf-8") as f:
        yaml.dump(signatures, f, default_flow_style=False, allow_unicode=True)

    return signatures[key]


# ---------------------------------------------------------------------------
# Compliance Check
# ---------------------------------------------------------------------------


def check_compliance(
    run_id: str,
    agent_id: str,
    *,
    workspace: Path = WORKSPACE,
) -> dict[str, Any]:
    """Run full compliance check for a workflow run.

    Returns:
        Compliance report with violations list
    """
    violations: list[dict[str, Any]] = []
    checks = {
        "range_declaration": False,
        "lock_status": False,
        "signature_valid": False,
    }

    # Check range declaration
    declaration = read_range_declaration(run_id, workspace=workspace)
    if declaration:
        checks["range_declaration"] = True
    else:
        violations.append(
            {
                "type": "missing_range_declaration",
                "severity": "warning",
                "message": f"No range declaration found for run {run_id}",
            }
        )

    # Check lock status
    lock = read_lock_status(run_id, workspace=workspace)
    if lock and lock.get("status") == "active":
        checks["lock_status"] = True
    else:
        violations.append(
            {
                "type": "no_active_lock",
                "severity": "warning",
                "message": f"No active lock found for run {run_id}",
            }
        )

    # Check signature
    sig_path = workspace / SIGNATURE_REGISTRY_PATH.relative_to(WORKSPACE)
    if sig_path.exists():
        try:
            with open(sig_path, encoding="utf-8") as f:
                signatures = yaml.safe_load(f) or {}
            key = f"{run_id}:{agent_id}"
            if key in signatures:
                stored_sig = signatures[key].get("signature", "")
                expected_sig = compute_agent_signature(agent_id, run_id)
                if stored_sig == expected_sig:
                    checks["signature_valid"] = True
                else:
                    violations.append(
                        {
                            "type": "signature_mismatch",
                            "severity": "error",
                            "message": "Stored signature does not match expected",
                        }
                    )
            else:
                violations.append(
                    {
                        "type": "signature_not_registered",
                        "severity": "warning",
                        "message": f"No signature registered for {agent_id} in run {run_id}",
                    }
                )
        except (yaml.YAMLError, OSError):
            violations.append(
                {
                    "type": "signature_registry_unreadable",
                    "severity": "error",
                    "message": "Cannot read signature registry",
                }
            )
    else:
        violations.append(
            {
                "type": "signature_registry_missing",
                "severity": "warning",
                "message": "Signature registry not found",
            }
        )

    # Check modification log for violations
    mod_log = get_modification_log(run_id, workspace=workspace)
    if declaration and mod_log:
        declared_paths = declaration.get("paths", [])
        for mod in mod_log:
            file_path = mod.get("file_path", "")
            if file_path and not check_path_in_range(file_path, declared_paths):
                violations.append(
                    {
                        "type": "modification_outside_range",
                        "severity": "error",
                        "message": f"Modification to {file_path} outside declared range",
                        "file_path": file_path,
                        "declared_paths": declared_paths,
                    }
                )

    return {
        "run_id": run_id,
        "agent_id": agent_id,
        "compliant": not violations,
        "checks": checks,
        "violations": violations,
        "checked_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def cleanup_expired_locks(
    *,
    workspace: Path = WORKSPACE,
    timeout_seconds: int = LOCK_TIMEOUT_SECONDS,
) -> int:
    """Clean up expired locks.

    Returns:
        Number of locks cleaned up
    """
    lock_dir = workspace / LOCK_STATUS_DIR.relative_to(WORKSPACE)
    if not lock_dir.exists():
        return 0

    cleaned = 0
    for lock_file in lock_dir.glob("*.yaml"):
        try:
            lock = yaml.safe_load(lock_file.read_text(encoding="utf-8"))
            if not lock:
                continue

            created_at = lock.get("created_at", "")
            if created_at:
                try:
                    created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    age = (datetime.now(UTC) - created_dt).total_seconds()
                    if age > timeout_seconds:
                        lock_file.unlink()
                        cleaned += 1
                except ValueError:
                    pass
        except (yaml.YAMLError, OSError):
            continue

    return cleaned


def get_standard_status(
    *,
    workspace: Path = WORKSPACE,
) -> dict[str, Any]:
    """Get overall standardization status."""
    lock_dir = workspace / LOCK_STATUS_DIR.relative_to(WORKSPACE)
    decl_dir = workspace / RANGE_DECLARATIONS_DIR.relative_to(WORKSPACE)

    active_locks = 0
    if lock_dir.exists():
        for lock_file in lock_dir.glob("*.yaml"):
            try:
                lock = yaml.safe_load(lock_file.read_text(encoding="utf-8"))
                if lock and lock.get("status") == "active":
                    active_locks += 1
            except (yaml.YAMLError, OSError):
                pass

    active_declarations = 0
    if decl_dir.exists():
        active_declarations = len(list(decl_dir.glob("*.yaml")))

    return {
        "standard_mode_enabled": os.environ.get(STANDARD_MODE_ENV, "").lower()
        in (
            "1",
            "true",
            "yes",
        ),
        "active_locks": active_locks,
        "active_declarations": active_declarations,
        "state_dir": str(STANDARD_STATE_DIR),
    }
