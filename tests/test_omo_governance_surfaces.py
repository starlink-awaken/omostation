from __future__ import annotations

import json
from pathlib import Path

import yaml

from omo.omo_governance import main as omo_governance_main
from omo.omo_governance_surfaces import build_governance_surfaces_report


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    _write(path, yaml.dump(payload, allow_unicode=True, sort_keys=False))


def _seed_workspace(root: Path) -> None:
    omo = root / ".omo"
    for rel in [
        "_truth/registry",
        "standards",
        "_control",
        "_knowledge",
        "_delivery",
        "_delivery/evidence-legacy",
        "_archive",
        "tasks/planned",
        "state",
        "debt",
        "workers",
    ]:
        (omo / rel).mkdir(parents=True, exist_ok=True)
    (omo / "evidence").symlink_to("_delivery/evidence-legacy")

    _write(
        omo / "standards" / "omo-governance-surfaces.md",
        "# OMO Governance Surfaces Standard\n",
    )
    _write_yaml(
        omo / "_truth" / "registry" / "omo-governance-surfaces.yaml",
        {
            "assets": [
                {"ref": ".omo/_truth/", "status": "active"},
                {"ref": ".omo/_control/", "status": "active"},
                {"ref": ".omo/_knowledge/", "status": "active"},
                {"ref": ".omo/_delivery/", "status": "active"},
                {"ref": ".omo/_archive/", "status": "active"},
                {"ref": ".omo/tasks/", "status": "active"},
                {"ref": ".omo/state/", "status": "active"},
                {"ref": ".omo/debt/", "status": "active"},
                {"ref": ".omo/workers/", "status": "active"},
                {"ref": ".omo/standards/", "status": "active"},
                {"ref": ".omo/evidence/", "status": "active", "asset_type": "compatibility_alias"},
            ]
        },
    )

    c2g_builder = root / "projects" / "c2g" / "src" / "c2g" / "task_builder.py"
    _write(
        c2g_builder,
        """
def build_ecos_task(*args, **kwargs):
    return {
        "governance_refs": [
            ".omo/standards/omo-governance-surfaces.md",
            ".omo/_truth/registry/omo-governance-surfaces.yaml",
        ],
        "metadata": {"ingress_plane": "projects/c2g"},
    }
""".strip()
        + "\n",
    )
    _write(
        root / ".pre-commit-config.yaml",
        """
- repo: local
  hooks:
    - id: omo-direct-io-gate
      entry: uv run --directory projects/omo python -m omo.cli lint direct-omo-io
""".strip()
        + "\n",
    )


