"""
cron_utils 共享工具库单元测试

测试覆盖:
- validate_task_name —— 任务名正则校验
- validate_script_name —— 脚本路径校验
- validate_working_dir —— 工作目录安全检查
- parse_schedule —— 调度表达式解析
- launchctl_is_loaded —— launchctl 查询
- get_cron_items / find_cron_item —— 注册表字典解析
- 路径辅助函数
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import cron_utils as m


class TestValidateTaskName:
    """测试任务名校验。"""

    def test_letters_and_numbers(self):
        assert m.validate_task_name("hello")
        assert m.validate_task_name("abc123")
        assert m.validate_task_name("TEST")

    def test_with_hyphen_underscore_dot(self):
        assert m.validate_task_name("hello-world")
        assert m.validate_task_name("hello.world")
        assert m.validate_task_name("hello_world")
        assert m.validate_task_name("a.b-c_d")

    def test_empty_string(self):
        assert not m.validate_task_name("")

    def test_leading_invalid_char(self):
        assert not m.validate_task_name("-hello")
        assert not m.validate_task_name(".hello")

    def test_contains_space(self):
        assert not m.validate_task_name("hello world")

    def test_contains_special_char(self):
        assert not m.validate_task_name("hello!world")
        assert not m.validate_task_name("hello@world")
        assert not m.validate_task_name("hello#world")


class TestValidateScriptName:
    """测试脚本名称校验。"""

    def test_simple_script(self):
        assert m.validate_script_name("script.sh")
        assert m.validate_script_name("script.py")

    def test_with_path(self):
        assert m.validate_script_name("path/to/script.sh")
        assert m.validate_script_name("a/b/script.py")
        assert m.validate_script_name("tools/deploy.sh")

    def test_empty_returns_true(self):
        assert m.validate_script_name("") is True

    def test_absolute_path_rejected(self):
        assert not m.validate_script_name("/etc/script.sh")
        assert not m.validate_script_name("/usr/local/bin/script.py")

    def test_invalid_extension(self):
        assert not m.validate_script_name("script.txt")
        assert not m.validate_script_name("script.exe")
        assert not m.validate_script_name("script.md")

    def test_no_extension(self):
        assert not m.validate_script_name("script")

    def test_name_with_dots(self):
        assert m.validate_script_name("test.utils.sh")
        assert m.validate_script_name("my.script.py")


class TestValidateWorkingDir:
    """测试工作目录安全校验。"""

    def test_empty_path(self):
        assert not m.validate_working_dir("")
        assert not m.validate_working_dir("  ")

    def test_shell_metacharacters(self):
        for ch in ";|&`$(){}<>":
            assert not m.validate_working_dir(f"/tmp/foo{ch}bar")

    def test_nonexistent_path(self):
        assert not m.validate_working_dir("/nonexistent_path_for_testing")

    def test_under_home(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        project = home / "myproject"
        project.mkdir()
        monkeypatch.setattr(Path, "home", lambda: home)
        assert m.validate_working_dir(str(project))

    def test_under_root(self, monkeypatch, tmp_path):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        assert m.validate_working_dir("/tmp")

    def test_home_dir_itself(self, monkeypatch, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: home)
        assert m.validate_working_dir(str(home))

    def test_symlinked_path(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        real_dir = tmp_path / "real_data"
        real_dir.mkdir()
        link = home / "link_to_data"
        link.symlink_to(real_dir)
        monkeypatch.setattr(Path, "home", lambda: home)
        assert m.validate_working_dir(str(link))


class TestParseSchedule:
    """测试调度表达式解析。"""

    def test_dict_with_known_keys(self):
        result = m.parse_schedule({"Minute": 30, "Hour": 9})
        assert result == {"Minute": 30, "Hour": 9}

    def test_dict_with_all_keys(self):
        result = m.parse_schedule(
            {
                "Minute": 0,
                "Hour": 6,
                "Day": 1,
                "Weekday": 0,
                "Month": 1,
            }
        )
        assert result == {"Minute": 0, "Hour": 6, "Day": 1, "Weekday": 0, "Month": 1}

    def test_dict_unknown_keys_filtered(self):
        result = m.parse_schedule({"Minute": 15, "unknown": 1})
        assert result == {"Minute": 15}

    def test_dict_empty(self):
        result = m.parse_schedule({})
        assert result == {}

    def test_cron_basic_minute_hour(self):
        result = m.parse_schedule("30 9 * * *")
        assert result == {"Minute": 30, "Hour": 9}

    def test_cron_with_weekday(self):
        result = m.parse_schedule("0 9 * * 1")
        assert result == {"Minute": 0, "Hour": 9, "Weekday": 1}

    def test_cron_all_wildcards(self):
        result = m.parse_schedule("* * * * *")
        assert result is None

    def test_cron_interval_not_supported(self):
        result = m.parse_schedule("*/5 * * * *")
        assert result is None

    def test_cron_list_not_supported(self):
        result = m.parse_schedule("0,30 * * * *")
        assert result is None

    def test_cron_range_not_supported(self):
        result = m.parse_schedule("0 9 * * 1-5")
        # range '1-5' fails int() → Weekday dropped
        assert result == {"Minute": 0, "Hour": 9}

    def test_cron_too_few_parts(self):
        assert m.parse_schedule("*") is None
        assert m.parse_schedule("") is None

    def test_non_string_non_dict(self):
        assert m.parse_schedule(None) is None
        assert m.parse_schedule(123) is None
        assert m.parse_schedule([]) is None


class TestScheduleDisplay:
    """测试调度描述文本生成。"""

    def test_dict_display(self):
        result = m.schedule_display({"Minute": 30, "Hour": 9})
        assert "30分" in result
        assert "9时" in result

    def test_dict_with_weekday(self):
        result = m.schedule_display({"Minute": 0, "Hour": 8, "Weekday": 1})
        assert "0分" in result
        assert "8时" in result
        assert "周一" in result

    def test_cron_string_display(self):
        result = m.schedule_display("30 9 * * *")
        assert "9时" in result
        assert "30分" in result

    def test_cron_interval_display(self):
        result = m.schedule_display("*/5 * * * *")
        assert "每5分钟" in result

    def test_invalid_cron(self):
        assert m.schedule_display("*") == "*"
        assert m.schedule_display("") == ""

    def test_non_string_non_dict(self):
        assert m.schedule_display(None) == "None"
        assert m.schedule_display(42) == "42"


class TestPathHelpers:
    """测试路径／标签辅助函数。"""

    def test_plist_path(self):
        expected = m.LAUNCH_AGENTS / "local.test-job.plist"
        assert m.plist_path("test-job") == expected

    def test_disabled_plist_path(self):
        expected = m.DISABLED_DIR / "local.test-job.plist"
        assert m.disabled_plist_path("test-job") == expected

    def test_plist_label(self):
        assert m.plist_label("test-job") == "local.test-job"

    def test_log_file(self):
        expected = str(m.LOG_DIR / "test-job.log")
        assert m.log_file("test-job") == expected

    def test_err_file(self):
        expected = str(m.LOG_DIR / "test-job.err")
        assert m.err_file("test-job") == expected


class TestLaunchctlIsLoaded:
    """测试 launchctl 状态查询（mock subprocess）。"""

    def test_loaded(self, monkeypatch):
        def mock_run(*args, **kwargs):
            return type("Result", (), {"returncode": 0})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        assert m.launchctl_is_loaded("test-job") is True

    def test_not_loaded(self, monkeypatch):
        def mock_run(*args, **kwargs):
            return type("Result", (), {"returncode": 1})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        assert m.launchctl_is_loaded("test-job") is False

    def test_exception_returns_false(self, monkeypatch):
        def mock_run(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(subprocess, "run", mock_run)
        assert m.launchctl_is_loaded("test-job") is False


class TestLaunchctlBootstrap:
    """测试 launchctl bootstrap（mock subprocess）。"""

    def test_bootstrap_success(self, monkeypatch):
        def mock_run(*args, **kwargs):
            return type("Result", (), {"returncode": 0, "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = m.launchctl_bootstrap("test-job")
        assert ok is True
        assert "已加载" in msg

    def test_bootstrap_already_loaded(self, monkeypatch):
        def mock_run(*args, **kwargs):
            return type("Result", (), {"returncode": 36, "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = m.launchctl_bootstrap("test-job")
        assert ok is True
        assert "之前已存在" in msg

    def test_bootstrap_plist_missing(self, monkeypatch):
        def mock_run(*args, **kwargs):
            return type("Result", (), {"returncode": 2, "stderr": "No such file"})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = m.launchctl_bootstrap("test-job")
        assert ok is False
        assert "plist 不存在" in msg

    def test_bootstrap_generic_error(self, monkeypatch):
        def mock_run(*args, **kwargs):
            return type("Result", (), {"returncode": 1, "stderr": "some error"})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = m.launchctl_bootstrap("test-job")
        assert ok is False
        assert "some error" in msg


class TestLaunchctlBootout:
    """测试 launchctl bootout（mock subprocess）。"""

    def test_bootout_success(self, monkeypatch):
        def mock_run(*args, **kwargs):
            return type("Result", (), {"returncode": 0, "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = m.launchctl_bootout("test-job")
        assert ok is True
        assert "已卸载" in msg

    def test_bootout_already_unloaded(self, monkeypatch):
        def mock_run(*args, **kwargs):
            return type("Result", (), {"returncode": 36, "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = m.launchctl_bootout("test-job")
        assert ok is True
        assert "未加载" in msg


class TestCronItems:
    """测试注册表 cron 条目解析。"""

    SAMPLE_REG = {
        "version": 4,
        "entities": {
            "cron": {
                "items": [
                    {"name": "job-alpha", "schedule": "0 6 * * *"},
                    {"name": "job-beta", "schedule": "30 9 * * 1"},
                ],
            },
        },
    }

    def test_get_cron_items_v4(self):
        items = m.get_cron_items(self.SAMPLE_REG)
        assert len(items) == 2
        assert items[0]["name"] == "job-alpha"
        assert items[1]["name"] == "job-beta"

    def test_get_cron_items_wrong_version(self):
        assert m.get_cron_items({"version": 3}) == []

    def test_get_cron_items_missing_version(self):
        assert m.get_cron_items({}) == []

    def test_get_cron_items_missing_entities(self):
        assert m.get_cron_items({"version": 4}) == []

    def test_find_cron_item_found(self):
        items = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        assert m.find_cron_item(items, "b") == 1
        assert m.find_cron_item(items, "a") == 0

    def test_find_cron_item_not_found(self):
        assert m.find_cron_item([{"name": "x"}], "y") is None

    def test_find_cron_item_empty(self):
        assert m.find_cron_item([], "x") is None


class TestGeneratePlistXml:
    """测试 plist XML 生成。"""

    def test_basic_plist(self):
        xml = m.generate_plist_xml(
            name="test-job",
            script_cmd="/bin/echo hello",
            working_dir=None,
            schedule=None,
        )
        assert isinstance(xml, bytes)
        assert b"local.test-job" in xml
        assert b"ProgramArguments" in xml
        assert b"RunAtLoad" in xml

    def test_plist_with_schedule(self):
        xml = m.generate_plist_xml(
            name="daily-job",
            script_cmd="/bin/true",
            working_dir=None,
            schedule="0 6 * * *",
        )
        assert b"StartCalendarInterval" in xml
        assert b"Minute" in xml

    def test_plist_with_working_dir(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        project = home / "myapp"
        project.mkdir()
        monkeypatch.setattr(Path, "home", lambda: home)
        xml = m.generate_plist_xml(
            name="app-job",
            script_cmd="/bin/true",
            working_dir=str(project),
            schedule=None,
        )
        assert b"WorkingDirectory" in xml

    def test_plist_invalid_working_dir_raises(self):
        with pytest.raises(ValueError, match="不安全的工作目录"):
            m.generate_plist_xml(
                name="bad-job",
                script_cmd="/bin/true",
                working_dir="/nonexistent_bad_path",
                schedule=None,
            )

    def test_plist_with_description(self):
        xml = m.generate_plist_xml(
            name="desc-job",
            script_cmd="/bin/true",
            working_dir=None,
            schedule=None,
            description="My test job description",
        )
        assert b"Description" in xml
        assert b"My test job description" in xml

    def test_plist_description_truncated(self):
        long_desc = "X" * 500
        xml = m.generate_plist_xml(
            name="long-desc",
            script_cmd="/bin/true",
            working_dir=None,
            schedule=None,
            description=long_desc,
        )
        assert b"Description" in xml
        # Should be truncated to 255
        assert len(long_desc) > 255
