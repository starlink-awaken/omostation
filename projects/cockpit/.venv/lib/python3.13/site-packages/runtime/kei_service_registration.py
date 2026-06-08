"""KEI Service Registration Extension — Audit & Validation for matrix.yaml/d entries.

Implements a KEI extension that validates new service entries when YAML is
written to matrix.yaml or matrix.d/, and logs audit records via kei_sandbox.

Usage:
    from runtime.kei_service_registration import validate_service_entry, validate_matrix_file

    # Validate a single service entry
    result = validate_service_entry({"name": "my-svc", "type": "daemon", ...})

    # Validate an entire matrix.yaml file
    result = validate_matrix_file("/path/to/matrix.yaml")
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Try to import the sandbox audit function; gracefully degrade if unavailable
try:
    from runtime.kei_sandbox import record_audit as _sandbox_audit

    _has_audit = True
except ImportError:
    _sandbox_audit = None
    _has_audit = False

# Extension identity for KEI audit trail
EXTENSION_ID = "ecos.kernel.service_registration"
EXTENSION_VERSION = "1.0.0"

# Required fields for a valid service entry
REQUIRED_SERVICE_FIELDS = {"name", "type", "status"}
RECOMMENDED_SERVICE_FIELDS = {
    "port",
    "health_url",
    "deploy_host",
    "deploy_path",
    "log_path",
    "start_command",
}

# Valid service types
VALID_TYPES = {"daemon", "mcp-server", "web", "worker", "cron", "bridge", "agent"}

# Valid statuses
VALID_STATUSES = {"running", "stopped", "starting", "degraded", "failed", "registered"}

# Path patterns for managed service directories
RUNTIME_HOME = Path.home() / "runtime"
MATRIX_FILE = RUNTIME_HOME / "matrix.yaml"
MATRIX_D_DIR = RUNTIME_HOME / "matrix.d"


def _audit(action: str, status: str, details: str) -> None:
    """Write a KEI audit record."""
    if _has_audit and _sandbox_audit is not None:
        try:
            _sandbox_audit(action, EXTENSION_ID, status, details)
        except Exception:
            pass  # Best-effort

    # Also write to local audit file as fallback
    audit_dir = RUNTIME_HOME / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "kei-service-registration.jsonl"
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "extension_id": EXTENSION_ID,
        "status": status,
        "details": details,
    }
    try:
        fd = os.open(str(audit_file), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        os.write(fd, (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8"))
        os.close(fd)
    except OSError:
        pass


def validate_service_entry(entry: dict, source: str = "unknown") -> dict:
    """Validate a single service entry.

    Args:
        entry: The service entry dict (e.g., name, type, port, status, ...).
        source: Human-readable source identifier (file path or context).

    Returns:
        dict with keys: valid (bool), errors (list), warnings (list), entry_name (str|None)
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "entry_name": entry.get("name"),
        "source": source,
    }

    name = entry.get("name", "")
    if not name:
        result["errors"].append("Service entry missing required 'name' field")
        result["valid"] = False
    elif not isinstance(name, str) or not re.match(r"^[a-zA-Z0-9._-]+$", name):
        result["errors"].append(
            f"Service name '{name}' contains invalid characters (use [a-zA-Z0-9._-])"
        )
        result["valid"] = False

    # Check required fields
    for field in REQUIRED_SERVICE_FIELDS:
        if field not in entry or entry[field] is None:
            result["errors"].append(
                f"Service '{name or '?'}' missing required field: {field}"
            )
            result["valid"] = False

    # Validate type
    svc_type = entry.get("type", "")
    if svc_type and svc_type not in VALID_TYPES:
        result["warnings"].append(
            f"Service '{name}' has unrecognized type '{svc_type}'. "
            f"Valid types: {', '.join(sorted(VALID_TYPES))}"
        )

    # Validate status
    status = entry.get("status", "")
    if status and status not in VALID_STATUSES:
        result["warnings"].append(
            f"Service '{name}' has unrecognized status '{status}'. "
            f"Valid statuses: {', '.join(sorted(VALID_STATUSES))}"
        )

    # Warn about missing recommended fields
    for field in RECOMMENDED_SERVICE_FIELDS:
        if field not in entry or entry[field] is None:
            result["warnings"].append(f"Service '{name}' missing recommended field: {field}")

    # Validate port format if provided
    port = entry.get("port")
    if port is not None:
        try:
            p = int(port)
            if p < 1 or p > 65535:
                result["errors"].append(
                    f"Service '{name}' has invalid port {port} (must be 1-65535)"
                )
                result["valid"] = False
        except (ValueError, TypeError):
            if port is not None and port != "null":
                result["warnings"].append(
                    f"Service '{name}' has non-numeric port '{port}'"
                )

    # Log audit
    if result["valid"]:
        _audit("validate", "pass", f"Service '{name}' validated OK from {source}")
    else:
        _audit(
            "validate",
            "fail",
            f"Service '{name or '?'}' validation FAILED: {'; '.join(result['errors'])} (source: {source})",
        )

    return result


