"""Drive the shipped SFOP/DFSQ slot checker."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "check-sfop-slots.py"


def _load_mod():
    spec = importlib.util.spec_from_file_location("check_sfop_slots", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _node(directory: Path, name: str, slot: str, dao: str, status: str = "active") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"COMP-WS-{name}.yaml").write_text(
        "\n".join(
            [
                f"id: COMP-WS-{name}",
                "type: Component",
                "subtype: Project",
                f"status: {status}",
                "properties:",
                f"  sfop_slot: {slot}",
                f"  dao_layer: {dao}",
                "",
            ]
        ),
        encoding="utf-8",
    )


class TestCoreLaws:
    def test_valid_nodes_pass(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        _node(nodes, "cockpit", "H", "qi")
        registry = tmp_path / "registry.yaml"
        registry.write_text("projects:\n  omo: {}\n  cockpit: {}\n", encoding="utf-8")
        cron = tmp_path / "cron.yaml"
        cron.write_text("jobs: []\n", encoding="utf-8")
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=registry,
            cron_registry_path=cron,
            projects_root=tmp_path / "projects",
            baseline_path=tmp_path / "baseline.txt",
            x3_path=tmp_path / "x3.yaml",
            repo_root=tmp_path,
        )
        assert result["ok"] is True
        assert result["s_holders"] == ["COMP-WS-omo"]
        assert "P" in result["vacant_slots"]
        assert "O" in result["vacant_slots"]

    def test_missing_slot_fails(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        nodes.mkdir()
        (nodes / "COMP-WS-omo.yaml").write_text(
            "id: COMP-WS-omo\nstatus: active\nproperties:\n  dao_layer: shu\n",
            encoding="utf-8",
        )
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=tmp_path / "missing.yaml",
            cron_registry_path=tmp_path / "cron.yaml",
            skip_call_scan=True,
        )
        assert result["ok"] is False
        assert any("CR-SFOP-01" in err for err in result["errors"])

    def test_second_dispatcher_fails(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        _node(nodes, "agora", "S", "shu")
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=tmp_path / "missing.yaml",
            cron_registry_path=tmp_path / "cron.yaml",
            skip_call_scan=True,
        )
        assert result["ok"] is False
        assert any("CR-SFOP-02" in err for err in result["errors"])

    def test_toolbox_external_not_warned(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        registry = tmp_path / "registry.yaml"
        registry.write_text(
            "projects:\n  omo: {}\n  toolbox:\n    build_backend: external-capability-runtime\n",
            encoding="utf-8",
        )
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=registry,
            cron_registry_path=tmp_path / "cron.yaml",
            skip_call_scan=True,
        )
        assert result["ok"] is True
        assert not any("toolbox" in w for w in result["warnings"])


class TestDfsqCross:
    def test_dao_cron_fails(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        _node(nodes, "l4-kernel", "K", "dao")
        cron = tmp_path / "cron.yaml"
        cron.write_text(
            "jobs:\n- id: dao-tick\n  command: python3 projects/l4-kernel/bin/tick.py\n",
            encoding="utf-8",
        )
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=tmp_path / "missing.yaml",
            cron_registry_path=cron,
            skip_call_scan=True,
        )
        assert result["ok"] is False
        assert any("CR-DFSQ-01" in err for err in result["errors"])

    def test_qi_l0_required_fails(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        _node(nodes, "cockpit", "H", "qi")
        l0 = tmp_path / "projects" / "cockpit" / "L0-constraints.yaml"
        l0.parent.mkdir(parents=True)
        l0.write_text("id: CR-FAKE-01\ntype: required\n", encoding="utf-8")
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=tmp_path / "missing.yaml",
            cron_registry_path=tmp_path / "cron.yaml",
            projects_root=tmp_path / "projects",
            repo_root=tmp_path,
            skip_call_scan=True,
        )
        assert result["ok"] is False
        assert any("CR-DFSQ-02" in err for err in result["errors"])


class TestHbAdjacency:
    def test_new_hb_call_fails_closed(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        _node(nodes, "cockpit", "H", "qi")
        caller = tmp_path / "projects" / "cockpit" / "src" / "hit.py"
        caller.parent.mkdir(parents=True)
        caller.write_text("from aetherforge.bridge import llm_generate\n", encoding="utf-8")
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=tmp_path / "missing.yaml",
            cron_registry_path=tmp_path / "cron.yaml",
            projects_root=tmp_path / "projects",
            baseline_path=tmp_path / "empty-baseline.txt",
            repo_root=tmp_path,
        )
        assert result["ok"] is False
        assert any("CR-SFOP-05" in err for err in result["errors"])

    def test_baseline_hb_call_warns(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        caller = tmp_path / "projects" / "cockpit" / "src" / "hit.py"
        caller.parent.mkdir(parents=True)
        caller.write_text("from aetherforge.bridge import llm_generate\n", encoding="utf-8")
        key = "projects/cockpit/src/hit.py:1:H->B:cockpit->aetherforge"
        baseline = tmp_path / "baseline.txt"
        baseline.write_text(key + "\n", encoding="utf-8")
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=tmp_path / "missing.yaml",
            cron_registry_path=tmp_path / "cron.yaml",
            projects_root=tmp_path / "projects",
            baseline_path=baseline,
            repo_root=tmp_path,
        )
        assert result["ok"] is True
        assert any("CR-SFOP-05" in w and "[baseline]" in w for w in result["warnings"])


class TestGateInventory:
    def test_sfop_slots_is_blocking_not_soft(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "gac_local_gate_sfop",
            REPO_ROOT / "bin" / "gac" / "gac-local-gate.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        ids = {name for name, _cmd in module.CHECKS}
        assert "sfop-slots" in ids
        assert "sfop-slots" not in module.SOFT_CHECKS


class TestShippedCli:
    def test_live_json_ok(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout
        data = json.loads(proc.stdout)
        assert data["ok"] is True
        assert data["s_holders"] == ["COMP-WS-omo"]
        assert "P" in data["vacant_slots"]
        assert "O" in data["vacant_slots"]
        assert not any("toolbox" in w for w in data["warnings"])
        assert "CR-SFOP-05" in data["constraint_ids"]
        assert "CR-DFSQ-01" in data["constraint_ids"]