def test_build_governance_surfaces_report_ok(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "ok"
    assert report["unregistered_top_levels"] == []
    assert report["missing_registered_roots"] == []
    assert report["c2g_missing_governance_refs"] == []
    assert report["direct_io_gate_present"] is True
    assert report["ingress_registry"]["exists"] is False
    assert report["ingress_registry"]["debt_ids"] == []


def test_build_governance_surfaces_report_flags_unregistered_top_level(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)
    (tmp_path / ".omo" / "mystery").mkdir()

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert "mystery" in report["unregistered_top_levels"]


def test_omo_governance_surfaces_cli_json(tmp_path: Path, capsys, monkeypatch: object) -> None:
    _seed_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc = omo_governance_main(["surfaces", "--workspace-root", ".", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert ".omo/standards/omo-governance-surfaces.md" in payload["c2g_governance_refs"]


def test_omo_governance_surfaces_cli_auto_detects_workspace_root_from_subrepo(
    tmp_path: Path, capsys, monkeypatch: object
) -> None:
    _seed_workspace(tmp_path)
    subrepo = tmp_path / "projects" / "omo"
    subrepo.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(subrepo)

    rc = omo_governance_main(["surfaces", "--workspace-root", ".", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["workspace_root"] == str(tmp_path)


def test_build_governance_surfaces_report_accepts_evidence_alias(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "ok"
    assert report["warnings"] == []


def test_build_governance_surfaces_report_requires_direct_io_gate(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)
    (tmp_path / ".pre-commit-config.yaml").unlink()

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert any("pre-commit direct io gate missing" in issue for issue in report["issues"])


def test_build_governance_surfaces_report_flags_ingress_registry_reverse_mapping_mismatch(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    ingress_dir = tmp_path / ".omo" / "_delivery" / "ingress"
    ingress_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "IMPORTED-1.yaml",
        {
            "id": "IMPORTED-1",
            "title": "task",
            "status": "candidate",
            "task_type": "feature",
            "risk_level": "L0",
            "depends_on": [],
            "source_docs": ["spec.md"],
            "deliverables": ["代码"],
            "imported_via": "projects/c2g",
            "context_uri": "bos://memory/spec#1",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "governance_refs": [".omo/standards/omo-governance-surfaces.md"],
            "entry_gate": [],
            "evidence_required": ["pytest"],
            "test_plan": ["uv run pytest"],
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "metadata": {},
        },
    )
    _write_yaml(
        ingress_dir / "registry.yaml",
        {
            "goals": {"by_id": {}, "by_source_ref": {}},
            "tasks": {
                "by_id": {
                    "IMPORTED-1": {
                        "source_ref": "c2g:bridge-import:IMPORTED-1",
                        "artifact_ref": ".omo/_delivery/ingress/tasks/IMPORTED-1.yaml",
                        "fingerprint": {"id": "IMPORTED-1"},
                        "created_at": "2026-06-18T00:00:00Z",
                    }
                },
                "by_source_ref": {"c2g:bridge-import:IMPORTED-1": "IMPORTED-OTHER"},
            },
            "debts": {"by_id": {}, "by_source_ref": {}},
        },
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert any("reverse mapping mismatch" in issue for issue in report["issues"])


def test_build_governance_surfaces_report_tracks_debt_ingress(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)
    ingress_dir = tmp_path / ".omo" / "_delivery" / "ingress"
    ingress_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(
        tmp_path / ".omo" / "debt" / "items" / "DEBT-1.yaml",
        {
            "id": "DEBT-1",
            "title": "debt",
            "lifecycle_state": "identified",
        },
    )
    _write_yaml(
        ingress_dir / "registry.yaml",
        {
            "goals": {"by_id": {}, "by_source_ref": {}},
            "tasks": {"by_id": {}, "by_source_ref": {}},
            "debts": {
                "by_id": {
                    "DEBT-1": {
                        "source_ref": "aetherforge:budget:DEBT-1",
                        "artifact_ref": ".omo/_delivery/ingress/debts/DEBT-1.yaml",
                        "fingerprint": {"id": "DEBT-1"},
                        "created_at": "2026-06-18T00:00:00Z",
                    }
                },
                "by_source_ref": {"aetherforge:budget:DEBT-1": "DEBT-1"},
            },
        },
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "ok"
    assert report["ingress_registry"]["debt_ids"] == ["DEBT-1"]
    assert report["ingress_registry"]["debt_source_refs"] == ["aetherforge:budget:DEBT-1"]


def test_build_governance_surfaces_report_accepts_archived_ingress_task_carrier(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    ingress_dir = tmp_path / ".omo" / "_delivery" / "ingress"
    ingress_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "archive" / "IMPORTED-1.yaml",
        {
            "id": "IMPORTED-1",
            "status": "archived",
        },
    )
    _write_yaml(
        ingress_dir / "registry.yaml",
        {
            "goals": {"by_id": {}, "by_source_ref": {}},
            "tasks": {
                "by_id": {
                    "IMPORTED-1": {
                        "source_ref": "c2g:bridge-import:IMPORTED-1",
                        "artifact_ref": ".omo/_delivery/ingress/tasks/IMPORTED-1.yaml",
                        "fingerprint": {"id": "IMPORTED-1"},
                        "created_at": "2026-06-18T00:00:00Z",
                    }
                },
                "by_source_ref": {"c2g:bridge-import:IMPORTED-1": "IMPORTED-1"},
            },
            "debts": {"by_id": {}, "by_source_ref": {}},
        },
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "ok"
    assert report["issues"] == []
