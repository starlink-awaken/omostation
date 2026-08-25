"""Drive the shipped SFOP slot checker (bin/gac/check-sfop-slots.py)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "check-sfop-slots.py"
DISPATCHER_ID = "COMP-WS-omo"


def _load_mod():
    spec = importlib.util.spec_from_file_location("check_sfop_slots", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_node(
    directory: Path,
    cid: str,
    *,
    slot: str | None,
    dao: str | None,
    status: str = "active",
) -> Path:
    props = ["  layer: L2", "  runtime: active"]
    if slot is not None:
        props.append(f"  sfop_slot: {slot}")
    if dao is not None:
        props.append(f"  dao_layer: {dao}")
    body = "\n".join(
        [
            f"id: {cid}",
            "type: Component",
            "subtype: Project",
            f"name: {cid.replace('COMP-WS-', '')}",
            f"status: {status}",
            "properties:",
            *props,
            "",
        ]
    )
    path = directory / f"{cid}.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def _write_registry(path: Path, names: list[str]) -> None:
    lines = ["projects:"]
    for name in names:
        lines.append(f"  {name}:")
        lines.append("    layer: L2")
        lines.append("    status: active")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestShippedCheckFunction:
    def test_valid_current_shaped_nodes_ok(self, tmp_path: Path) -> None:
        _write_node(tmp_path, DISPATCHER_ID, slot="S", dao="shu")
        _write_node(tmp_path, "COMP-WS-cockpit", slot="H", dao="qi")
        mod = _load_mod()
        result = mod.check(nodes_dir=tmp_path, registry_path=tmp_path / "missing.yaml")
        assert result["ok"] is True
        assert result["s_holders"] == [DISPATCHER_ID]
        assert result["errors"] == []
        for comp in result["components"]:
            assert "id" in comp
            assert "sfop_slot" in comp
            assert "dao_layer" in comp

    def test_missing_slot_fails_closed(self, tmp_path: Path) -> None:
        _write_node(tmp_path, DISPATCHER_ID, slot="S", dao="shu")
        _write_node(tmp_path, "COMP-WS-cockpit", slot=None, dao="qi")
        mod = _load_mod()
        result = mod.check(nodes_dir=tmp_path, registry_path=tmp_path / "missing.yaml")
        assert result["ok"] is False
        assert any("CR-SFOP-01" in err for err in result["errors"])

    def test_two_active_s_slots_fail_closed(self, tmp_path: Path) -> None:
        _write_node(tmp_path, DISPATCHER_ID, slot="S", dao="shu")
        _write_node(tmp_path, "COMP-WS-imposter", slot="S", dao="shu")
        mod = _load_mod()
        result = mod.check(nodes_dir=tmp_path, registry_path=tmp_path / "missing.yaml")
        assert result["ok"] is False
        assert any("CR-SFOP-02" in err for err in result["errors"])

    def test_registry_project_without_node_is_warning(self, tmp_path: Path) -> None:
        _write_node(tmp_path, DISPATCHER_ID, slot="S", dao="shu")
        registry = tmp_path / "registry.yaml"
        _write_registry(registry, ["omo", "toolbox"])
        mod = _load_mod()
        result = mod.check(nodes_dir=tmp_path, registry_path=registry)
        assert result["ok"] is True
        assert any("toolbox" in warn for warn in result["warnings"])


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
        assert "sfop-slots" not in module.CI_ONLY_CHECKS
        assert "sfop-slots" not in module.OPS_ONLY_CHECKS
        selected = module.gate_checks("files", ["bin/gac/check-sfop-slots.py"], "", False)
        selected_ids = {name for name, _cmd in selected}
        assert "sfop-slots" in selected_ids
        command = dict(selected)["sfop-slots"]
        assert command[:2] == ["bin/gac/check-sfop-slots.py", "--json"]


class TestShippedCli:
    def test_live_json_ok(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        assert data["ok"] is True
        assert data["s_holders"] == [DISPATCHER_ID]
        assert data["components"]
        for comp in data["components"]:
            assert comp["sfop_slot"]
            assert comp["dao_layer"]
