from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from omo.omo_worker_core import (
    _build_launch_argv,
    _default_enabled_worker_id,
    _require_admitted_worker,
)
from omo.omo_worker_dispatch import dispatch_task


def _task_fixture(root: Path, *, worker: dict) -> Path:
    active_dir = root / ".omo" / "tasks" / "active"
    registry_dir = root / ".omo" / "_truth" / "registry"
    active_dir.mkdir(parents=True)
    registry_dir.mkdir(parents=True)
    (registry_dir / "workers.yaml").write_text(
        yaml.safe_dump({"workers": [worker]}, sort_keys=False), encoding="utf-8"
    )
    task_path = active_dir / "TASK-ADMISSION-GATE.yaml"
    task_path.write_text(
        yaml.safe_dump(
            {
                "id": "TASK-ADMISSION-GATE",
                "title": "Admission gate fixture",
                "status": "pending",
                "assigned_to": None,
                "dispatch_id": None,
                "run_ref": None,
                "approval_ref": None,
                "review_ref": None,
                "knowledge_refs": [],
                "handoff_refs": [],
                "risk_level": "L1",
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "source_docs": ["docs/source.md"],
                "entry_gate": [],
                "evidence_required": ["worker review"],
                "deliverables": ["docs/result.md"],
                "test_plan": ["pytest"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return task_path


def _worker(
    *,
    enabled: bool = True,
    admission_state: str = "admitted",
    transports: dict | None = None,
) -> dict:
    return {
        "id": "pi",
        "enabled": enabled,
        "admission_state": admission_state,
        "transports": transports
        if transports is not None
        else {"cli_prompt": {"command": "pi --prompt {prompt}"}},
    }


def _admitted_pi_worker() -> dict:
    return {
        "id": "pi",
        "enabled": True,
        "admission_state": "admitted",
        "provider_ref": "pi",
        "role": "worker",
        "class": "external_agent_cli",
        "transports": {
            "cli_prompt": {
                "command": (
                    "/usr/bin/python3 bin/gac/pi-worker-adapter.py run --execute "
                    '--timeout-seconds 120 --prompt "{prompt}"'
                )
            }
        },
        "capabilities": ["reasoning", "verification"],
        "allowed_operation_level": "L0",
        "forbidden_domains": ["apple", "wechat", "smb", "family", "media"],
        "write_scope": {"mode": "none"},
        "lease_policy": {
            "heartbeat_interval_seconds": 300,
            "warning_after_seconds": 900,
            "lease_expired_after_seconds": 1200,
            "reclaim_after_seconds": 1800,
        },
    }


def _file_snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (root / ".omo").rglob("*")
        if path.is_file()
    }


def test_dispatch_rejects_declared_worker_before_any_runtime_write(
    tmp_path: Path,
) -> None:
    task_path = _task_fixture(
        tmp_path, worker=_worker(enabled=False, admission_state="declared")
    )
    before = _file_snapshot(tmp_path)
    runs_dir = tmp_path / ".omo" / "workers" / "runs"
    mesh_log = tmp_path / ".omo" / "_knowledge" / "workflow-mesh" / "events.jsonl"

    with pytest.raises(
        ValueError,
        match=r"worker admission denied: worker_id=pi reason=disabled",
    ):
        dispatch_task(
            tmp_path,
            task_id="TASK-ADMISSION-GATE",
            worker_id="pi",
            allowed_write_paths=["docs/"],
            launch=False,
            now="2026-08-13T01:02:03+00:00",
        )

    assert _file_snapshot(tmp_path) == before
    assert yaml.safe_load(task_path.read_text(encoding="utf-8"))["status"] == "pending"
    assert not runs_dir.exists()
    assert not mesh_log.exists()


@pytest.mark.parametrize(
    ("worker_id", "registry", "reason"),
    [
        ("missing", {"workers": []}, "not_registered"),
        (
            "pi",
            {"workers": [_worker(enabled=False, admission_state="admitted")]},
            "disabled",
        ),
        (
            "pi",
            {"workers": [_worker(enabled=True, admission_state="declared")]},
            "not_admitted",
        ),
        (
            "pi",
            {
                "workers": [
                    _worker(enabled=True, admission_state="admitted", transports={})
                ]
            },
            "transport_missing",
        ),
    ],
)
def test_worker_admission_reasons_are_stable(
    worker_id: str, registry: dict, reason: str
) -> None:
    with pytest.raises(
        ValueError,
        match=rf"worker admission denied: worker_id={worker_id} reason={reason}",
    ):
        _require_admitted_worker(registry, worker_id, "cli_prompt")


def test_worker_admission_returns_admitted_worker() -> None:
    worker = _worker()
    assert _require_admitted_worker({"workers": [worker]}, "pi", "cli_prompt") == worker


def test_default_worker_skips_declared_enabled_worker() -> None:
    declared = _worker(enabled=True, admission_state="declared")
    admitted = _worker(enabled=True, admission_state="admitted")
    admitted["id"] = "admitted-pi"
    assert (
        _default_enabled_worker_id({"workers": [declared, admitted]}) == "admitted-pi"
    )


def test_default_worker_requires_an_admitted_worker() -> None:
    with pytest.raises(ValueError, match="no admitted worker is registered"):
        _default_enabled_worker_id(
            {"workers": [_worker(enabled=True, admission_state="declared")]}
        )


def test_admitted_pi_worker_uses_one_shell_free_omo_transport() -> None:
    pi = _admitted_pi_worker()

    assert pi["enabled"] is True
    assert pi["admission_state"] == "admitted"
    assert pi["provider_ref"] == "pi"
    assert pi["role"] == "worker"
    assert pi["class"] == "external_agent_cli"
    assert pi["capabilities"] == ["reasoning", "verification"]
    assert pi["allowed_operation_level"] == "L0"
    assert pi["write_scope"] == {"mode": "none"}
    assert pi["transports"] == {
        "cli_prompt": {
            "command": (
                "/usr/bin/python3 bin/gac/pi-worker-adapter.py run --execute "
                '--timeout-seconds 120 --prompt "{prompt}"'
            )
        }
    }
    assert "receipt" not in pi["transports"]["cli_prompt"]["command"]

    prompt = "quoted prompt; $(must remain one argv)"
    argv = _build_launch_argv({"workers": [pi]}, "pi", "cli_prompt", prompt)

    assert argv == [
        "/usr/bin/python3",
        "bin/gac/pi-worker-adapter.py",
        "run",
        "--execute",
        "--timeout-seconds",
        "120",
        "--prompt",
        prompt,
    ]
    assert argv.count(prompt) == 1
    assert "-c" not in argv
    assert not any(
        fragment in argument for argument in argv for fragment in ("&&", "||", "|")
    )


def test_admitted_pi_worker_dispatch_without_launch_creates_only_governed_artifacts(
    tmp_path: Path,
) -> None:
    pi = _admitted_pi_worker()
    task_path = _task_fixture(tmp_path, worker=pi)
    task = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    task["risk_level"] = "L0"
    task["allowed_operation_level"] = "L0"
    task_path.write_text(yaml.safe_dump(task, sort_keys=False), encoding="utf-8")
    before = _file_snapshot(tmp_path)

    result = dispatch_task(
        tmp_path,
        task_id="TASK-ADMISSION-GATE",
        worker_id="pi",
        allowed_write_paths=[],
        launch=False,
        now="2026-08-13T01:02:03+00:00",
    )

    after = _file_snapshot(tmp_path)
    changed_paths = {
        path for path, digest in after.items() if before.get(path) != digest
    }
    expected_run_paths = {
        Path(path).as_posix() for name, path in result.items() if name.endswith("_path")
    }
    assert expected_run_paths <= changed_paths
    assert changed_paths <= {
        str(task_path.relative_to(tmp_path)),
        *expected_run_paths,
        ".omo/_knowledge/workflow-mesh/events.jsonl",
        ".omo/_knowledge/workflow-mesh/events.jsonl.lock",
    }
    assert not (
        tmp_path / ".omo" / "workers" / "runs" / f"{result['dispatch_id']}-stdout.log"
    ).exists()
