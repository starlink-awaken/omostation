"""Public contract tests for the workflow compatibility projection."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "agent-workflow.py"


def _canonical_registry(tmp_path: Path) -> Path:
    registry = tmp_path / "agent-workflows"
    workflows = registry / "workflows"
    workflows.mkdir(parents=True)
    (registry / "_root.yaml").write_text(
        "version: 1\n"
        "description: Canonical workflow registry\n"
        "runner:\n"
        "  entrypoint: bin/agent-workflow.py\n",
        encoding="utf-8",
    )
    (workflows / "beta.yaml").write_text(
        "id: beta\nrun_frequency: periodic\ntitle: Beta\n",
        encoding="utf-8",
    )
    (workflows / "alpha.yaml").write_text(
        "id: alpha\nrun_frequency: on_demand\ntitle: Alpha\n",
        encoding="utf-8",
    )
    return registry


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _load_script(name: str, relative: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_projection_sync_is_deterministic_and_carries_read_only_provenance(tmp_path: Path) -> None:
    registry = _canonical_registry(tmp_path)
    projection = tmp_path / "agent-workflows.yaml"

    first = _run(
        "projection-sync",
        "--registry",
        str(registry),
        "--projection",
        str(projection),
        "--json",
    )
    first_bytes = projection.read_bytes()
    second = _run(
        "projection-sync",
        "--registry",
        str(registry),
        "--projection",
        str(projection),
        "--json",
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert projection.read_bytes() == first_bytes
    assert json.loads(first.stdout)["changed"] is True
    assert json.loads(second.stdout)["changed"] is False
    payload = yaml.safe_load(first_bytes)
    assert payload["projection"] == {
        "schema": "agent-workflow-compat-projection/v1",
        "authority": "projection",
        "lifecycle": "read_only_generated_compatibility",
        "source": ".omo/_truth/registry/agent-workflows",
        "source_digest": payload["projection"]["source_digest"],
        "writer": "bin/agent-workflow.py projection-sync",
    }
    assert payload["projection"]["source_digest"].startswith("sha256:")
    assert [workflow["id"] for workflow in payload["workflows"]] == ["alpha", "beta"]


def test_projection_check_fails_closed_on_content_or_provenance_drift(tmp_path: Path) -> None:
    registry = _canonical_registry(tmp_path)
    projection = tmp_path / "agent-workflows.yaml"
    synced = _run(
        "projection-sync",
        "--registry",
        str(registry),
        "--projection",
        str(projection),
        "--json",
    )
    assert synced.returncode == 0, synced.stderr

    current = _run(
        "projection-check",
        "--registry",
        str(registry),
        "--projection",
        str(projection),
        "--json",
    )
    assert current.returncode == 0, current.stderr
    before = projection.read_bytes()

    projection.write_text(
        projection.read_text(encoding="utf-8").replace("authority: projection", "authority: ssot"),
        encoding="utf-8",
    )
    drifted = _run(
        "projection-check",
        "--registry",
        str(registry),
        "--projection",
        str(projection),
        "--json",
    )

    assert drifted.returncode == 1
    assert "WORKFLOW_PROJECTION_DRIFT" in drifted.stderr
    assert projection.read_bytes() != before


def test_projection_check_detects_canonical_change_without_writing(tmp_path: Path) -> None:
    registry = _canonical_registry(tmp_path)
    projection = tmp_path / "agent-workflows.yaml"
    synced = _run(
        "projection-sync",
        "--registry",
        str(registry),
        "--projection",
        str(projection),
    )
    assert synced.returncode == 0, synced.stderr
    before = projection.read_bytes()
    (registry / "workflows" / "gamma.yaml").write_text(
        "id: gamma\nrun_frequency: on_demand\ntitle: Gamma\n",
        encoding="utf-8",
    )

    result = _run(
        "projection-check",
        "--registry",
        str(registry),
        "--projection",
        str(projection),
    )

    assert result.returncode == 1
    assert "WORKFLOW_PROJECTION_DRIFT" in result.stderr
    assert projection.read_bytes() == before


def test_projection_sync_refuses_to_overwrite_canonical_sources(tmp_path: Path) -> None:
    registry = _canonical_registry(tmp_path)
    canonical_root = registry / "_root.yaml"
    before = canonical_root.read_bytes()

    result = _run(
        "projection-sync",
        "--registry",
        str(registry),
        "--projection",
        str(canonical_root),
    )

    assert result.returncode == 1
    assert "WORKFLOW_PROJECTION_TARGET_INVALID" in result.stderr
    assert canonical_root.read_bytes() == before


def test_active_consumers_watch_and_classify_canonical_authority() -> None:
    watcher = _load_script("workflow_projection_ssot_watcher", "bin/ssot-watcher.py")
    lane_check = _load_script("workflow_projection_lane_check", "bin/change-lane-check.py")
    local_gate = _load_script("workflow_projection_local_gate", "bin/gac/gac-local-gate.py")

    watched = dict(watcher.SSOT_FILES)
    assert watched["agent_workflows"] == ".omo/_truth/registry/agent-workflows/"
    assert watched["agent_workflow_projection"] == ".omo/_truth/registry/agent-workflows.yaml"
    canonical_file = ".omo/_truth/registry/agent-workflows/workflows/project-code-change.yaml"
    assert lane_check.classify(canonical_file, set()) == "governance_code"
    local_gate.staged_files_git = lambda: [canonical_file]
    assert local_gate.staged_touches_agent_workflow() is True


def test_canonical_workflows_only_write_split_registry_surfaces() -> None:
    registry_root = ROOT / ".omo/_truth/registry/agent-workflows"
    onboarding = yaml.safe_load((registry_root / "workflows/agent-onboarding.yaml").read_text(encoding="utf-8"))
    adapter_sync = yaml.safe_load(
        (registry_root / "workflows/external-adapter-sync.yaml").read_text(encoding="utf-8")
    )
    root = yaml.safe_load((registry_root / "_root.yaml").read_text(encoding="utf-8"))

    assert onboarding["surfaces"]["write"] == [
        ".omo/_truth/registry/agent-workflows/profiles/**",
        ".agents/skills/**",
    ]
    assert adapter_sync["surfaces"]["write"][0] == ".omo/_truth/registry/agent-workflows/adapters/**"
    projection_check = next(
        check for check in root["diff_checks"] if check["id"] == "agent-workflow-projection-check"
    )
    assert projection_check["command"][-1] == "projection-check"
    assert projection_check["required"] is True


def test_snapshot_loader_rejects_a_canonical_change_during_registry_load(tmp_path: Path) -> None:
    projection_module = _load_script(
        "workflow_projection_snapshot_loader", "lib/agent_workflow_projection.py"
    )
    registry = _canonical_registry(tmp_path)

    def racing_loader(_source: Path) -> dict[str, object]:
        (registry / "workflows/gamma.yaml").write_text(
            "id: gamma\nrun_frequency: on_demand\ntitle: Gamma\n",
            encoding="utf-8",
        )
        return {"version": 1, "workflows": [{"id": "alpha"}]}

    with pytest.raises(projection_module.ProjectionError, match="WORKFLOW_PROJECTION_SOURCE_RACED"):
        projection_module.load_registry_snapshot(racing_loader, registry)


def test_projection_refuses_to_bind_an_old_registry_to_new_source_bytes(tmp_path: Path) -> None:
    projection_module = _load_script(
        "workflow_projection_stale_registry", "lib/agent_workflow_projection.py"
    )
    registry = _canonical_registry(tmp_path)
    projection = tmp_path / "agent-workflows.yaml"
    old_digest = projection_module.source_digest(registry)
    old_registry = {
        "version": 1,
        "workflows": [
            {"id": "alpha", "run_frequency": "on_demand", "title": "Alpha"},
            {"id": "beta", "run_frequency": "periodic", "title": "Beta"},
        ],
    }
    (registry / "workflows/gamma.yaml").write_text(
        "id: gamma\nrun_frequency: on_demand\ntitle: Gamma\n",
        encoding="utf-8",
    )

    with pytest.raises(projection_module.ProjectionError, match="WORKFLOW_PROJECTION_SOURCE_RACED"):
        projection_module.sync_projection(
            old_registry,
            registry,
            projection,
            source_digest_bound=old_digest,
        )
    assert not projection.exists()
