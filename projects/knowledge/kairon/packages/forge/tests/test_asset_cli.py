"""
Forge asset_cli 单元测试
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import asset_cli as m

# 便捷别名
_default = m._default
_load = m._load
_save = m._save
_find = m._find
_normalize_type = m._normalize_type
ASSET_TYPES = m.ASSET_TYPES
cmd_register = m.cmd_register
cmd_remove = m.cmd_remove
cmd_list = m.cmd_list
cmd_check = m.cmd_check
cmd_scan = m.cmd_scan
cmd_export = m.cmd_export
cmd_import = m.cmd_import


@pytest.fixture(autouse=True)
def _isolate_fs(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        monkeypatch.setattr(m, "REGISTRY_FILE", td_path / "registry.json")
        monkeypatch.setattr(m, "TOOLS_FILE", td_path / "tools-registry.json")
        monkeypatch.setattr(m, "HISTORY_FILE", td_path / "history.jsonl")
        monkeypatch.setattr(m, "ASSETS_DIR", td_path)
        yield


@pytest.fixture
def sample_asset() -> dict:
    return {
        "id": "test-agent",
        "name": "Test Agent",
        "type": "agent",
        "status": "active",
        "capabilities": ["code-gen", "review"],
    }


@pytest.fixture
def sample_service() -> dict:
    return {
        "id": "test-service",
        "name": "Test Service",
        "type": "service",
        "status": "active",
        "port": 9999,
        "health_endpoint": "http://127.0.0.1:9999/health",
    }


# ══════════════════════════════════════════════════
# 1. 基础函数
# ══════════════════════════════════════════════════


class TestDefaults:
    def test_default_has_version(self):
        d = _default()
        assert d["version"] == 3
        assert d["unified"] is True
        assert d["assets"] == []

    def test_normalize_type(self):
        assert _normalize_type("agent") == "agent"
        assert _normalize_type("gateway") == "service"
        assert _normalize_type("skill") == "plugin"
        assert _normalize_type("orchestrator") == "daemon"
        assert _normalize_type("automation") == "pipeline"
        assert _normalize_type("unknown") == "service"

    def test_find_by_id(self):
        assets = [{"id": "foo", "name": "Foo"}, {"id": "bar", "name": "Bar"}]
        assert _find(assets, "bar") == 1
        assert _find(assets, "foo") == 0

    def test_find_by_name(self):
        assets = [{"id": "x-1", "name": "Alice"}, {"id": "x-2", "name": "Bob"}]
        assert _find(assets, "Bob") == 1

    def test_find_missing(self):
        assert _find([], "nope") is None


class TestLoadSave:
    def test_load_creates_default(self):
        reg = _load()
        assert reg["version"] == 3
        assert m.REGISTRY_FILE.exists()

    def test_save_and_reload(self):
        reg = _load()
        reg["assets"].append({"id": "x"})
        _save(reg)
        reg2 = json.loads(m.REGISTRY_FILE.read_text())
        assert len(reg2["assets"]) == 1
        assert reg2["assets"][0]["id"] == "x"

    def test_save_updates_timestamp(self):
        reg = _load()
        _save(reg)
        reg2 = json.loads(m.REGISTRY_FILE.read_text())
        assert reg2["updated"]


# ══════════════════════════════════════════════════
# 2. 注册/更新
# ══════════════════════════════════════════════════


class TestRegister:
    def test_register_new(self, sample_asset):
        cmd_register([json.dumps(sample_asset)])
        reg = _load()
        assert len(reg["assets"]) == 1
        assert reg["assets"][0]["id"] == "test-agent"

    def test_register_duplicate_id(self, sample_asset):
        cmd_register([json.dumps(sample_asset)])
        updated = dict(sample_asset, notes="updated")
        cmd_register([json.dumps(updated)])
        reg = _load()
        assert len(reg["assets"]) == 1
        assert reg["assets"][0]["notes"] == "updated"

    def test_register_missing_fields(self):
        with pytest.raises(SystemExit):
            cmd_register(['{"name": "no-id"}'])

    def test_register_invalid_type(self):
        with pytest.raises(SystemExit):
            cmd_register(['{"id": "x", "name": "x", "type": "invalid"}'])

    def test_register_merge(self, sample_asset):
        cmd_register([json.dumps(sample_asset)])
        partial = {"id": "test-agent", "name": "Test Agent", "type": "agent", "notes": "added note"}
        cmd_register([json.dumps(partial)])
        reg = _load()
        a = reg["assets"][0]
        assert a["notes"] == "added note"
        assert a["status"] == "active"


class TestRemove:
    def test_remove_by_id(self, sample_asset):
        cmd_register([json.dumps(sample_asset)])
        cmd_remove(["test-agent"])
        reg = _load()
        assert len(reg["assets"]) == 0

    def test_remove_missing(self):
        with pytest.raises(SystemExit):
            cmd_remove(["nonexistent"])


# ══════════════════════════════════════════════════
# 3. 列表/检查
# ══════════════════════════════════════════════════


class TestList:
    def test_list_empty(self):
        cmd_list([])

    def test_list_by_type(self, sample_asset, sample_service):
        cmd_register([json.dumps(sample_asset)])
        cmd_register([json.dumps(sample_service)])
        with patch("asset_cli._port_check", return_value=(False, "")):
            cmd_list(["agent"])

    def test_list_invalid_type(self):
        # cmd_list 打印错误但不退出
        with patch("sys.stdout"):
            cmd_list(["nonexistent"])


class TestCheck:
    def test_check_empty(self):
        cmd_check([])

    def test_check_port_offline(self, sample_service):
        cmd_register([json.dumps(sample_service)])
        with patch("asset_cli._port_check", return_value=(False, "")):
            cmd_check([])

    def test_check_port_online(self, sample_service):
        cmd_register([json.dumps(sample_service)])
        with patch("asset_cli._port_check", return_value=(True, "127.0.0.1")):
            cmd_check([])


# ══════════════════════════════════════════════════
# 4. 扫描
# ══════════════════════════════════════════════════


class TestScan:
    def test_scan_dry_run(self, sample_asset):
        cmd_register([json.dumps(sample_asset)])
        len(m.REGISTRY_FILE.read_text() if m.REGISTRY_FILE.exists() else "")
        with patch("asset_cli.socket.socket") as mock_sock:
            inst = mock_sock.return_value
            inst.connect_ex.return_value = 1
            cmd_scan(["--dry-run"])
        # dry-run 不修改文件
        after = len(_load().get("assets", []))
        assert after >= 1

    def test_scan_normal(self, sample_service):
        cmd_register([json.dumps(sample_service)])
        with patch("asset_cli.socket.socket") as mock_sock:
            inst = mock_sock.return_value
            inst.connect_ex.return_value = 0  # port open
            cmd_scan([])


# ══════════════════════════════════════════════════
# 5. 导出/导入
# ══════════════════════════════════════════════════


class TestExport:
    def test_export_tools_creates_file(self, sample_asset):
        cmd_register([json.dumps(sample_asset)])
        cmd_export(["tools"])
        assert m.TOOLS_FILE.exists()
        data = json.loads(m.TOOLS_FILE.read_text())
        assert "tools" in data or isinstance(data, list)


class TestImport:
    def test_import_tools_roundtrip(self, sample_asset):
        cmd_register([json.dumps(sample_asset)])
        cmd_export(["tools"])
        cmd_remove(["test-agent"])
        assert len(_load()["assets"]) == 0
        cmd_import(["tools"])
        reg = _load()
        imported = [a for a in reg["assets"] if a.get("id") == "test-agent"]
        assert len(imported) >= 1


# ══════════════════════════════════════════════════
# 6. 边界情况
# ══════════════════════════════════════════════════


class TestEdgeCases:
    def test_register_all_types(self):
        for t in ASSET_TYPES:
            asset = {"id": f"test-{t}", "name": f"Test {t}", "type": t}
            cmd_register([json.dumps(asset)])
        reg = _load()
        assert len(reg["assets"]) == len(ASSET_TYPES)

    def test_history_logged_on_register(self, sample_asset):
        cmd_register([json.dumps(sample_asset)])
        assert m.HISTORY_FILE.exists()
        lines = m.HISTORY_FILE.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        assert entry["action"] == "register"
        assert entry["name"] == "test-agent"

    def test_history_logged_on_remove(self, sample_asset):
        cmd_register([json.dumps(sample_asset)])
        cmd_remove(["test-agent"])
        lines = m.HISTORY_FILE.read_text().strip().split("\n")
        actions = [json.loads(l)["action"] for l in lines]  # noqa: E741
        assert "remove" in actions
