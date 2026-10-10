"""Focused contract tests for the bounded compact observation collector."""

from __future__ import annotations

import fcntl
import importlib.util
import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/compact-observation.py"
SPEC = importlib.util.spec_from_file_location("compact_observation", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
compact = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compact)

NOW = datetime(2026, 10, 7, 1, 0, tzinfo=UTC)


def _values() -> dict[str, dict]:
    return {
        "knowledge_health": {
            "total": 12,
            "fresh": 10,
            "stale": 2,
            "orphaned": 0,
            "freshness_pct": 83.3,
            "coverage_pct": 100.0,
            "orphan_pct": 0.0,
        },
        "experience_graph": {
            "nodes_by_type": {"decision": 4},
            "internal_refs": 7,
            "hotspots": [{"type": "decision", "count": 4}],
            "connectivity_pct": 68,
        },
        "connectors": {
            "total": 1,
            "available": ["github"],
            "wired_to_scenes": ["github"],
            "unwired_available": [],
        },
        "bos_verifier": {"last_run_ok": 226, "last_run_errors": 0},
        "evolution": {
            "total": 1,
            "proposal_paths": [".omo/state/evolution-proposals/a.yaml"],
            "recent_proposals": ["a"],
        },
        "workspace": {
            "worktrees": [{"path": "/tmp/worktree", "branch": "main"}],
            "total_worktrees": 1,
            "lock_files": [".omo/_delivery/agent-workflows/locks/example.yaml"],
            "total_lock_files": 1,
        },
    }


def _clock(start: float = 0.0, step: float = 0.01):
    current = start - step

    def tick() -> float:
        nonlocal current
        current += step
        return current

    return tick


def test_launchd_observation_requires_registry_digest_and_keeps_it_in_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = {
        "schema": "launchd-health-observation/v1", "available": True,
        "facet_state": "LIVE", "verdict": "PASS", "loaded": 1, "failed": 0,
        "registry_sha256": "c" * 64,
        "jobs": [{
            "name": "demo", "label": "com.omostation.demo", "uid": 501,
            "schedule": "every-4m", "observed_at": "2026-10-07T01:00:00Z",
            "command_result_class": "loaded", "command_exit_code": 0,
            "stdout": "state = running", "stderr": "", "parsed": {"state": "running"},
            "semantic_verdict": "PASS",
        }],
    }
    monkeypatch.setattr(compact, "_collector_digest", lambda _root: "a" * 64)
    observed = compact.collect_observation(
        root=tmp_path, facets=("launchd_health",),
        runner=lambda _root, _name, _timeout: value,
        now_fn=lambda: NOW, monotonic=_clock(),
    )["facets"]["launchd_health"]

    assert observed["status"] == "OBSERVED"
    assert observed["provenance"]["registry_sha256"] == "c" * 64
    assert observed["source_digest"] == compact._source_digest(value)


def test_success_records_direct_per_facet_observation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(compact, "_collector_digest", lambda _root: "a" * 64)
    values = _values()

    result = compact.collect_observation(
        root=tmp_path,
        facets=tuple(values),
        runner=lambda _root, name, _timeout: values[name],
        now_fn=lambda: NOW,
        monotonic=_clock(),
    )

    assert result["schema"] == compact.SCHEMA
    assert result["overrun"] is False
    for name, facet in result["facets"].items():
        assert facet["status"] == "OBSERVED"
        assert facet["observation_status"] == "OBSERVED"
        assert facet["value"] == values[name]
        assert facet["observed_at"] == "2026-10-07T01:00:00Z"
        assert facet["last_success_at"] == facet["observed_at"]
        assert facet["last_attempt_at"] == facet["observed_at"]
        assert facet["error_class"] is None
        assert facet["provenance"]["source_ref"].endswith(compact.FACET_COLLECTORS[name])
        assert facet["provenance"]["source_digest"] == facet["source_digest"]
        assert facet["source_digest"] == compact._source_digest(facet["value"])


def test_evolution_and_workspace_collectors_are_plain_enumerations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    collector = compact._load_panorama_collector(ROOT)
    monkeypatch.setattr(collector, "ROOT", tmp_path)
    proposal_dir = tmp_path / ".omo/state/evolution-proposals"
    proposal_dir.mkdir(parents=True)
    (proposal_dir / "b.yaml").write_text("id: b\n", encoding="utf-8")
    (proposal_dir / "a.yaml").write_text("id: a\n", encoding="utf-8")
    lock_dir = tmp_path / ".omo/_delivery/agent-workflows/locks"
    lock_dir.mkdir(parents=True)
    (lock_dir / "held.yaml").write_text("state: active\n", encoding="utf-8")
    monkeypatch.setattr(
        collector,
        "run",
        lambda _command, **_kwargs: (0, "worktree /tmp/worktree\nbranch refs/heads/main\n\n"),
    )

    evolution = collector.collect_evolution()
    workspace = collector.collect_workspace_hygiene()

    assert evolution == {
        "total": 2,
        "proposal_paths": [
            ".omo/state/evolution-proposals/a.yaml",
            ".omo/state/evolution-proposals/b.yaml",
        ],
        "recent_proposals": ["a", "b"],
    }
    assert workspace == {
        "worktrees": [{"path": "/tmp/worktree", "branch": "refs/heads/main"}],
        "total_worktrees": 1,
        "lock_files": [".omo/_delivery/agent-workflows/locks/held.yaml"],
        "total_lock_files": 1,
    }
    assert "orphan_locks" not in workspace


