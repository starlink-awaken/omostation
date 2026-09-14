"""
entropy 反熵系统单元测试

测试覆盖:
- _days_since —— 日期差计算
- sunrise_cleanup —— 候选池清理
- sunset_auto_deprecate —— 自动废弃
- converge_* —— 收敛检查
- CLI 调度函数
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import datetime
import json
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import entropy as m


class TestDaysSince:
    """测试日期差计算。"""

    def test_today(self):
        today = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")
        assert m._days_since(today) == 0

    def test_yesterday(self):
        yesterday = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        assert m._days_since(yesterday) >= 1

    def test_invalid_date(self):
        assert m._days_since("invalid") == 0

    def test_empty_string(self):
        assert m._days_since("") == 0


class TestNowTs:
    """测试时间戳生成。"""

    def test_returns_iso_format(self):
        ts = m._now_ts()
        assert ts.endswith("Z")
        assert "T" in ts
        # Should be parseable
        datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")


class TestSunriseCleanup:
    """测试 sunrise_cleanup 候选池清理。"""

    def _make_registry(self, tmp_path, tools):
        """在 tmp_path 中创建注册表文件并 monkeypatch REGISTRY。"""
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(json.dumps({"tools": tools}))
        return reg_file

    def test_no_candidates(self, tmp_path, monkeypatch):
        reg_file = self._make_registry(tmp_path, [{"id": "t1", "status": "active"}])
        monkeypatch.setattr(m, "REGISTRY", reg_file)
        monkeypatch.setattr(m, "CANDIDATE_DAYS", 30)
        result = m.sunrise_cleanup(quiet=True)
        assert result == 0

    def test_expired_candidate_dry_run(self, tmp_path, monkeypatch):
        old = (datetime.datetime.now() - datetime.timedelta(days=40)).strftime("%Y-%m-%d")
        tools = [
            {
                "id": "old-tool",
                "status": "candidate",
                "_discovery": {"first_seen": old, "source": "test"},
            }
        ]
        self._make_registry(tmp_path, tools)
        monkeypatch.setattr(m, "REGISTRY", tmp_path / "tools-registry.json")
        monkeypatch.setattr(m, "CANDIDATE_DAYS", 30)
        result = m.sunrise_cleanup(dry_run=True, quiet=True)
        assert result == 1

    def test_expired_candidate_removed(self, tmp_path, monkeypatch):
        old = (datetime.datetime.now() - datetime.timedelta(days=40)).strftime("%Y-%m-%d")
        tools = [
            {"id": "keep-tool", "status": "candidate", "_discovery": {"first_seen": "2099-01-01", "source": "test"}},
            {"id": "remove-tool", "status": "candidate", "_discovery": {"first_seen": old, "source": "test"}},
        ]
        self._make_registry(tmp_path, tools)
        monkeypatch.setattr(m, "REGISTRY", tmp_path / "tools-registry.json")
        monkeypatch.setattr(m, "CANDIDATE_DAYS", 30)
        monkeypatch.setattr(m, "FORGE_ROOT", tmp_path)
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: type("R", (), {"returncode": 0})())

        result = m.sunrise_cleanup(dry_run=False, quiet=True)
        assert result == 1

        saved = json.loads((tmp_path / "tools-registry.json").read_text())
        saved_ids = [t["id"] for t in saved["tools"]]
        assert "remove-tool" not in saved_ids
        assert "keep-tool" in saved_ids
        # event_log should contain the removal
        events = [e for e in saved.get("event_log", []) if e.get("type") == "entropy:sunrise_expired"]
        assert len(events) == 1
        assert events[0]["tool_id"] == "remove-tool"

    def test_active_tool_not_affected(self, tmp_path, monkeypatch):
        tools = [
            {"id": "active-tool", "status": "active"},
            {
                "id": "candidate-tool",
                "status": "candidate",
                "_discovery": {"first_seen": "2080-01-01", "source": "test"},
            },
        ]
        self._make_registry(tmp_path, tools)
        monkeypatch.setattr(m, "REGISTRY", tmp_path / "tools-registry.json")
        monkeypatch.setattr(m, "CANDIDATE_DAYS", 30)
        monkeypatch.setattr(m, "FORGE_ROOT", tmp_path)
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: type("R", (), {"returncode": 0})())

        result = m.sunrise_cleanup(dry_run=False, quiet=True)
        assert result == 0
        saved = json.loads((tmp_path / "tools-registry.json").read_text())
        assert len(saved["tools"]) == 2


class TestSunsetAutoDeprecate:
    """测试 sunset_auto_deprecate 自动废弃。"""

    def _make_registry(self, tmp_path, tools):
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(json.dumps({"tools": tools}))
        return reg_file

    def test_no_stale_tools(self, tmp_path, monkeypatch):
        tools = [{"id": "active-tool", "status": "active"}]
        self._make_registry(tmp_path, tools)
        monkeypatch.setattr(m, "REGISTRY", tmp_path / "tools-registry.json")
        monkeypatch.setattr(m, "STALE_DAYS", 90)
        result = m.sunset_auto_deprecate(dry_run=True)
        assert result == 0

    def test_stale_not_expired(self, tmp_path, monkeypatch):
        recent = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        tools = [{"id": "fresh-stale", "status": "stale", "updated": recent}]
        self._make_registry(tmp_path, tools)
        monkeypatch.setattr(m, "REGISTRY", tmp_path / "tools-registry.json")
        monkeypatch.setattr(m, "STALE_DAYS", 90)
        result = m.sunset_auto_deprecate(dry_run=False)
        assert result == 0
        saved = json.loads((tmp_path / "tools-registry.json").read_text())
        assert saved["tools"][0]["status"] == "stale"  # unchanged

    def test_stale_expired(self, tmp_path, monkeypatch):
        old = (datetime.datetime.now() - datetime.timedelta(days=100)).strftime("%Y-%m-%d")
        tools = [{"id": "old-stale", "status": "stale", "updated": old, "name": "Old Tool"}]
        self._make_registry(tmp_path, tools)
        monkeypatch.setattr(m, "REGISTRY", tmp_path / "tools-registry.json")
        monkeypatch.setattr(m, "STALE_DAYS", 90)
        result = m.sunset_auto_deprecate(dry_run=False)
        assert result == 1
        saved = json.loads((tmp_path / "tools-registry.json").read_text())
        assert saved["tools"][0]["status"] == "deprecated"
        events = [e for e in saved.get("event_log", []) if e.get("type") == "entropy:auto_deprecated"]
        assert len(events) == 1
        assert events[0]["tool_id"] == "old-stale"

    def test_multiple_stale(self, tmp_path, monkeypatch):
        old = (datetime.datetime.now() - datetime.timedelta(days=100)).strftime("%Y-%m-%d")
        recent = (datetime.datetime.now() - datetime.timedelta(days=10)).strftime("%Y-%m-%d")
        tools = [
            {"id": "expired-stale", "status": "stale", "updated": old},
            {"id": "fresh-stale", "status": "stale", "updated": recent},
        ]
        self._make_registry(tmp_path, tools)
        monkeypatch.setattr(m, "REGISTRY", tmp_path / "tools-registry.json")
        monkeypatch.setattr(m, "STALE_DAYS", 90)
        result = m.sunset_auto_deprecate(dry_run=False)
        assert result == 1  # only one expired
        saved = json.loads((tmp_path / "tools-registry.json").read_text())
        statuses = {t["id"]: t["status"] for t in saved["tools"]}
        assert statuses["expired-stale"] == "deprecated"
        assert statuses["fresh-stale"] == "stale"

    def test_dry_run_does_not_modify(self, tmp_path, monkeypatch):
        old = (datetime.datetime.now() - datetime.timedelta(days=100)).strftime("%Y-%m-%d")
        tools = [{"id": "old-stale", "status": "stale", "updated": old}]
        self._make_registry(tmp_path, tools)
        monkeypatch.setattr(m, "REGISTRY", tmp_path / "tools-registry.json")
        monkeypatch.setattr(m, "STALE_DAYS", 90)
        result = m.sunset_auto_deprecate(dry_run=True)
        assert result == 0  # dry_run doesn't count changes
        saved = json.loads((tmp_path / "tools-registry.json").read_text())
        assert saved["tools"][0]["status"] == "stale"  # unchanged


class TestConverge:
    """测试收敛检查函数。"""

    def test_converge_categories_empty(self, tmp_path, monkeypatch):
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(json.dumps({"tools": []}))
        monkeypatch.setattr(m, "REGISTRY", reg_file)
        m.converge_categories()

    def test_converge_categories_with_data(self, tmp_path, monkeypatch):
        tools = [
            {"id": "t1", "category": ["MCP", "AI"]},
            {"id": "t2", "category": ["AI", "Local"]},
        ]
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(json.dumps({"tools": tools}))
        monkeypatch.setattr(m, "REGISTRY", reg_file)
        m.converge_categories()

    def test_converge_pressure_empty(self, tmp_path, monkeypatch):
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(json.dumps({"tools": []}))
        monkeypatch.setattr(m, "REGISTRY", reg_file)
        m.converge_pressure()

    def test_converge_pressure_with_data(self, tmp_path, monkeypatch):
        tools = [{"id": "t1", "type": "tool"}, {"id": "t2", "type": "skill"}]
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(json.dumps({"tools": tools, "event_log": [{"type": "x"}]}))
        monkeypatch.setattr(m, "REGISTRY", reg_file)
        m.converge_pressure()

    def test_cmd_converge_logs_event(self, tmp_path, monkeypatch):
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(json.dumps({"tools": []}))
        monkeypatch.setattr(m, "REGISTRY", reg_file)
        monkeypatch.setattr(m, "FORGE_ROOT", tmp_path)
        rc = m.cmd_converge([])
        assert rc == 0
        saved = json.loads(reg_file.read_text())
        events = [e for e in saved.get("event_log", []) if e.get("type") == "entropy:converged"]
        assert len(events) == 1


class TestAtomicSave:
    """测试 _atomic_save 原子写入。"""

    def test_saves_correctly(self, tmp_path, monkeypatch):
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(json.dumps({"tools": []}))
        monkeypatch.setattr(m, "REGISTRY", reg_file)
        data = {"tools": [{"id": "new-tool"}]}
        m._atomic_save(data)
        saved = json.loads(reg_file.read_text())
        assert len(saved["tools"]) == 1
        assert saved["tools"][0]["id"] == "new-tool"


class TestCliDispatch:
    """测试 CLI 调度函数。"""

    def test_run_no_args(self, capsys):
        rc = m.run([])
        assert rc == 0
        captured = capsys.readouterr()
        assert "用法" in captured.out

    def test_run_help(self, capsys):
        rc = m.run(["--help"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "用法" in captured.out

    def test_run_unknown_action(self):
        rc = m.run(["unknown"])
        assert rc == 1

    def test_cmd_sunrise_help(self, capsys):
        rc = m.cmd_sunrise(["--help"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "用法" in captured.out

    def test_cmd_sunset_help(self, capsys):
        rc = m.cmd_sunset(["--help"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "用法" in captured.out

    def test_sunrise_list(self, tmp_path, monkeypatch):
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(json.dumps({"tools": []}))
        monkeypatch.setattr(m, "REGISTRY", reg_file)
        monkeypatch.setattr(m, "CANDIDATE_DAYS", 30)
        rc = m.cmd_sunrise(["--list"])
        assert rc == 0

    def test_sunset_list(self, tmp_path, monkeypatch):
        reg_file = tmp_path / "tools-registry.json"
        reg_file.write_text(json.dumps({"tools": []}))
        monkeypatch.setattr(m, "REGISTRY", reg_file)
        rc = m.cmd_sunset(["--list"])
        assert rc == 0
