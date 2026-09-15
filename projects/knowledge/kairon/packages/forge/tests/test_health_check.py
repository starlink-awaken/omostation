"""Forge health_check.py 单元测试

测试覆盖:
- 模块导入与结构
- 各检查函数（_check_registry, _check_graph, _check_scripts, _check_disk, _check_kos, _check_sync）
- run() 主入口
- 错误/边界路径
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))


@pytest.fixture
def hc():
    import health_check

    return health_check


@pytest.fixture
def sample_registry() -> dict:
    return {
        "schema_version": "1.2",
        "tools": [
            {"id": "tool-a", "status": "active", "capabilities": ["code"]},
            {"id": "tool-b", "status": "candidate", "capabilities": ["vision"]},
        ],
        "event_log": [{"type": "test", "timestamp": "2026-01-01", "summary": "test"}],
        "last_updated": "2026-05-28",
    }


# ═══════════════════════════════════════════════════
# 1. 模块导入与结构
# ═══════════════════════════════════════════════════


class TestImports:
    def test_module_imports(self):
        import health_check

        assert hasattr(health_check, "run")
        assert callable(health_check.run)

    def test_constants_defined(self, hc):
        assert hasattr(hc, "REGISTRY")
        assert hasattr(hc, "SCRIPTS")
        assert hasattr(hc, "GRAPH")


# ═══════════════════════════════════════════════════
# 2. _check_registry
# ═══════════════════════════════════════════════════


class TestCheckRegistry:
    def test_registry_exists_and_valid(self, hc, monkeypatch, tmp_path):
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "tools": [{"id": "t1", "status": "active"}],
                    "event_log": [],
                }
            )
        )
        monkeypatch.setattr(hc, "REGISTRY", reg_file)
        hc._ok = hc._wrn = hc._err = 0
        hc._check_registry()
        assert hc._err == 0

    def test_registry_missing(self, hc, monkeypatch, tmp_path):
        reg_file = tmp_path / "nonexistent.json"
        monkeypatch.setattr(hc, "REGISTRY", reg_file)
        hc._ok = hc._wrn = hc._err = 0
        hc._check_registry()
        assert hc._err > 0

    def test_registry_corrupt_json(self, hc, monkeypatch, tmp_path):
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text("{invalid json}")
        monkeypatch.setattr(hc, "REGISTRY", reg_file)
        hc._ok = hc._wrn = hc._err = 0
        hc._check_registry()
        assert hc._err > 0

    def test_registry_missing_tools_key(self, hc, monkeypatch, tmp_path):
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(json.dumps({"schema_version": "1.0"}))
        monkeypatch.setattr(hc, "REGISTRY", reg_file)
        hc._ok = hc._wrn = hc._err = 0
        hc._check_registry()
        assert hc._err > 0

    def test_registry_empty_tools(self, hc, monkeypatch, tmp_path):
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "tools": [],
                    "event_log": [],
                }
            )
        )
        monkeypatch.setattr(hc, "REGISTRY", reg_file)
        hc._ok = hc._wrn = hc._err = 0
        hc._check_registry()
        assert hc._ok >= 2  # passes for count and schema


# ═══════════════════════════════════════════════════
# 3. _check_graph
# ═══════════════════════════════════════════════════


class TestCheckGraph:
    def test_graph_exists_with_nodes(self, hc, monkeypatch, tmp_path):
        graph_file = tmp_path / "graph" / "graph.json"
        graph_file.parent.mkdir(parents=True)
        graph_file.write_text(
            json.dumps(
                {
                    "stats": {"total_nodes": 10, "total_edges": 5},
                    "nodes": [{"id": "n1"}],
                    "edges": [],
                }
            )
        )
        monkeypatch.setattr(hc, "GRAPH", graph_file)
        hc._ok = hc._wrn = hc._err = 0
        hc._check_graph()
        assert hc._wrn == 0
        assert hc._err == 0

    def test_graph_missing(self, hc, monkeypatch, tmp_path):
        graph_file = tmp_path / "graph" / "graph.json"
        monkeypatch.setattr(hc, "GRAPH", graph_file)
        hc._ok = hc._wrn = hc._err = 0
        hc._check_graph()
        assert hc._wrn > 0

    def test_graph_corrupt(self, hc, monkeypatch, tmp_path):
        graph_file = tmp_path / "graph" / "graph.json"
        graph_file.parent.mkdir(parents=True)
        graph_file.write_text("{bad json}")
        monkeypatch.setattr(hc, "GRAPH", graph_file)
        hc._ok = hc._wrn = hc._err = 0
        hc._check_graph()
        assert hc._wrn > 0

    def test_graph_empty(self, hc, monkeypatch, tmp_path):
        graph_file = tmp_path / "graph" / "graph.json"
        graph_file.parent.mkdir(parents=True)
        graph_file.write_text(
            json.dumps(
                {
                    "stats": {"total_nodes": 0, "total_edges": 0},
                }
            )
        )
        monkeypatch.setattr(hc, "GRAPH", graph_file)
        hc._ok = hc._wrn = hc._err = 0
        hc._check_graph()
        assert hc._wrn > 0


# ═══════════════════════════════════════════════════
# 4. _check_scripts
# ═══════════════════════════════════════════════════


class TestCheckScripts:
    def test_all_scripts_exist(self, hc, monkeypatch, tmp_path):
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        for name in ("build-graph.sh", "query-graph.sh", "sniff-local.sh", "classify.sh"):
            (scripts_dir / name).write_text("#!/bin/bash\necho ok")
        monkeypatch.setattr(hc, "SCRIPTS", scripts_dir)
        hc._ok = hc._wrn = hc._err = 0
        hc._check_scripts()
        assert hc._ok == 4
        assert hc._wrn == 0

    def test_some_scripts_missing(self, hc, monkeypatch, tmp_path):
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "build-graph.sh").write_text("#!/bin/bash")
        monkeypatch.setattr(hc, "SCRIPTS", scripts_dir)
        hc._ok = hc._wrn = hc._err = 0
        hc._check_scripts()
        assert hc._ok >= 1
        assert hc._wrn >= 1


# ═══════════════════════════════════════════════════
# 5. _check_disk
# ═══════════════════════════════════════════════════


class TestCheckDisk:
    def test_disk_check_success(self, hc, monkeypatch):
        hc._ok = hc._wrn = hc._err = 0
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "1.2M\t/path/to/project\n"
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            hc._check_disk()
            assert hc._ok > 0

    def test_disk_check_exception(self, hc, monkeypatch):
        hc._ok = hc._wrn = hc._err = 0
        with patch("subprocess.run", side_effect=Exception("no du")):
            hc._check_disk()
            assert hc._wrn > 0


# ═══════════════════════════════════════════════════
# 6. _check_kos
# ═══════════════════════════════════════════════════


class TestCheckKos:
    def test_kos_probe_not_found(self, hc, monkeypatch, tmp_path):
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        monkeypatch.setattr(hc, "SCRIPTS", scripts_dir)
        hc._ok = hc._wrn = hc._err = 0
        hc._check_kos()
        assert hc._wrn > 0

    def test_kos_probe_success(self, hc, monkeypatch, tmp_path):
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "kos-probe.py").write_text("")
        monkeypatch.setattr(hc, "SCRIPTS", scripts_dir)
        hc._ok = hc._wrn = hc._err = 0
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "KOS 状态: code-complete\n"
            mock_result.stderr = ""
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            hc._check_kos()
            assert hc._ok > 0

    def test_kos_probe_exception(self, hc, monkeypatch, tmp_path):
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "kos-probe.py").write_text("")
        monkeypatch.setattr(hc, "SCRIPTS", scripts_dir)
        hc._ok = hc._wrn = hc._err = 0
        with patch("subprocess.run", side_effect=Exception("timeout")):
            hc._check_kos()
            assert hc._wrn > 0


# ═══════════════════════════════════════════════════
# 7. _check_sync
# ═══════════════════════════════════════════════════


class TestCheckSync:
    def test_sync_updated_today(self, hc, monkeypatch, tmp_path):
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(
            json.dumps(
                {
                    "last_updated": "2026-05-28",
                }
            )
        )
        monkeypatch.setattr(hc, "REGISTRY", reg_file)
        hc._ok = hc._wrn = hc._err = 0
        with patch("health_check.date") as mock_date:
            mock_date.today.return_value.isoformat.return_value = "2026-05-28"
            hc._check_sync()
            assert hc._ok > 0

    def test_sync_not_updated(self, hc, monkeypatch, tmp_path):
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(
            json.dumps(
                {
                    "last_updated": "2026-01-01",
                }
            )
        )
        monkeypatch.setattr(hc, "REGISTRY", reg_file)
        hc._ok = hc._wrn = hc._err = 0
        hc._check_sync()
        assert hc._wrn > 0

    def test_sync_cannot_read(self, hc, monkeypatch, tmp_path):
        reg_file = tmp_path / "nonexistent.json"
        monkeypatch.setattr(hc, "REGISTRY", reg_file)
        hc._ok = hc._wrn = hc._err = 0
        hc._check_sync()
        assert hc._wrn > 0


# ═══════════════════════════════════════════════════
# 8. run() 主入口
# ═══════════════════════════════════════════════════


class TestRun:
    def test_run_all_pass(self, hc, monkeypatch, tmp_path):
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "tools": [],
                    "event_log": [],
                    "last_updated": "2026-05-28",
                }
            )
        )
        monkeypatch.setattr(hc, "REGISTRY", reg_file)
        monkeypatch.setattr(hc, "SCRIPTS", tmp_path / "scripts")
        graph_file = tmp_path / "graph" / "graph.json"
        graph_file.parent.mkdir(parents=True)
        graph_file.write_text(json.dumps({"stats": {"total_nodes": 1, "total_edges": 0}}))
        monkeypatch.setattr(hc, "GRAPH", graph_file)
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "1.0M\t/tmp\n"
            mock_result.stderr = ""
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            with patch("health_check.date") as mock_date:
                mock_date.today.return_value.isoformat.return_value = "2026-05-28"
                rc = hc.run()
        assert rc == 0

    def test_run_with_errors(self, hc, monkeypatch, tmp_path):
        reg_file = tmp_path / "nonexistent.json"
        monkeypatch.setattr(hc, "REGISTRY", reg_file)
        monkeypatch.setattr(hc, "SCRIPTS", tmp_path / "scripts")
        monkeypatch.setattr(hc, "GRAPH", tmp_path / "graph" / "graph.json")
        with patch("subprocess.run", side_effect=Exception("fail")):
            rc = hc.run()
        assert rc == 1  # error present
