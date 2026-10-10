#!/usr/bin/env python3
"""Collect a bounded, last-good-preserving observation of compact facets.

The collector reads the same authoritative sources as ``panorama-collect.py``
but runs each admitted facet in a disposable subprocess.  A timeout or failed
read never advances ``observed_at``/``last_success_at`` and never replaces the
last good value.  Projection publication and lease renewal are intentionally
outside this contract.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "panorama-compact-observation/v1"
DEFAULT_RELATIVE_OUTPUT = Path("runtime/dashboard/compact-observation.json")
MAX_STATE_BYTES = 4 * 1024 * 1024
DEFAULT_FACET_TIMEOUT_SECONDS = 45.0
DEFAULT_BUDGET_SECONDS = 240.0
PROCESS_GROUP_TERMINATION_GRACE_SECONDS = 1.0
FACET_COLLECTORS = {
    "knowledge_health": "collect_knowledge_health",
    "experience_graph": "collect_experience_graph",
    "connectors": "collect_connectors",
    "bos_verifier": "collect_bos_verifier",
    "evolution": "collect_evolution",
    "workspace": "collect_workspace_hygiene",
    "launchd_health": "collect_launchd_health_observation",
}


class ObservationError(RuntimeError):
    """A bounded observation could not produce admissible evidence."""


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_time(value: object, *, not_after: datetime) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (OverflowError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.astimezone(UTC) > not_after:
        return None
    return _iso(parsed)


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        if path.is_symlink():
            return None
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_STATE_BYTES:
                return None
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                body = stream.read(MAX_STATE_BYTES + 1)
        finally:
            os.close(descriptor)
        if len(body) > MAX_STATE_BYTES:
            return None
        value = json.loads(body)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _collector_digest(root: Path) -> str:
    path = root / "bin/panorama/panorama-collect.py"
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "unavailable"


def _source_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_result(name: str, value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("error"):
        raise ObservationError("collector_error")
    if name == "knowledge_health":
        required = {"total", "fresh", "stale", "orphaned", "freshness_pct", "coverage_pct", "orphan_pct"}
        if not required <= value.keys():
            raise ObservationError("invalid_payload")
    elif name == "experience_graph":
        if not {"nodes_by_type", "internal_refs", "hotspots", "connectivity_pct"} <= value.keys():
            raise ObservationError("invalid_payload")
    elif name == "connectors":
        if not {"total", "available", "wired_to_scenes", "unwired_available"} <= value.keys():
            raise ObservationError("invalid_payload")
    elif name == "bos_verifier":
        if not {"last_run_ok", "last_run_errors"} <= value.keys():
            raise ObservationError("invalid_payload")
    elif name == "evolution":
        paths = value.get("proposal_paths")
        if (
            not isinstance(value.get("total"), int)
            or isinstance(value.get("total"), bool)
            or value["total"] < 0
            or not isinstance(paths, list)
            or len(paths) != value["total"]
            or any(not isinstance(path, str) or not path for path in paths)
            or paths != sorted(set(paths))
            or not isinstance(value.get("recent_proposals"), list)
            or any(not isinstance(item, str) for item in value["recent_proposals"])
        ):
            raise ObservationError("invalid_payload")
    elif name == "workspace":
        worktrees = value.get("worktrees")
        lock_files = value.get("lock_files")
        if (
            not isinstance(worktrees, list)
            or not isinstance(value.get("total_worktrees"), int)
            or isinstance(value.get("total_worktrees"), bool)
            or value["total_worktrees"] != len(worktrees)
            or any(
                not isinstance(item, dict)
                or not isinstance(item.get("path"), str)
                or not item.get("path")
                or (item.get("branch") is not None and not isinstance(item.get("branch"), str))
                for item in worktrees
            )
            or not isinstance(lock_files, list)
            or not isinstance(value.get("total_lock_files"), int)
            or isinstance(value.get("total_lock_files"), bool)
            or value["total_lock_files"] != len(lock_files)
            or any(not isinstance(path, str) or not path for path in lock_files)
        ):
            raise ObservationError("invalid_payload")
    elif name == "launchd_health":
        jobs = value.get("jobs")
        registry_digest = value.get("registry_sha256")
        if (
            not isinstance(jobs, list)
            or not jobs
            or value.get("facet_state") not in {"LIVE", "PARTIAL"}
            or value.get("verdict") not in {"PASS", "DEGRADED", "FAILED"}
            or not isinstance(registry_digest, str)
            or len(registry_digest) != 64
            or any(not isinstance(job, dict) or not isinstance(job.get("label"), str) for job in jobs)
        ):
            raise ObservationError("invalid_payload")
        try:
            int(registry_digest, 16)
        except ValueError as exc:
            raise ObservationError("invalid_payload") from exc
    else:
        raise ObservationError("facet_not_admitted")
    return value


def _load_panorama_collector(root: Path) -> Any:
    path = root / "bin/panorama/panorama-collect.py"
    spec = importlib.util.spec_from_file_location("_panorama_compact_source", path)
    if spec is None or spec.loader is None:
        raise ObservationError("collector_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _collect_one(root: Path, name: str) -> dict[str, Any]:
    function_name = FACET_COLLECTORS.get(name)
    if function_name is None:
        raise ObservationError("facet_not_admitted")
    module = _load_panorama_collector(root)
    function = getattr(module, function_name, None)
    if not callable(function):
        raise ObservationError("collector_unavailable")
    return _valid_result(name, function())


def _terminate_facet_process_group(process: subprocess.Popen[str]) -> None:
    """Stop and reap a timed-out facet's isolated session.

    Each facet starts a new session, so its PID is also the process-group ID.
    Signalling that group prevents a collector that spawned helper processes
    from leaking descendants past the observation deadline.
    """

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.communicate(timeout=PROCESS_GROUP_TERMINATION_GRACE_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.communicate()


def _run_facet(root: Path, name: str, timeout_seconds: float) -> dict[str, Any]:
    command = [
        sys.executable,
        "-B",
        str(Path(__file__).resolve()),
        "--root",
        str(root),
        "--collect-one",
        name,
    ]
    process = subprocess.Popen(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, _stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate_facet_process_group(process)
        raise
    if process.returncode != 0:
        try:
            failure = json.loads(stdout)
        except json.JSONDecodeError:
            failure = None
        if (
            isinstance(failure, Mapping)
            and isinstance(failure.get("error"), str)
            and failure["error"].replace("_", "").isalnum()
        ):
            raise ObservationError(failure["error"])
        raise ObservationError("collector_error")
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ObservationError("invalid_payload") from exc
    return _valid_result(name, value)


def _previous_good(previous: object, name: str, *, now: datetime) -> dict[str, Any] | None:
    if not isinstance(previous, Mapping) or previous.get("schema") != SCHEMA:
        return None
    facets = previous.get("facets")
    prior = facets.get(name) if isinstance(facets, Mapping) else None
    if not isinstance(prior, Mapping) or not isinstance(prior.get("value"), dict):
        return None
    status = prior.get("observation_status", prior.get("status"))
    legacy_status = prior.get("status")
    if legacy_status is not None and legacy_status != status:
        return None
    if status not in {"OBSERVED", "STALE"}:
        return None
    try:
        value = _valid_result(name, prior["value"])
    except (ObservationError, TypeError, ValueError):
        return None
    observed_at = _parse_time(prior.get("observed_at"), not_after=now)
    last_success_at = _parse_time(prior.get("last_success_at"), not_after=now)
    provenance = prior.get("provenance")
    if observed_at is None or last_success_at is None or not isinstance(provenance, Mapping):
        return None
    if observed_at != last_success_at:
        return None
    source_ref = f"bin/panorama/panorama-collect.py::{FACET_COLLECTORS[name]}"
    if name == "launchd_health":
        source_ref = "bin/panorama/panorama-collect.py::collect_launchd_health"
    collector_digest = provenance.get("collector_sha256")
    if (
        provenance.get("kind") != "direct-read"
        or provenance.get("source_ref") != source_ref
        or not isinstance(collector_digest, str)
        or len(collector_digest) != 64
    ):
        return None
    try:
        int(collector_digest, 16)
    except ValueError:
        return None
    error_class = prior.get("error_class")
    if status == "OBSERVED" and error_class is not None:
        return None
    if status == "STALE" and (not isinstance(error_class, str) or not error_class):
        return None
    source_digest = prior.get("source_digest")
    provenance_source_digest = provenance.get("source_digest")
    if provenance_source_digest is not None and provenance_source_digest != source_digest:
        return None
    if name == "launchd_health" and provenance.get("registry_sha256") != value.get("registry_sha256"):
        return None
    try:
        if source_digest != _source_digest(value):
            return None
    except (TypeError, ValueError):
        return None
    return {
        "value": value,
        "source_digest": source_digest,
        "observed_at": observed_at,
        "last_success_at": last_success_at,
        "provenance": dict(provenance),
    }


def collect_observation(
    *,
    root: Path,
    previous: object = None,
    facets: Sequence[str] = tuple(FACET_COLLECTORS),
    facet_timeout_seconds: float = DEFAULT_FACET_TIMEOUT_SECONDS,
    budget_seconds: float = DEFAULT_BUDGET_SECONDS,
    runner: Callable[[Path, str, float], dict[str, Any]] | None = None,
    now_fn: Callable[[], datetime] = _utc_now,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    if runner is None:
        runner = _run_facet
    started_at = now_fn().astimezone(UTC)
    started_clock = monotonic()
    digest = _collector_digest(root)
    results: dict[str, Any] = {}
    for name in facets:
        if name not in FACET_COLLECTORS:
            raise ObservationError(f"facet_not_admitted:{name}")
        attempt_at = now_fn().astimezone(UTC)
        facet_started = monotonic()
        elapsed = max(0.0, facet_started - started_clock)
        remaining = budget_seconds - elapsed
        error_class: str | None = None
        value: dict[str, Any] | None = None
        if remaining <= 0:
            error_class = "overall_timeout"
        else:
            try:
                value = runner(root, name, min(facet_timeout_seconds, remaining))
                value = _valid_result(name, value)
            except subprocess.TimeoutExpired:
                error_class = "timeout"
            except ObservationError as exc:
                error_class = str(exc).split(":", 1)[0]
            except (OSError, ValueError):
                error_class = "collector_error"
        finished_at = now_fn().astimezone(UTC)
        duration_ms = max(0, round((monotonic() - facet_started) * 1000))
        source_ref = f"bin/panorama/panorama-collect.py::{FACET_COLLECTORS[name]}"
        if name == "launchd_health":
            source_ref = "bin/panorama/panorama-collect.py::collect_launchd_health"
        attempt_provenance = {
            "kind": "direct-read",
            "source_ref": source_ref,
            "collector_sha256": digest,
            "source_digest": _source_digest(value) if error_class is None and value is not None else None,
        }
        if name == "launchd_health" and error_class is None and value is not None:
            attempt_provenance["registry_sha256"] = value["registry_sha256"]
        if error_class is None and value is not None:
            source_digest = _source_digest(value)
            observed_at = _iso(finished_at)
            results[name] = {
                "status": "OBSERVED",
                "observation_status": "OBSERVED",
                "value": value,
                "source_digest": source_digest,
                "observed_at": observed_at,
                "last_attempt_at": _iso(attempt_at),
                "last_success_at": observed_at,
                "error_class": None,
                "duration_ms": duration_ms,
                "overrun": duration_ms > round(facet_timeout_seconds * 1000),
                "provenance": attempt_provenance,
            }
            continue
        prior = _previous_good(previous, name, now=attempt_at)
        results[name] = {
            "status": "STALE" if prior else "UNKNOWN",
            "observation_status": "STALE" if prior else "UNKNOWN",
            "value": prior["value"] if prior else None,
            "source_digest": prior.get("source_digest") if prior else None,
            "observed_at": prior["observed_at"] if prior else None,
            "last_attempt_at": _iso(attempt_at),
            "last_success_at": prior["last_success_at"] if prior else None,
            "error_class": error_class or "collector_error",
            "duration_ms": duration_ms,
            "overrun": error_class in {"timeout", "overall_timeout"},
            "provenance": prior["provenance"] if prior else attempt_provenance,
            "attempt_provenance": attempt_provenance,
        }
    completed_at = now_fn().astimezone(UTC)
    duration_ms = max(0, round((monotonic() - started_clock) * 1000))
    return {
        "schema": SCHEMA,
        "started_at": _iso(started_at),
        "completed_at": _iso(completed_at),
        "duration_ms": duration_ms,
        "budget_seconds": budget_seconds,
        "overrun": duration_ms > round(budget_seconds * 1000),
        "facets": results,
    }


def run_once(
    *,
    root: Path,
    output: Path,
    lock_path: Path,
    facets: Sequence[str],
    facet_timeout_seconds: float,
    budget_seconds: float,
    runner: Callable[[Path, str, float], dict[str, Any]] | None = None,
) -> tuple[int, dict[str, Any]]:
    output.parent.mkdir(parents=True, exist_ok=True)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 2, {"schema": SCHEMA, "status": "single_flight_busy"}
        previous = _read_json_object(output)
        observation = collect_observation(
            root=root,
            previous=previous,
            facets=facets,
            facet_timeout_seconds=facet_timeout_seconds,
            budget_seconds=budget_seconds,
            runner=runner,
        )
        _atomic_write_json(output, observation)
    failed = [name for name, value in observation["facets"].items() if value["status"] != "OBSERVED"]
    return (1 if failed else 0), {
        "schema": SCHEMA,
        "status": "partial" if failed else "observed",
        "output": str(output),
        "failed_facets": failed,
        "duration_ms": observation["duration_ms"],
        "overrun": observation["overrun"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--facet", action="append", choices=sorted(FACET_COLLECTORS))
    parser.add_argument("--facet-timeout", type=float, default=DEFAULT_FACET_TIMEOUT_SECONDS)
    parser.add_argument("--budget", type=float, default=DEFAULT_BUDGET_SECONDS)
    parser.add_argument("--collect-one", choices=sorted(FACET_COLLECTORS), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    if args.collect_one:
        try:
            print(json.dumps(_collect_one(root, args.collect_one), ensure_ascii=False, sort_keys=True))
            return 0
        except ObservationError as exc:
            print(json.dumps({"error": str(exc)}, sort_keys=True))
            return 1
    output = (args.output or (root / DEFAULT_RELATIVE_OUTPUT)).expanduser().resolve()
    lock_path = (args.lock or output.with_suffix(output.suffix + ".lock")).expanduser().resolve()
    if args.facet_timeout <= 0 or args.budget <= 0:
        parser.error("--facet-timeout and --budget must be positive")
    code, summary = run_once(
        root=root,
        output=output,
        lock_path=lock_path,
        facets=args.facet or tuple(FACET_COLLECTORS),
        facet_timeout_seconds=args.facet_timeout,
        budget_seconds=args.budget,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