def test_failure_preserves_last_good_without_advancing_success_time(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(compact, "_collector_digest", lambda _root: "b" * 64)
    value = _values()["knowledge_health"]
    previous = compact.collect_observation(
        root=tmp_path,
        facets=("knowledge_health",),
        runner=lambda *_args: value,
        now_fn=lambda: NOW,
        monotonic=_clock(),
    )
    previous["facets"]["knowledge_health"].pop("observation_status")

    def fail(*_args):
        raise compact.ObservationError("collector_error")

    later = NOW + timedelta(minutes=1)
    result = compact.collect_observation(
        root=tmp_path,
        previous=previous,
        facets=("knowledge_health",),
        runner=fail,
        now_fn=lambda: later,
        monotonic=_clock(),
    )
    facet = result["facets"]["knowledge_health"]
    assert facet["status"] == "STALE"
    assert facet["observation_status"] == "STALE"
    assert facet["value"] == value
    assert facet["observed_at"] == "2026-10-07T01:00:00Z"
    assert facet["last_success_at"] == "2026-10-07T01:00:00Z"
    assert facet["last_attempt_at"] == "2026-10-07T01:01:00Z"
    assert facet["error_class"] == "collector_error"
    assert facet["source_digest"] == compact._source_digest(value)


def test_failure_rejects_last_good_value_with_mismatched_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(compact, "_collector_digest", lambda _root: "b" * 64)
    previous = compact.collect_observation(
        root=tmp_path,
        facets=("knowledge_health",),
        runner=lambda *_args: _values()["knowledge_health"],
        now_fn=lambda: NOW,
        monotonic=_clock(),
    )
    previous["facets"]["knowledge_health"]["source_digest"] = "0" * 64

    result = compact.collect_observation(
        root=tmp_path,
        previous=previous,
        facets=("knowledge_health",),
        runner=lambda *_args: (_ for _ in ()).throw(compact.ObservationError("collector_error")),
        now_fn=lambda: NOW + timedelta(minutes=1),
        monotonic=_clock(),
    )

    facet = result["facets"]["knowledge_health"]
    assert facet["status"] == "UNKNOWN"
    assert facet["value"] is None
    assert facet["source_digest"] is None


def test_failure_does_not_promote_unknown_record_to_last_good(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(compact, "_collector_digest", lambda _root: "b" * 64)
    previous = compact.collect_observation(
        root=tmp_path,
        facets=("knowledge_health",),
        runner=lambda *_args: _values()["knowledge_health"],
        now_fn=lambda: NOW,
        monotonic=_clock(),
    )
    previous["facets"]["knowledge_health"]["status"] = "UNKNOWN"

    result = compact.collect_observation(
        root=tmp_path,
        previous=previous,
        facets=("knowledge_health",),
        runner=lambda *_args: (_ for _ in ()).throw(compact.ObservationError("collector_error")),
        now_fn=lambda: NOW + timedelta(minutes=1),
        monotonic=_clock(),
    )

    facet = result["facets"]["knowledge_health"]
    assert facet["status"] == "UNKNOWN"
    assert facet["value"] is None
    assert facet["source_digest"] is None


def test_failure_rejects_conflicting_status_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(compact, "_collector_digest", lambda _root: "b" * 64)
    previous = compact.collect_observation(
        root=tmp_path,
        facets=("knowledge_health",),
        runner=lambda *_args: _values()["knowledge_health"],
        now_fn=lambda: NOW,
        monotonic=_clock(),
    )
    previous["facets"]["knowledge_health"]["observation_status"] = "STALE"

    result = compact.collect_observation(
        root=tmp_path,
        previous=previous,
        facets=("knowledge_health",),
        runner=lambda *_args: (_ for _ in ()).throw(compact.ObservationError("collector_error")),
        now_fn=lambda: NOW + timedelta(minutes=1),
        monotonic=_clock(),
    )

    facet = result["facets"]["knowledge_health"]
    assert facet["status"] == "UNKNOWN"
    assert facet["observation_status"] == "UNKNOWN"
    assert facet["value"] is None


def test_timeout_without_last_good_is_unknown_and_overrun(tmp_path: Path) -> None:
    def timeout(*_args):
        raise subprocess.TimeoutExpired(["collector"], 1)

    result = compact.collect_observation(
        root=tmp_path,
        facets=("connectors",),
        runner=timeout,
        now_fn=lambda: NOW,
        monotonic=_clock(),
    )
    facet = result["facets"]["connectors"]
    assert facet["status"] == "UNKNOWN"
    assert facet["value"] is None
    assert facet["observed_at"] is None
    assert facet["last_success_at"] is None
    assert facet["error_class"] == "timeout"
    assert facet["overrun"] is True


def test_future_last_good_is_rejected_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(compact, "_collector_digest", lambda _root: "c" * 64)
    previous = compact.collect_observation(
        root=tmp_path,
        facets=("bos_verifier",),
        runner=lambda *_args: _values()["bos_verifier"],
        now_fn=lambda: NOW,
        monotonic=_clock(),
    )
    future = "2026-10-07T01:05:00Z"
    previous["facets"]["bos_verifier"]["observed_at"] = future
    previous["facets"]["bos_verifier"]["last_success_at"] = future

    result = compact.collect_observation(
        root=tmp_path,
        previous=previous,
        facets=("bos_verifier",),
        runner=lambda *_args: (_ for _ in ()).throw(compact.ObservationError("invalid_payload")),
        now_fn=lambda: NOW,
        monotonic=_clock(),
    )
    facet = result["facets"]["bos_verifier"]
    assert facet["status"] == "UNKNOWN"
    assert facet["value"] is None
    assert facet["observed_at"] is None


def test_single_flight_busy_does_not_replace_existing_state(tmp_path: Path) -> None:
    output = tmp_path / "compact-observation.json"
    output.write_text('{"sentinel":true}\n', encoding="utf-8")
    before = output.read_bytes()
    lock_path = tmp_path / "compact-observation.lock"
    with lock_path.open("a+b") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        code, summary = compact.run_once(
            root=tmp_path,
            output=output,
            lock_path=lock_path,
            facets=("knowledge_health",),
            facet_timeout_seconds=1,
            budget_seconds=2,
        )
    assert code == 2
    assert summary["status"] == "single_flight_busy"
    assert output.read_bytes() == before


def test_malformed_or_oversized_previous_state_is_not_trusted(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("not-json", encoding="utf-8")
    assert compact._read_json_object(path) is None
    path.write_bytes(b"x" * (compact.MAX_STATE_BYTES + 1))
    assert compact._read_json_object(path) is None


def _wait_for_process_exit(pid: int, *, timeout_seconds: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.02)
    return False


@pytest.mark.parametrize("ignore_sigterm", [False, True])
def test_timeout_reaps_facet_session_descendants_and_releases_single_flight_lock(
    ignore_sigterm: bool,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A timed-out collector cannot strand helpers or prevent the next run."""

    descendant_pid_path = tmp_path / "descendant.pid"
    real_popen = subprocess.Popen
    signal_setup = "signal.signal(signal.SIGTERM, signal.SIG_IGN)" if ignore_sigterm else ""
    descendant = "\n".join(
        (
            "import os",
            "import pathlib",
            "import signal",
            "import sys",
            "import time",
            signal_setup,
            "pathlib.Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')",
            "time.sleep(60)",
        )
    )
    helper = "\n".join(
        (
            "import subprocess",
            "import sys",
            "child = subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[1]])",
            "sys.exit(0)",
        )
    )

    def spawn_hanging_facet(*_args, **_kwargs):
        return real_popen(
            [sys.executable, "-c", helper, str(descendant_pid_path), descendant],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )

    monkeypatch.setattr(compact.subprocess, "Popen", spawn_hanging_facet)
    output = tmp_path / "compact-observation.json"
    lock_path = tmp_path / "compact-observation.lock"
    try:
        code, summary = compact.run_once(
            root=tmp_path,
            output=output,
            lock_path=lock_path,
            facets=("connectors",),
            facet_timeout_seconds=1.5,
            budget_seconds=2,
        )
        assert code == 1
        assert summary["status"] == "partial"
        descendant_pid = int(descendant_pid_path.read_text(encoding="utf-8"))
        assert _wait_for_process_exit(descendant_pid)
    finally:
        if descendant_pid_path.exists():
            pid = int(descendant_pid_path.read_text(encoding="utf-8"))
            if not _wait_for_process_exit(pid, timeout_seconds=0.1):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    values = _values()
    code, summary = compact.run_once(
        root=tmp_path,
        output=output,
        lock_path=lock_path,
        facets=("connectors",),
        facet_timeout_seconds=1,
        budget_seconds=2,
        runner=lambda _root, name, _timeout: values[name],
    )
    assert code == 0
    assert summary["status"] == "observed"
