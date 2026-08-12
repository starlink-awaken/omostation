"""Read-only observation preflight for declared external agent workers.

This command is deliberately *not* a scheduler, selector, dispatcher, model
client, credential reader, or configuration writer.  It joins the existing
provider and worker declarations into an observation receipt with a SHA-256
checksum that can be independently verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "agent-pool-observation/v1"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_QUOTA_MAX_AGE_SECONDS = 900
ROUTE_REF = "bos://compute/aetherforge/infer"
SAFE_EXECUTABLES = frozenset(
    {
        "agy",
        "claude",
        "codebuddy",
        "codex",
        "crush",
        "grok",
        "kilo",
        "mimo",
        "omp",
        "opencode",
        "pi",
        "reasonix",
    }
)
SAFE_ARG_RE = re.compile(r"^[A-Za-z0-9_./:=+-]+$")
CODEXBAR_PROVIDERS = frozenset({"claude", "codex", "grok", "kilo", "mimo", "opencode"})
QUOTA_WINDOW_NAMES = frozenset({"primary", "secondary", "tertiary"})
SENSITIVE_KEY_RE = re.compile(r"account|email|token|key|identity|loginmethod", re.IGNORECASE)
SAFE_WINDOW_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


def canonical_json(value: Mapping[str, Any]) -> str:
    """Encode a receipt deterministically for its integrity digest."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def manifest_digest(manifest: Mapping[str, Any]) -> str:
    """Return the SHA-256 of the manifest excluding its self-referential digest."""
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_digest"}
    return hashlib.sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()


def _load_last_yaml_document(path: Path) -> dict[str, Any]:
    try:
        documents = [document for document in yaml.safe_load_all(path.read_text(encoding="utf-8")) if document]
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"registry_unreadable:{path.name}") from exc
    if not documents or not isinstance(documents[-1], dict):
        raise ValueError(f"registry_invalid:{path.name}")
    return documents[-1]


def _default_runner(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)


