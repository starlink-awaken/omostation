"""Forge cron_manager.py 单元测试

测试覆盖:
- 模块导入与结构
- cmd_list, cmd_register, cmd_enable, cmd_disable, cmd_status
- cmd_reminder_add, cmd_reminder_remove
- cmd_cron_script (list/create)
- run() CLI 入口
- 错误路径和边界条件
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


SAMPLE_CRON_ITEMS = [
    {
        "name": "forge-daily-maintenance",
        "schedule": {"Hour": 6, "Minute": 5},
        "script": "maintenance.sh",
        "description": "Daily maintenance",
        "enabled": True,
        "added": "2026-01-01",
    },
    {
        "name": "forge-weekly-report",
        "schedule": "0 9 * * 1",
        "script": "weekly-report.sh",
        "description": "Weekly report",
        "enabled": False,
        "added": "2026-01-01",
    },
]

SAMPLE_REGISTRY_V4 = {
    "version": 4,
    "entities": {
        "cron": {
            "$schema": {},
            "items": SAMPLE_CRON_ITEMS,
        }
    },
}


@pytest.fixture
def setup_registry(monkeypatch, tmp_path):
    """Patch REGISTRY_FILE and related paths to temp files."""
    import cron_manager

    reg_file = tmp_path / "registry.json"
    reg_file.write_text(json.dumps(SAMPLE_REGISTRY_V4))
    monkeypatch.setattr(cron_manager, "REGISTRY_FILE", reg_file)
    monkeypatch.setattr(cron_manager, "FORGE_SCRIPTS", tmp_path / "scripts")
    # Ensure cron_utils paths are also patched
    import cron_utils

    monkeypatch.setattr(cron_utils, "REGISTRY_FILE", reg_file)
    return cron_manager


# ═══════════════════════════════════════════════════
# 1. 模块导入与结构
# ═══════════════════════════════════════════════════


class TestImports:
    def test_module_imports(self):
        import cron_manager

        assert hasattr(cron_manager, "run")
        assert hasattr(cron_manager, "cmd_list")
        assert hasattr(cron_manager, "cmd_register")
        assert hasattr(cron_manager, "cmd_enable")
        assert hasattr(cron_manager, "cmd_disable")
        assert hasattr(cron_manager, "cmd_status")
        assert hasattr(cron_manager, "cmd_reminder_add")
        assert hasattr(cron_manager, "cmd_reminder_remove")
        assert hasattr(cron_manager, "cmd_cron_script")

    def test_run_is_callable(self):
        import cron_manager

        assert callable(cron_manager.run)


# ═══════════════════════════════════════════════════
# 2. cmd_list
# ═══════════════════════════════════════════════════


class TestCmdList:
    def test_list_with_items(self, setup_registry):
        cm = setup_registry
        with patch("cron_manager.launchctl_is_loaded", return_value=True):
            rc = cm.cmd_list([])
        assert rc == 0

    def test_list_empty(self, setup_registry, monkeypatch, tmp_path):
        cm = setup_registry
        reg = {"version": 4, "entities": {"cron": {"items": []}}}
        reg_file = tmp_path / "registry.json"
        reg_file.write_text(json.dumps(reg))
        monkeypatch.setattr(cm, "REGISTRY_FILE", reg_file)
        import cron_utils

        monkeypatch.setattr(cron_utils, "REGISTRY_FILE", reg_file)

        rc = cm.cmd_list([])
        assert rc == 0


# ═══════════════════════════════════════════════════
# 3. cmd_register
# ═══════════════════════════════════════════════════


class TestCmdRegister:
    def test_register_new(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_register(
            [
                "my-new-task",
                "--schedule",
                '{"Hour":8,"Minute":0}',
                "--script",
                "my-script.sh",
                "--desc",
                "A new task",
                "--working-dir",
                "/tmp",
            ]
        )
        assert rc == 0
        reg = cm.load_registry()
        items = cm.get_cron_items(reg)
        names = [i["name"] for i in items]
        assert "my-new-task" in names

    def test_register_update_existing(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_register(
            ["forge-daily-maintenance", "--schedule", '{"Hour":7,"Minute":0}', "--script", "new-script.sh"]
        )
        assert rc == 0
        reg = cm.load_registry()
        items = cm.get_cron_items(reg)
        maint = [i for i in items if i["name"] == "forge-daily-maintenance"][0]
        assert maint["schedule"]["Hour"] == 7
        assert maint["script"] == "new-script.sh"

    def test_register_no_args(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_register([])
        assert rc == 1

    def test_register_invalid_name(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_register(["bad name!!!"])
        assert rc == 1

    def test_register_invalid_script_name(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_register(["good-name", "--script", "evil space.sh"])
        assert rc == 1

    def test_register_unknown_option(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_register(["good-name", "--bogus", "value"])
        assert rc == 1


# ═══════════════════════════════════════════════════
# 4. cmd_enable
# ═══════════════════════════════════════════════════


class TestCmdEnable:
    def test_enable_existing(self, setup_registry):
        cm = setup_registry
        with patch("cron_manager.launchctl_bootstrap", return_value=(True, "已加载")):
            with patch("cron_manager.plist_path"):
                with patch("cron_manager.disabled_plist_path"):
                    rc = cm.cmd_enable(["forge-weekly-report"])
        assert rc == 0
        reg = cm.load_registry()
        items = cm.get_cron_items(reg)
        report = [i for i in items if i["name"] == "forge-weekly-report"][0]
        assert report["enabled"] is True

    def test_enable_nonexistent(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_enable(["nonexistent-task"])
        assert rc == 1

    def test_enable_invalid_name(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_enable(["invalid name!"])
        assert rc == 1

    def test_enable_no_args(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_enable([])
        assert rc == 1


# ═══════════════════════════════════════════════════
# 5. cmd_disable
# ═══════════════════════════════════════════════════


class TestCmdDisable:
    def test_disable_existing(self, setup_registry):
        cm = setup_registry
        with patch("cron_manager.launchctl_bootout", return_value=(True, "已卸载")):
            with patch("cron_manager.plist_path"):
                with patch("cron_manager.disabled_plist_path"):
                    rc = cm.cmd_disable(["forge-daily-maintenance"])
        assert rc == 0
        reg = cm.load_registry()
        items = cm.get_cron_items(reg)
        maint = [i for i in items if i["name"] == "forge-daily-maintenance"][0]
        assert maint["enabled"] is False

    def test_disable_nonexistent_still_ok(self, setup_registry):
        """Disabling a non-existent task should succeed (it tries direct unload)."""
        cm = setup_registry
        with patch("cron_manager.launchctl_bootout", return_value=(True, "已卸载")):
            with patch("cron_manager.plist_path"):
                with patch("cron_manager.disabled_plist_path"):
                    rc = cm.cmd_disable(["nonexistent-task"])
        assert rc == 0

    def test_disable_no_args(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_disable([])
        assert rc == 1


# ═══════════════════════════════════════════════════
# 6. cmd_status
# ═══════════════════════════════════════════════════


class TestCmdStatus:
    def test_status_all(self, setup_registry):
        cm = setup_registry
        with patch("cron_manager.launchctl_is_loaded", return_value=True):
            rc = cm.cmd_status([])
        assert rc == 0

    def test_status_single(self, setup_registry):
        cm = setup_registry
        with patch("cron_manager.launchctl_is_loaded", return_value=True):
            rc = cm.cmd_status(["forge-daily-maintenance"])
        assert rc == 0

    def test_status_nonexistent(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_status(["nonexistent-task"])
        assert rc == 1


# ═══════════════════════════════════════════════════
# 7. cmd_reminder_add / cmd_reminder_remove
# ═══════════════════════════════════════════════════


class TestCmdReminder:
    def test_reminder_add_no_args(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_reminder_add([])
        assert rc == 1

    def test_reminder_add_short_args(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_reminder_add(["task-name"])
        assert rc == 1

    def test_reminder_add_osascript_success(self, setup_registry):
        cm = setup_registry
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            rc = cm.cmd_reminder_add(
                ["my-reminder", "--title", "Do it", "--body", "Remember to do this", "--schedule", "每周五 9:00"]
            )
        assert rc == 0

    def test_reminder_add_osascript_failure(self, setup_registry):
        cm = setup_registry
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "error"
            mock_run.return_value = mock_result
            rc = cm.cmd_reminder_add(["my-reminder", "--title", "Do it", "--schedule", "每周五 9:00"])
        assert rc == 1

    def test_reminder_remove_no_args(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_reminder_remove([])
        assert rc == 1

    def test_reminder_remove_success(self, setup_registry):
        cm = setup_registry
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            rc = cm.cmd_reminder_remove(["test-keyword"])
        assert rc == 0

    def test_reminder_remove_exception(self, setup_registry):
        cm = setup_registry
        with patch("subprocess.run", side_effect=Exception("osascript failed")):
            rc = cm.cmd_reminder_remove(["test-keyword"])
        assert rc == 1


# ═══════════════════════════════════════════════════
# 8. cmd_cron_script
# ═══════════════════════════════════════════════════


class TestCmdCronScript:
    def test_script_list(self, setup_registry, tmp_path):
        cm = setup_registry
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "wf-daily.sh").write_text("#!/bin/bash")
        cm.FORGE_SCRIPTS = scripts_dir
        rc = cm.cmd_cron_script(["list"])
        assert rc == 0

    def test_script_create(self, setup_registry, tmp_path):
        cm = setup_registry
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        cm.FORGE_SCRIPTS = scripts_dir
        rc = cm.cmd_cron_script(["create", "wf-test.sh", "echo hello"])
        assert rc == 0
        assert (scripts_dir / "wf-test.sh").exists()
        content = (scripts_dir / "wf-test.sh").read_text()
        assert "echo hello" in content

    def test_script_create_invalid_name(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_cron_script(["create", "invalid name!", "echo x"])
        assert rc == 1

    def test_script_create_no_sh_extension(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_cron_script(["create", "script.py", "print('x')"])
        assert rc == 1

    def test_script_unknown_subcommand(self, setup_registry):
        cm = setup_registry
        rc = cm.cmd_cron_script(["bogus"])
        assert rc == 1


# ═══════════════════════════════════════════════════
# 9. run() CLI 入口
# ═══════════════════════════════════════════════════


class TestRun:
    def test_run_help(self, setup_registry):
        cm = setup_registry
        rc = cm.run([])
        assert rc == 0

    def test_run_help_flag(self, setup_registry):
        cm = setup_registry
        rc = cm.run(["--help"])
        assert rc == 0

    def test_run_list(self, setup_registry):
        cm = setup_registry
        with patch("cron_manager.launchctl_is_loaded", return_value=True):
            rc = cm.run(["list"])
        assert rc == 0

    def test_run_unknown_command(self, setup_registry):
        cm = setup_registry
        rc = cm.run(["bogus"])
        assert rc == 1

    def test_run_register(self, setup_registry):
        cm = setup_registry
        rc = cm.run(["register", "run-test", "--schedule", "0 0 * * *", "--script", "test.sh"])
        assert rc == 0
