from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "affected-graph.py"
CASCADE_WORKFLOW = ROOT / ".github" / "workflows" / "cascading-test.yml"


def _load_module():
    spec = importlib.util.spec_from_file_location("affected_graph", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cascading_workflow_preserves_project_argument_boundaries():
    workflow = CASCADE_WORKFLOW.read_text(encoding="utf-8")

    assert "tr -d '[:space:]'" not in workflow
    # The workflow must invoke affected-graph.py with --changed-projects
    # and --json. Allow either the legacy single-string form or the modern
    # bash-array form (the array form is preferred to handle project names
    # with whitespace safely).
    assert (
        "affected-graph.py --changed-projects" in workflow
        and "--json" in workflow
    ), "cascading-test.yml must invoke affected-graph.py with --changed-projects and --json"


def _workspace(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir(parents=True)
    (docs / "layer-contract.yaml").write_text(
        "layers:\n"
        "  L2:\n"
        "    projects: [gbrain, omo]\n"
        "  L3:\n"
        "    projects: [cockpit]\n"
        "dependency_rules:\n"
        "  allowed_directions:\n"
        "    - from: [L3]\n"
        "      to: [L2]\n",
        encoding="utf-8",
    )
    return tmp_path


def test_root_only_receipt_uses_explicit_workspace_root_project(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)

    receipt = module.create_receipt(["workspace-root"], workspace)

    assert receipt["schema"] == "affected-graph-receipt/v1"
    assert receipt["changed_projects"] == ["workspace-root"]
    assert receipt["affected_projects"] == ["workspace-root"]


def test_projects_omo_receipt_is_stable_and_recomputable(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)

    first = module.create_receipt(["omo"], workspace)
    second = module.create_receipt(["omo"], workspace)
    unsigned = {key: value for key, value in first.items() if key != "receipt_hash"}
    canonical = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    assert first == second
    assert first["affected_projects"] == ["cockpit", "omo"]
    assert first["receipt_hash"] == hashlib.sha256(canonical.encode()).hexdigest()


def test_cross_project_receipt_is_sorted_and_complete(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)

    receipt = module.create_receipt(["omo", "gbrain"], workspace)

    assert receipt["changed_projects"] == ["gbrain", "omo"]
    assert receipt["affected_projects"] == ["cockpit", "gbrain", "omo"]


def test_unknown_project_fails_closed(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)

    with pytest.raises(module.AffectedGraphError, match="unknown project"):
        module.create_receipt(["not-real"], workspace)


def test_cli_writes_canonical_receipt_file(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    output_ref = Path("evidence/receipt.json")
    output = workspace / output_ref

    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--workspace-root",
            str(workspace),
            "--changed-projects",
            "omo",
            "--output",
            str(output_ref),
            "--json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == json.loads(output.read_text())


def test_cli_rejects_unknown_project(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--workspace-root",
            str(workspace),
            "--changed-projects",
            "unknown",
            "--json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "unknown project" in result.stderr


def test_cli_refuses_to_overwrite_existing_receipt(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    output_ref = Path("evidence/receipt.json")
    output = workspace / output_ref
    output.parent.mkdir()
    output.write_text("preserve-me\n", encoding="utf-8")

    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--workspace-root",
            str(workspace),
            "--changed-projects",
            "omo",
            "--output",
            str(output_ref),
            "--json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "already exists" in result.stderr
    assert output.read_text() == "preserve-me\n"


def test_cli_rejects_output_outside_workspace(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    output = tmp_path / "outside-receipt.json"
    output_ref = Path("../outside-receipt.json")

    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--workspace-root",
            str(workspace),
            "--changed-projects",
            "omo",
            "--output",
            str(output_ref),
            "--json",
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "canonical workspace-relative" in result.stderr
    assert not output.exists()


def test_cli_rejects_symlinked_output_parent(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "linked-evidence").symlink_to(outside, target_is_directory=True)
    output_ref = Path("linked-evidence/receipt.json")

    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--workspace-root",
            str(workspace),
            "--changed-projects",
            "omo",
            "--output",
            str(output_ref),
            "--json",
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "symlink" in result.stderr
    assert not (outside / "receipt.json").exists()