def _utc_now(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _safe_version_argv(provider: Mapping[str, Any]) -> list[str] | None:
    launch_argv = provider.get("launch_argv")
    argv = provider.get("version_probe_argv")
    if not isinstance(launch_argv, list) or not launch_argv or not isinstance(launch_argv[0], str):
        return None
    executable = launch_argv[0]
    if executable not in SAFE_EXECUTABLES:
        return None
    if not isinstance(argv, list) or len(argv) != 2 or argv[0] != executable or argv[1] != "--version":
        return None
    if not all(isinstance(part, str) and SAFE_ARG_RE.fullmatch(part) for part in argv):
        return None
    return list(argv)


def _probe_version(
    provider: Mapping[str, Any], runner: Callable[[list[str], float], subprocess.CompletedProcess[str]], timeout: float
) -> dict[str, str]:
    argv = _safe_version_argv(provider)
    if argv is None:
        return {"state": "error", "reason": "unsafe_argv"}
    try:
        result = runner(argv, timeout)
    except FileNotFoundError:
        return {"state": "unavailable", "reason": "command_missing"}
    except subprocess.TimeoutExpired:
        return {"state": "error", "reason": "probe_timeout"}
    except OSError:
        return {"state": "error", "reason": "probe_error"}
    if result.returncode != 0:
        return {"state": "unavailable", "reason": "probe_nonzero"}
    version = result.stdout.strip().splitlines()[0][:200] if result.stdout else ""
    return {"state": "observed", "version": version}


def _quota_argv(quota_observer: Mapping[str, Any], provider_name: str) -> list[str] | None:
    executable = quota_observer.get("executable")
    prefix = quota_observer.get("argv_prefix")
    if executable != "codexbar" or prefix != ["codexbar", "usage"]:
        return None
    return [
        executable,
        "usage",
        "--provider",
        provider_name,
        "--format",
        "json",
        "--status",
        "--no-credits",
        "--no-color",
    ]


def _contains_sensitive_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            (isinstance(key, str) and SENSITIVE_KEY_RE.search(key) is not None) or _contains_sensitive_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _project_quota_window(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict) or _contains_sensitive_key(value):
        return None
    used_percent = value.get("usedPercent")
    if not isinstance(used_percent, (int, float)):
        return None
    entry: dict[str, Any] = {"used_percent": used_percent}
    resets_at = value.get("resetsAt")
    if isinstance(resets_at, str):
        entry["resets_at"] = resets_at
    return entry


def _project_quota_windows(usage: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    windows: dict[str, dict[str, Any]] = {}
    for name in QUOTA_WINDOW_NAMES:
        projected = _project_quota_window(usage.get(name))
        if projected is not None:
            windows[name] = projected
    extra = usage.get("extraRateWindows")
    if isinstance(extra, dict) and not _contains_sensitive_key(extra):
        for name, value in extra.items():
            if not isinstance(name, str) or not SAFE_WINDOW_NAME_RE.fullmatch(name) or SENSITIVE_KEY_RE.search(name):
                continue
            projected = _project_quota_window(value)
            if projected is not None:
                windows[f"extra:{name}"] = projected
    return windows


def _sanitize_quota(payload: object, provider_name: str, now: datetime, max_age_seconds: int) -> dict[str, Any]:
    rows = payload if isinstance(payload, list) else [payload]
    row = next((item for item in rows if isinstance(item, dict) and item.get("provider") == provider_name), None)
    if row is None:
        return {"state": "unknown", "reason": "malformed"}
    usage = row.get("usage")
    if not isinstance(usage, dict):
        return {"state": "unknown", "reason": "malformed"}
    timestamp = _parse_timestamp(usage.get("updatedAt") or row.get("updatedAt") or row.get("observedAt"))
    if timestamp is None:
        return {"state": "unknown", "reason": "timestamp_missing"}
    confidence = usage.get("dataConfidence")
    if not isinstance(confidence, str) or confidence.lower() in {"", "unknown"}:
        return {"state": "unknown", "reason": "confidence_unknown"}
    if (now - timestamp).total_seconds() > max_age_seconds:
        return {"state": "unknown", "reason": "stale"}
    windows = _project_quota_windows(usage)
    if not windows:
        return {"state": "unknown", "reason": "malformed"}
    return {"state": "observed", "confidence": confidence, "windows": windows}


def _observe_quota(
    provider: Mapping[str, Any],
    quota_observer: Mapping[str, Any],
    runner: Callable[[list[str], float], subprocess.CompletedProcess[str]],
    now: datetime,
    timeout: float,
) -> dict[str, Any]:
    observation = provider.get("quota_observation")
    if not isinstance(observation, dict) or observation.get("source") != "codexbar":
        return {"state": "unknown", "reason": "not_configured"}
    provider_name = observation.get("provider")
    if not isinstance(provider_name, str) or provider_name not in CODEXBAR_PROVIDERS:
        return {"state": "unknown", "reason": "unsupported_provider"}
    argv = _quota_argv(quota_observer, provider_name)
    if argv is None:
        return {"state": "unknown", "reason": "unsafe_argv"}
    configured_age = observation.get("max_age_seconds", DEFAULT_QUOTA_MAX_AGE_SECONDS)
    max_age_seconds = configured_age if isinstance(configured_age, int) and configured_age >= 0 else DEFAULT_QUOTA_MAX_AGE_SECONDS
    try:
        result = runner(argv, timeout)
    except FileNotFoundError:
        return {"state": "unknown", "reason": "adapter_missing"}
    except subprocess.TimeoutExpired:
        return {"state": "unknown", "reason": "adapter_timeout"}
    except OSError:
        return {"state": "unknown", "reason": "adapter_error"}
    if result.returncode != 0:
        return {"state": "unknown", "reason": "adapter_nonzero"}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"state": "unknown", "reason": "malformed"}
    return _sanitize_quota(payload, provider_name, now, max_age_seconds)


def _observe_compute(
    compute_plane: Mapping[str, Any],
    runner: Callable[[list[str], float], subprocess.CompletedProcess[str]],
    timeout: float,
) -> dict[str, str]:
    route_ref = compute_plane.get("route_uri", ROUTE_REF)
    argv = compute_plane.get("health_probe_argv")
    if not isinstance(route_ref, str) or not isinstance(argv, list) or argv != ["omlxc", "status", "--json"]:
        return {"route_ref": ROUTE_REF, "state": "error", "reason": "unsafe_argv"}
    result_base = {"route_ref": route_ref}
    try:
        result = runner(argv, timeout)
    except FileNotFoundError:
        return result_base | {"state": "unavailable", "reason": "command_missing"}
    except subprocess.TimeoutExpired:
        return result_base | {"state": "error", "reason": "probe_timeout"}
    except OSError:
        return result_base | {"state": "error", "reason": "probe_error"}
    if result.returncode != 0:
        return result_base | {"state": "error", "reason": "probe_nonzero"}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return result_base | {"state": "error", "reason": "malformed"}
    if not isinstance(payload, dict):
        return result_base | {"state": "error", "reason": "malformed"}
    if payload.get("status") == "ready":
        return result_base | {"state": "observed", "reason": "reported_ready"}
    return result_base | {"state": "degraded", "reason": "reported_degraded"}


def observe_pool(
    providers_path: Path,
    workers_path: Path,
    *,
    runner: Callable[[list[str], float], subprocess.CompletedProcess[str]] = _default_runner,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Build a redacted, non-admitting observation receipt from declared SSOT."""
    providers_document = _load_last_yaml_document(providers_path)
    workers_document = _load_last_yaml_document(workers_path)
    providers = providers_document.get("providers", [])
    workers = workers_document.get("workers", [])
    if not isinstance(providers, list) or not isinstance(workers, list):
        raise TypeError("registry_invalid:expected_lists")
    provider_by_id = {
        provider.get("id"): provider
        for provider in providers
        if isinstance(provider, dict) and isinstance(provider.get("id"), str)
    }
    observation_contract = providers_document.get("observation_contract", {})
    if not isinstance(observation_contract, dict):
        observation_contract = {}
    quota_observer = providers_document.get("quota_observer", {})
    if not isinstance(quota_observer, dict):
        quota_observer = {}
    version_timeout = observation_contract.get("version_probe_timeout_seconds", timeout)
    quota_timeout = observation_contract.get("quota_probe_timeout_seconds", timeout)
    if not isinstance(version_timeout, (int, float)) or version_timeout <= 0:
        version_timeout = timeout
    if not isinstance(quota_timeout, (int, float)) or quota_timeout <= 0:
        quota_timeout = timeout
    now = _utc_now(clock)
    agents: list[dict[str, Any]] = []
    for worker in workers:
        if not isinstance(worker, dict) or worker.get("class") != "external_agent_cli":
            continue
        worker_id = worker.get("id")
        provider_id = worker.get("provider_ref")
        if not isinstance(worker_id, str) or not isinstance(provider_id, str):
            continue
        provider = provider_by_id.get(provider_id)
        if not isinstance(provider, dict):
            agents.append(
                {
                    "worker_id": worker_id,
                    "provider_id": provider_id,
                    "enabled": bool(worker.get("enabled", False)),
                    "admission_state": str(worker.get("admission_state", "declared")),
                    "probe": {"state": "error", "reason": "provider_missing"},
                    "quota": {"state": "unknown", "reason": "provider_missing"},
                }
            )
            continue
        agents.append(
            {
                "worker_id": worker_id,
                "provider_id": provider_id,
                "enabled": bool(worker.get("enabled", False)),
                "admission_state": str(worker.get("admission_state", "declared")),
                "probe": _probe_version(provider, runner, float(version_timeout)),
                "quota": _observe_quota(provider, quota_observer, runner, now, float(quota_timeout)),
            }
        )
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": _iso(now),
        "mode": "observation_only",
        "dispatch": "forbidden",
        "agents": agents,
        "compute": _observe_compute(providers_document.get("compute_plane", {}), runner, float(version_timeout)),
    }
    manifest["manifest_digest"] = manifest_digest(manifest)
    return manifest


def verify_manifest(manifest: object, expected_digest: str | None = None) -> list[str]:
    """Verify the self-checksum and, if supplied, an independent fixed checksum."""
    if not isinstance(manifest, dict):
        return ["manifest_not_object"]
    errors: list[str] = []
    if manifest.get("schema") != SCHEMA:
        errors.append("schema_invalid")
    if manifest.get("mode") != "observation_only" or manifest.get("dispatch") != "forbidden":
        errors.append("execution_boundary_invalid")
    if not isinstance(manifest.get("agents"), list) or not isinstance(manifest.get("compute"), dict):
        errors.append("structure_invalid")
    recomputed_digest = manifest_digest(manifest)
    embedded_digest = manifest.get("manifest_digest")
    if embedded_digest != recomputed_digest:
        errors.append("manifest_digest_mismatch")
    if expected_digest is not None and (expected_digest != embedded_digest or expected_digest != recomputed_digest):
        errors.append("expected_digest_mismatch")
    return errors


def _parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    observe = subcommands.add_parser("observe", help="emit a read-only observation manifest")
    observe.add_argument("--providers", type=Path, default=root / ".omo/_truth/registry/capability-providers.yaml")
    observe.add_argument("--workers", type=Path, default=root / ".omo/_truth/registry/workers.yaml")
    observe.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    observe.add_argument("--json", action="store_true", help="required for machine output compatibility")
    verify = subcommands.add_parser("verify", help="verify a manifest's structure and checksum")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--expected-digest", help="independent fixed SHA-256 checksum expected for the manifest")
    verify.add_argument("--json", action="store_true", help="required for machine output compatibility")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command == "observe":
        try:
            payload = observe_pool(args.providers, args.workers, timeout=args.timeout)
        except (TypeError, ValueError) as exc:
            print(json.dumps({"reason": str(exc)}))
            return 2
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(json.dumps({"valid": False, "errors": ["manifest_unreadable"]}))
        return 2
    errors = verify_manifest(manifest, expected_digest=args.expected_digest)
    print(json.dumps({"valid": not errors, "checksum": manifest.get("manifest_digest"), "errors": errors}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