def validate_matrix_file(filepath: str | Path) -> dict:
    """Validate all service entries in a matrix.yaml-style file.

    Args:
        filepath: Path to the YAML file to validate.

    Returns:
        dict with: valid (bool), file (str), service_count (int),
                   services (list of individual validation results),
                   errors (list), warnings (list)
    """
    path = Path(filepath)
    result = {
        "valid": True,
        "file": str(path),
        "service_count": 0,
        "services": [],
        "errors": [],
        "warnings": [],
    }

    if not path.exists():
        result["valid"] = False
        result["errors"].append(f"File not found: {path}")
        _audit("validate", "fail", f"Matrix file not found: {path}")
        return result

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        result["valid"] = False
        result["errors"].append(f"YAML parse error: {e}")
        _audit("validate", "fail", f"YAML parse error in {path}: {e}")
        return result
    except Exception as e:
        result["valid"] = False
        result["errors"].append(f"Read error: {e}")
        _audit("validate", "fail", f"Read error in {path}: {e}")
        return result

    if not isinstance(data, dict):
        result["valid"] = False
        result["errors"].append("Root element is not a mapping")
        return result

    # Handle matrix.yaml format: runtime_matrix.services[...]
    services = []
    if "runtime_matrix" in data:
        services = data["runtime_matrix"].get("services", [])
    elif "services" in data:
        services = data["services"]
    elif isinstance(data, list):
        services = data

    if not isinstance(services, list):
        result["valid"] = False
        result["errors"].append("'services' is not a list")
        return result

    result["service_count"] = len(services)
    any_invalid = False

    for i, entry in enumerate(services):
        if not isinstance(entry, dict):
            result["services"].append(
                {
                    "valid": False,
                    "errors": [f"Entry at index {i} is not a mapping"],
                    "warnings": [],
                    "entry_name": f"index_{i}",
                    "source": str(path),
                }
            )
            any_invalid = True
            continue

        svc_result = validate_service_entry(entry, source=str(path))
        result["services"].append(svc_result)
        if not svc_result["valid"]:
            any_invalid = True
            result["errors"].extend(svc_result["errors"])
        result["warnings"].extend(svc_result["warnings"])

    result["valid"] = not any_invalid
    return result


def validate_matrix_d() -> dict:
    """Validate all .yaml/.yml files in matrix.d/ directory."""
    result = {
        "valid": True,
        "directory": str(MATRIX_D_DIR),
        "files_validated": 0,
        "file_results": [],
        "errors": [],
        "warnings": [],
    }

    if not MATRIX_D_DIR.exists():
        result["errors"].append(f"matrix.d/ not found at {MATRIX_D_DIR}")
        result["valid"] = False
        return result

    for ext in ("*.yaml", "*.yml"):
        for fpath in sorted(MATRIX_D_DIR.glob(ext)):
            file_result = validate_matrix_file(fpath)
            result["file_results"].append(file_result)
            result["files_validated"] += 1
            if not file_result["valid"]:
                result["valid"] = False
                result["errors"].extend(file_result["errors"])
            result["warnings"].extend(file_result["warnings"])

    return result


def register_service_from_file(filepath: str | Path) -> dict:
    """Register a service from a YAML file.

    This is the main entry point for matrix.d/ drop-in registration.
    Validates the file, then if valid, marks the service as registered.

    Args:
        filepath: Path to a YAML file containing a single service entry.

    Returns:
        dict with registration result.
    """
    path = Path(filepath)
    result = {
        "registered": False,
        "file": str(path),
        "service_name": None,
        "validation": None,
        "errors": [],
    }

    # Validate the file
    validation = validate_matrix_file(path)
    result["validation"] = validation

    if not validation["valid"]:
        result["errors"] = validation["errors"]
        _audit("execute", "blocked", f"Service registration blocked for {path}: {validation['errors']}")
        return result

    # Extract service name from the first valid entry
    for svc in validation.get("services", []):
        if svc.get("valid") and svc.get("entry_name"):
            result["service_name"] = svc["entry_name"]
            result["registered"] = True
            _audit(
                "execute",
                "pass",
                f"Service '{svc['entry_name']}' registered from {path}",
            )
            break

    return result


def validate_all() -> dict:
    """Validate both matrix.yaml and all matrix.d/ entries.

    Convenience function to run a full validation sweep.

    Returns:
        dict with overall validation result.
    """
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "extension_id": EXTENSION_ID,
        "extension_version": EXTENSION_VERSION,
        "matrix_yaml": None,
        "matrix_d": None,
        "overall_valid": True,
        "total_services": 0,
        "total_errors": 0,
        "total_warnings": 0,
    }

    # Validate matrix.yaml
    if MATRIX_FILE.exists():
        mf_result = validate_matrix_file(MATRIX_FILE)
        results["matrix_yaml"] = mf_result
        results["total_services"] += mf_result.get("service_count", 0)
        if not mf_result["valid"]:
            results["overall_valid"] = False
            results["total_errors"] += len(mf_result["errors"])
        results["total_warnings"] += len(mf_result["warnings"])

    # Validate matrix.d/
    if MATRIX_D_DIR.exists():
        md_result = validate_matrix_d()
        results["matrix_d"] = md_result
        results["total_services"] += sum(
            fr.get("service_count", 0) for fr in md_result.get("file_results", [])
        )
        if not md_result["valid"]:
            results["overall_valid"] = False
            results["total_errors"] += len(md_result["errors"])
        results["total_warnings"] += len(md_result["warnings"])

    # Final audit
    if results["overall_valid"]:
        _audit(
            "validate",
            "pass",
            f"Service registration audit complete: {results['total_services']} services, all valid",
        )
    else:
        _audit(
            "validate",
            "fail",
            f"Service registration audit: {results['total_services']} services, "
            f"{results['total_errors']} error(s), {results['total_warnings']} warning(s)",
        )

    return results


# ── CLI Entry Point ───────────────────────────────────────────────────────────

def main():
    """CLI entry point for manual validation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="KEI Service Registration — validate matrix.yaml/d entries"
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="One or more YAML files to validate (default: matrix.yaml + matrix.d/)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="Output as JSON (default: true)",
    )
    args = parser.parse_args()

    if args.files:
        results = [validate_matrix_file(f) for f in args.files]
    else:
        results = validate_all()

    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
