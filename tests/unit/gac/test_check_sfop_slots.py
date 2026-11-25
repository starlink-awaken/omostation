"""Drive the shipped SFOP/DFSQ slot checker."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# 下面两条直接读 omo 内核源码做「已修正树」对照; 干净检出上该文件缺席属输入没备齐。
_OMO_CLI_SRC = REPO_ROOT / "projects" / "omo" / "src" / "omo" / "cli.py"
_REQUIRES_OMO_CLI = pytest.mark.skipif(
    not _OMO_CLI_SRC.exists(),
    reason=(
        f"omo 内核源码缺席: {_OMO_CLI_SRC} —— "
        "先 `git submodule update --init projects/omo`（检出形态, 不是回归）"
    ),
)
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
        key = "projects/cockpit/src/hit.py:H->B:cockpit->aetherforge"
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

    def test_legacy_line_numbered_baseline_still_matches(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        caller = tmp_path / "projects" / "cockpit" / "src" / "hit.py"
        caller.parent.mkdir(parents=True)
        caller.write_text("from aetherforge.bridge import llm_generate\n", encoding="utf-8")
        baseline = tmp_path / "baseline.txt"
        baseline.write_text("projects/cockpit/src/hit.py:1:H->B:cockpit->aetherforge\n", encoding="utf-8")
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

    def test_adapter_seam_does_not_fail(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        caller = tmp_path / "projects" / "cockpit" / "src" / "cockpit" / "adapters" / "runtime.py"
        caller.parent.mkdir(parents=True)
        caller.write_text("from runtime.executor.engine import AgentRuntime\n", encoding="utf-8")
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=tmp_path / "missing.yaml",
            cron_registry_path=tmp_path / "cron.yaml",
            projects_root=tmp_path / "projects",
            baseline_path=tmp_path / "empty.txt",
            repo_root=tmp_path,
        )
        assert result["ok"] is True
        assert any("adapter seam" in w for w in result["warnings"])
        assert result["hb_seam_files"]

    def test_venv_scan_parts_are_ignored(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        noise = tmp_path / "projects" / "cockpit" / ".venv" / "lib" / "site-packages" / "hit.py"
        noise.parent.mkdir(parents=True)
        noise.write_text("from aetherforge.bridge import llm_generate\n", encoding="utf-8")
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=tmp_path / "missing.yaml",
            cron_registry_path=tmp_path / "cron.yaml",
            projects_root=tmp_path / "projects",
            baseline_path=tmp_path / "empty.txt",
            repo_root=tmp_path,
        )
        assert result["ok"] is True
        assert not any("CR-SFOP-05" in e for e in result["errors"])

    def test_claimed_active_cron_missing_slot_fails(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        cron = tmp_path / "cron.yaml"
        cron.write_text(
            "jobs:\n  - name: live-sched\n    status: active\n    command: python3 bin/gac/meta-doctor.py\n",
            encoding="utf-8",
        )
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=tmp_path / "missing.yaml",
            cron_registry_path=cron,
            projects_root=tmp_path / "projects",
            baseline_path=tmp_path / "empty.txt",
            repo_root=tmp_path,
            skip_call_scan=True,
        )
        assert result["ok"] is False
        assert any("CR-SFOP-06" in e and "live-sched" in e for e in result["errors"])

    def test_claimed_active_cron_illegal_slot_fails(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        cron = tmp_path / "cron.yaml"
        cron.write_text(
            "jobs:\n  - name: live-sched\n    status: active\n    sfop_slot: Z\n"
            "    command: python3 bin/gac/meta-doctor.py\n",
            encoding="utf-8",
        )
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=tmp_path / "missing.yaml",
            cron_registry_path=cron,
            projects_root=tmp_path / "projects",
            skip_call_scan=True,
        )
        assert result["ok"] is False
        assert any("CR-SFOP-06" in e and "sfop_slot='Z'" in e for e in result["errors"])

    def test_unclaimed_cron_missing_slot_warns(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        cron = tmp_path / "cron.yaml"
        cron.write_text(
            "jobs:\n  - name: historic\n    command: python3 bin/gac/meta-doctor.py\n",
            encoding="utf-8",
        )
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=tmp_path / "missing.yaml",
            cron_registry_path=cron,
            projects_root=tmp_path / "projects",
            skip_call_scan=True,
        )
        assert result["ok"] is True
        assert any("CR-SFOP-06" in w and "historic" in w for w in result["warnings"])
        assert not any("CR-SFOP-06" in e for e in result["errors"])

    def test_claimed_active_cron_legal_slot_passes(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        cron = tmp_path / "cron.yaml"
        cron.write_text(
            "jobs:\n  - name: live-sched\n    status: active\n    sfop_slot: S\n"
            "    command: python3 bin/gac/meta-doctor.py\n",
            encoding="utf-8",
        )
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=tmp_path / "missing.yaml",
            cron_registry_path=cron,
            projects_root=tmp_path / "projects",
            skip_call_scan=True,
        )
        assert result["ok"] is True
        assert not any("CR-SFOP-06" in e for e in result["errors"])

    def test_claimed_active_h_cron_reaching_b_fails(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes"
        _node(nodes, "omo", "S", "shu")
        cron = tmp_path / "cron.yaml"
        cron.write_text(
            "jobs:\n  - name: h-job\n    status: active\n    sfop_slot: H\n"
            "    command: python3 projects/runtime/bin/run.py\n",
            encoding="utf-8",
        )
        mod = _load_mod()
        result = mod.check(
            nodes_dir=nodes,
            registry_path=tmp_path / "missing.yaml",
            cron_registry_path=cron,
            projects_root=tmp_path / "projects",
            skip_call_scan=True,
        )
        assert result["ok"] is False
        assert any("CR-SFOP-05" in e and "h-job" in e for e in result["errors"])


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
        # s_holders 是**live 快照**: COMP-WS-omo 的声明在 projects/ecos 子模块的
        # nodes 目录里 (DEFAULT_NODES)。未 init 子模块 / 干净检出时该目录不存在
        # ⇒ s_holders=[] —— 那是检出形态, 不是缺陷。与下面 vacant_slots 同类
        # (那处已经因为 live 快照断言失效过一次, 见下)。
        nodes_dir = REPO_ROOT / "projects/ecos/src/ecos/ssot/mof/nodes"
        assert data["s_holders"] == (["COMP-WS-omo"] if nodes_dir.is_dir() else [])
        # vacant_slots 是**派生值** (VACANT_ALLOWED 减去已占用槽)。此前断言
        # `"P" in vacant_slots` 属 live 快照 —— P 现由 COMP-WS-ecos /
        # COMP-WS-observability 合法占用 (CR-SFOP-04 只规定 P/O **可**空缺,
        # 不要求其必须空缺), 故该断言随仓库演进失效。
        # 改为断言**推导正确性**: vacant = VACANT_ALLOWED - occupied。
        mod = _load_mod()
        occupied = {c["sfop_slot"] for c in data["components"]}
        assert set(data["vacant_slots"]) <= mod.VACANT_ALLOWED
        assert data["vacant_slots"] == sorted(mod.VACANT_ALLOWED - occupied)
        assert not any("toolbox" in w for w in data["warnings"])
        assert "CR-SFOP-05" in data["constraint_ids"]
        assert "CR-SFOP-06" in data["constraint_ids"]
        assert "CR-DFSQ-01" in data["constraint_ids"]
        assert not any("CR-SFOP-06" in e for e in data["errors"])
        assert not any("CR-SFOP-03" in e for e in data["errors"])


_DIRECT_CELL = """
def main(args):
    if args and args[0] == "cell":
        from omo.resident.cell_cli import main as cell_main
        from omo.workflow_mesh import WorkflowMeshStore, dispatch_backend
        omo_dir = _omo_dir()
        store = WorkflowMeshStore(omo_dir) if omo_dir is not None else None
        if store is not None:
            return dispatch_backend(store, "cell", cell_main, args[1:])
        return cell_main(args[1:])
"""

_HIDE_CELL = """
def main(args):
    if args and args[0] == "cell":
        from omo.resident.cell_cli import main as cell_main
        from omo.workflow_mesh import dispatch_backend
        omo_dir = _omo_dir()
        if omo_dir is None:
            print("cell: no .omo directory", file=sys.stderr)
            return 1
        try:
            store.append(event)
        except Exception:
            pass
        return dispatch_backend(store, "cell", cell_main, args[1:])
"""

_NAME_ONLY_CELL = """
def main(args):
    if args and args[0] == "cell":
        from omo.workflow_mesh import dispatch_backend
        return dispatch_backend(store, "cell", cell_main, args[1:])
"""

_SWALLOW_DISPATCH = """
def dispatch_backend(store, backend_name, fn, args):
    try:
        store.append(event)
    except Exception:
        pass
    return fn(args)
"""


def _slot_check(mod, tmp_path: Path, cell_source: str | None = None, *, mesh: str | None = None):
    nodes = tmp_path / "nodes"
    _node(nodes, "omo", "S", "shu")
    _node(nodes, "cockpit", "H", "qi")
    registry = tmp_path / "registry.yaml"
    registry.write_text("projects:\n  omo: {}\n  cockpit: {}\n", encoding="utf-8")
    if mesh is not None:
        mesh_path = tmp_path / "projects/omo/src/omo/workflow_mesh.py"
        mesh_path.parent.mkdir(parents=True, exist_ok=True)
        mesh_path.write_text(mesh, encoding="utf-8")
    if cell_source is not None:
        cli_path = tmp_path / "projects/omo/src/omo/cli.py"
        cli_path.parent.mkdir(parents=True, exist_ok=True)
        cli_path.write_text(cell_source, encoding="utf-8")
    return mod.check(
        nodes_dir=nodes,
        registry_path=registry,
        cron_registry_path=tmp_path / "cron.yaml",
        projects_root=tmp_path / "projects",
        baseline_path=tmp_path / "baseline.txt",
        x3_path=tmp_path / "x3.yaml",
        repo_root=tmp_path,
        cell_entry_source=cell_source,
    )


class TestCellEntryBypass:
    def test_direct_backend_when_no_store(self, tmp_path: Path) -> None:
        mod = _load_mod()
        result = _slot_check(mod, tmp_path, _DIRECT_CELL)
        assert result["ok"] is False
        assert any(
            "calls the backend directly when no store exists" in err
            for err in result["errors"]
        )

    def test_hides_event_write_error(self, tmp_path: Path) -> None:
        mod = _load_mod()
        result = _slot_check(mod, tmp_path, _HIDE_CELL)
        assert result["ok"] is False
        assert any("hides an event-write error" in err for err in result["errors"])
        assert not any("calls the backend directly" in err for err in result["errors"])

    def test_dispatcher_name_alone_is_not_a_pass(self, tmp_path: Path) -> None:
        mod = _load_mod()
        result = _slot_check(mod, tmp_path, _NAME_ONLY_CELL)
        assert result["ok"] is False
        assert any("naming dispatch_backend does not fail-close" in err for err in result["errors"])
        assert mod.cell_entry_bypass_errors("dispatch_backend") != []

    @_REQUIRES_OMO_CLI
    def test_swallowed_dispatch_function_fails(self, tmp_path: Path) -> None:
        mod = _load_mod()
        corrected = (REPO_ROOT / "projects/omo/src/omo/cli.py").read_text(encoding="utf-8")
        result = _slot_check(mod, tmp_path, corrected, mesh=_SWALLOW_DISPATCH)
        assert result["ok"] is False
        assert any("dispatch_backend hides an event-write error" in err for err in result["errors"])

    @_REQUIRES_OMO_CLI
    def test_corrected_tree_has_no_cr_sfop_03(self, tmp_path: Path) -> None:
        mod = _load_mod()
        cli = (REPO_ROOT / "projects/omo/src/omo/cli.py").read_text(encoding="utf-8")
        mesh = (REPO_ROOT / "projects/omo/src/omo/workflow_mesh.py").read_text(encoding="utf-8")
        assert mod.cell_entry_bypass_errors(cli) == []
        assert mod.dispatch_backend_write_errors(mesh) == []
        result = _slot_check(mod, tmp_path, cli, mesh=mesh)
        assert result["ok"] is True
        assert not any("CR-SFOP-03" in err for err in result["errors"])
