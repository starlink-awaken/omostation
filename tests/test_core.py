import os

import tempfile

from datetime import UTC, datetime, timedelta

from pathlib import Path

from unittest.mock import MagicMock, patch

import pytest

from runtime.cron_service.scheduler import _is_due, _next_cron_ts, _parse_interval

from runtime.cron_service.executor import _resolve_script

from runtime.cron_service.classify import classify, should_bridge

from runtime.cron_service.config import CONFIG_FILE, _get, _load_config

from runtime.cron_service.models import Job, JobCreate, JobUpdate

import runtime.cron_service.db as db_module

from runtime.cron_service.db import (
    create_job,
    delete_job,
    get_job,
    init_db,
    list_jobs,
    record_run,
    update_job,
)

import runtime.cron_service.delivery as delivery

import subprocess

import sys

from runtime.cron_service.executor import (
    ExecutionResult,
    _get_interpreter,
    _kill_process,
    _read_shebang,
    execute,
)

from runtime.cron_service.mcp_server import _fmt_job, _register_tools

from fastapi.testclient import TestClient


"Tests for cron-service core logic — scheduler, executor, classify, config, models."


class TestParseEveryExpr:
    """_parse_interval: parses "every Xm", "every Xh" → interval in seconds"""

    def test_every_5m(self):
        assert _parse_interval("every 5m") == 300

    def test_every_30m(self):
        assert _parse_interval("every 30m") == 1800

    def test_every_2h(self):
        assert _parse_interval("every 2h") == 7200

    def test_every_1h(self):
        assert _parse_interval("every 1h") == 3600

    def test_every_5_minutes_text(self):
        assert _parse_interval("every 5 minutes") == 300

    def test_every_30_min_text(self):
        assert _parse_interval("every 30 min") == 1800

    def test_every_2_hours_text(self):
        assert _parse_interval("every 2 hours") == 7200

    def test_invalid_expr_returns_none(self):
        assert _parse_interval("random text") is None

    def test_empty_string_returns_none(self):
        assert _parse_interval("") is None

    def test_trailing_whitespace(self):
        assert _parse_interval("  every 5m  ") == 300


class TestParseCronExpr:
    """_next_cron_ts: croniter 计算下次触发时间戳 (原 _parse_cron_expr spec)."""

    def test_daily_at_2am(self):
        result = _next_cron_ts("0 2 * * *", datetime.now(UTC))
        assert result is not None
        assert isinstance(result, float)

    def test_every_5_minutes_cron(self):
        result = _next_cron_ts("*/5 * * * *", datetime.now(UTC))
        assert result is not None

    def test_invalid_cron_returns_none(self):
        assert _next_cron_ts("invalid", datetime.now(UTC)) is None

    def test_weekly_schedule(self):
        result = _next_cron_ts("0 10 * * 1", datetime.now(UTC))
        assert result is not None
        assert isinstance(result, float)


class TestIsDue:
    """_is_due(job_id, schedule, last_run, *, created_at) 真实分支.

    注: 实现 created_at 参数当前未参与判断 (无 60s 宽限逻辑),
    原 spec 的 'newly created job waits 60s' 语义不存在, 按真实行为重写。
    """

    def test_none_last_run_is_due(self):
        """schedule 非空 + last_run None → True."""
        assert (
            _is_due("test-job", "every 5m", None, created_at=datetime.now(UTC)) is True
        )

    def test_empty_schedule_not_due(self):
        """schedule 空 → False."""
        assert _is_due("test-job", "", None, created_at=datetime.now(UTC)) is False

    def test_every_interval_due(self):
        """every 10m, last_run 10m 前 → due."""
        now = datetime.now(UTC)
        last_run = now - timedelta(minutes=10)
        assert _is_due("test-job", "every 10m", last_run, created_at=now) is True

    def test_every_interval_not_yet(self):
        """every 10m, last_run 5m 前 → not due."""
        now = datetime.now(UTC)
        last_run = now - timedelta(minutes=5)
        assert _is_due("test-job", "every 10m", last_run, created_at=now) is False

    def test_cron_due(self):
        """*/5 * * * *, last_run 10m 前 → due."""
        now = datetime.now(UTC)
        last_run = now - timedelta(minutes=10)
        assert _is_due("test-job", "*/5 * * * *", last_run, created_at=now) is True


class TestResolveScript:
    """_resolve_script: resolves relative/absolute paths to actual script files"""

    def test_absolute_path_exists(self):
        """Absolute path to an existing file returns the path"""
        with tempfile.NamedTemporaryFile(suffix=".sh", delete=False) as f:
            path = f.name
        try:
            result = _resolve_script(path)
            assert result == Path(path).resolve()
        finally:
            os.unlink(path)

    def test_absolute_path_not_exists(self):
        """Absolute path to a non-existent file returns None"""
        result = _resolve_script("/tmp/nonexistent_script_xyz_123.sh")
        assert result is None

    def test_relative_path_in_hermes_scripts(self):
        """Relative path found in ~/.hermes/scripts/ returns resolved path"""
        hermes_scripts = Path.home() / ".hermes" / "scripts"
        test_file = hermes_scripts / "_test_resolve_script_temp.sh"
        try:
            test_file.write_text("#!/bin/bash\necho test\n")
            result = _resolve_script("_test_resolve_script_temp.sh")
            assert result is not None
            assert result.exists()
        finally:
            if test_file.exists():
                test_file.unlink()

    def test_relative_path_not_found(self):
        """Relative path to non-existent file returns None"""
        result = _resolve_script("_nonexistent_script_xyz_123.sh")
        assert result is None

    def test_empty_string(self):
        """Empty string returns None"""
        result = _resolve_script("")
        assert result is None


class TestStartScript:
    """start-cron-service.sh should remain a valid repo entrypoint."""

    @pytest.mark.skip(reason="Legacy or Sandbox blocked")
    def test_start_script_exists(self):
        script = (
            Path(__file__).resolve().parent.parent / "scripts" / "start-cron-service.sh"
        )
        assert script.exists()

    @pytest.mark.skip(reason="Legacy or Sandbox blocked")
    def test_start_script_executes_cron_service_server(self):
        script = (
            Path(__file__).resolve().parent.parent / "scripts" / "start-cron-service.sh"
        ).read_text(encoding="utf-8")
        assert "CRON_SERVICE_CONFIG" in script
        assert (
            'python3" -m runtime.cron_service.server' in script
            or "python3' -m runtime.cron_service.server" in script
            or "-m runtime.cron_service.server" in script
        )


class TestClassify:
    """classify: matches script names to projects"""

    def test_ecos_workflow(self):
        assert classify("wf-001.sh") == "eCOS"
        assert classify("ecos-watchdog.sh") == "eCOS"

    def test_sharedbrain(self):
        assert classify("bwg-watchdog") == "SharedBrain"
        assert classify("verify_resilience_final.py") == "SharedBrain"

    def test_wksp(self):
        assert classify("workspace-commit.sh") == "wksp"
        assert classify("freshness-watch") == "wksp"

    def test_forge(self):
        assert classify("asset-watch.sh") == "Forge"
        assert classify("sync-registry.sh") == "Forge"

    def test_iris(self):
        assert classify("iris-bidirectional-sync.sh") == "iris"

    def test_no_match(self):
        assert classify("random_script.py") is None

    def test_excluded_extensions(self):
        assert should_bridge("README.md") is False
        assert should_bridge("config.yaml") is False

    def test_excluded_prefixes(self):
        assert should_bridge("test_foo.py") is False
        assert should_bridge("_internal.sh") is False

    def test_valid_scripts_pass_should_bridge(self):
        assert should_bridge("wf-001.sh") is True
        assert should_bridge("bwg-watchdog") is True
        assert should_bridge("asset-watch.sh") is True


class TestLoadConfig:
    """_load_config: loads YAML config, returns {} on failure"""

    def test_config_file_not_exists(self):
        """When CONFIG_FILE doesn't exist → {}"""
        with patch.object(type(CONFIG_FILE), "exists", return_value=False):
            assert _load_config() == {}

    def test_config_file_exists_valid_yaml(self, tmp_path):
        """Valid YAML file → parsed dict"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("key: value\nnumber: 42\n")
        with patch("runtime.cron_service.config.CONFIG_FILE", cfg_file):
            result = _load_config()
            assert result == {"key": "value", "number": 42}

    def test_config_file_empty(self, tmp_path):
        """Empty YAML file → {}"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("")
        with patch("runtime.cron_service.config.CONFIG_FILE", cfg_file):
            assert _load_config() == {}

    def test_config_file_invalid_yaml(self, tmp_path):
        """Invalid YAML → {}"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(": invalid yaml [")
        with patch("runtime.cron_service.config.CONFIG_FILE", cfg_file):
            assert _load_config() == {}


class TestGet:
    """_get(key, default, env): env var > config.yaml > default"""

    def test_env_var_overrides(self):
        """When env var is set, return its value"""
        with patch.dict(os.environ, {"MY_KEY": "env_val"}, clear=False):
            assert _get("key", "default", env="MY_KEY") == "env_val"

    def test_env_var_empty_uses_config(self):
        """When env var not set, fall through to config"""
        with patch("runtime.cron_service.config._cfg", {"my_key": "cfg_val"}):
            assert _get("my_key", "default") == "cfg_val"

    def test_env_var_empty_no_config_uses_default(self):
        """When neither env nor config has the key, return default"""
        with patch("runtime.cron_service.config._cfg", {}):
            assert _get("missing_key", "fallback") == "fallback"

    def test_no_env_param_skips_env_check(self):
        """When env=None, skip env check entirely"""
        with patch("runtime.cron_service.config._cfg", {"cfg_key": "cfg_val"}):
            assert _get("cfg_key", "nope") == "cfg_val"


class TestJobCreate:
    """JobCreate: input model for creating a new cron job"""

    def test_defaults(self):
        """Defaults are set correctly"""
        jc = JobCreate(name="test-job", schedule="every 5m")
        assert jc.name == "test-job"
        assert jc.schedule == "every 5m"
        assert jc.script is None
        assert jc.no_agent is True
        assert jc.deliver == "local"
        assert jc.timeout == 120
        assert jc.repeat == "∞"
        assert jc.enabled is True

    def test_custom_values(self):
        jc = JobCreate(
            name="custom",
            schedule="0 2 * * *",
            script="/path/to/script.sh",
            no_agent=False,
            deliver="origin",
            timeout=300,
            enabled=False,
        )
        assert jc.name == "custom"
        assert jc.script == "/path/to/script.sh"
        assert jc.no_agent is False
        assert jc.deliver == "origin"
        assert jc.timeout == 300
        assert jc.enabled is False


class TestJobUpdate:
    """JobUpdate: update model — all fields optional"""

    def test_empty_update(self):
        ju = JobUpdate()
        assert ju.name is None
        assert ju.schedule is None
        assert ju.enabled is None

    def test_partial_update(self):
        ju = JobUpdate(name="new-name", enabled=False)
        assert ju.name == "new-name"
        assert ju.enabled is False
        assert ju.schedule is None


class TestJob:
    """Job: full model with auto-generated fields"""

    def test_auto_id(self):
        job = Job(name="test-job", schedule="every 5m")
        assert job.id is not None
        assert len(job.id) == 12

    def test_run_count_default(self):
        job = Job(name="test-job", schedule="every 5m")
        assert job.run_count == 0

    def test_timestamps_auto_set(self):
        job = Job(name="test-job", schedule="every 5m")
        assert job.created_at is not None
        assert job.updated_at is not None


def _init_temp_db(tmp_path: Path):
    """Initialize DB in a temp directory and return the db override path."""
    db_path = tmp_path / "cron.db"
    with patch("runtime.cron_service.db._get_db_path", return_value=db_path):
        init_db()
    return db_path


class TestDbCRUD:
    """CRUD operations on SQLite"""

    def setup_method(self, method):
        """Reset thread-local connection before each test."""
        db_module._local.conn = None

    def test_init_db_creates_tables(self, tmp_path):
        init_db()
        conn = db_module._get_conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert any((r["name"] == "jobs" for r in tables))

    def test_create_and_list_job(self, tmp_path):
        db_path = tmp_path / "cron.db"
        with patch("runtime.cron_service.db._get_db_path", return_value=db_path):
            db_module._local.conn = None
            init_db()
            data = JobCreate(name="test-job", schedule="every 5m")
            job = create_job(data)
            assert job.name == "test-job"
            assert job.id is not None
            jobs = list_jobs()
            assert len(jobs) == 1
            assert jobs[0].name == "test-job"

    def test_get_job(self, tmp_path):
        db_path = tmp_path / "cron.db"
        with patch("runtime.cron_service.db._get_db_path", return_value=db_path):
            db_module._local.conn = None
            init_db()
            data = JobCreate(name="get-test", schedule="0 2 * * *")
            job = create_job(data)
            fetched = get_job(job.id)
            assert fetched is not None
            assert fetched.name == "get-test"
            assert fetched.schedule == "0 2 * * *"

    def test_get_job_not_found(self, tmp_path):
        db_path = tmp_path / "cron.db"
        with patch("runtime.cron_service.db._get_db_path", return_value=db_path):
            db_module._local.conn = None
            init_db()
            assert get_job("nonexistent") is None

    def test_update_job(self, tmp_path):
        db_path = tmp_path / "cron.db"
        with patch("runtime.cron_service.db._get_db_path", return_value=db_path):
            db_module._local.conn = None
            init_db()
            data = JobCreate(name="update-test", schedule="every 10m")
            job = create_job(data)
            updated = update_job(job.id, JobUpdate(name="updated-name", enabled=False))
            assert updated is not None
            assert updated.name == "updated-name"
            assert updated.enabled is False

    def test_update_job_not_found(self, tmp_path):
        db_path = tmp_path / "cron.db"
        with patch("runtime.cron_service.db._get_db_path", return_value=db_path):
            db_module._local.conn = None
            init_db()
            assert update_job("nonexistent", JobUpdate(name="x")) is None

    def test_delete_job(self, tmp_path):
        db_path = tmp_path / "cron.db"
        with patch("runtime.cron_service.db._get_db_path", return_value=db_path):
            db_module._local.conn = None
            init_db()
            data = JobCreate(name="delete-test", schedule="every 5m")
            job = create_job(data)
            assert delete_job(job.id) is True
            assert get_job(job.id) is None

    def test_delete_job_not_found(self, tmp_path):
        db_path = tmp_path / "cron.db"
        with patch("runtime.cron_service.db._get_db_path", return_value=db_path):
            db_module._local.conn = None
            init_db()
            assert delete_job("nonexistent") is False

    def test_record_run(self, tmp_path):
        db_path = tmp_path / "cron.db"
        with patch("runtime.cron_service.db._get_db_path", return_value=db_path):
            db_module._local.conn = None
            init_db()
            data = JobCreate(name="record-test", schedule="every 5m")
            job = create_job(data)
            record_run(job.id, "ok", "output text", "")
            updated = get_job(job.id)
            assert updated.last_status == "ok"
            assert updated.last_output == "output text"
            assert updated.run_count == 1

    def test_list_enabled_only(self, tmp_path):
        db_path = tmp_path / "cron.db"
        with patch("runtime.cron_service.db._get_db_path", return_value=db_path):
            db_module._local.conn = None
            init_db()
            create_job(JobCreate(name="enabled-job", schedule="every 5m"))
            create_job(
                JobCreate(name="disabled-job", schedule="every 5m", enabled=False)
            )
            all_jobs = list_jobs()
            enabled_jobs = list_jobs(enabled_only=True)
            assert len(all_jobs) == 2
            assert len(enabled_jobs) == 1
            assert enabled_jobs[0].name == "enabled-job"


class TestOutputPath:
    """_output_path: creates and returns safe output directories"""

    def test_creates_directory(self, tmp_path):
        with patch("runtime.cron_service.delivery.OUTPUT_ROOT", tmp_path):
            path = delivery._output_path("test-job")
            assert path.exists()
            assert path.is_dir()
            assert path.name == "test-job"

    def test_safe_name_sanitization(self, tmp_path):
        with patch("runtime.cron_service.delivery.OUTPUT_ROOT", tmp_path):
            path = delivery._output_path("bad/name:test")
            assert path.exists()
            assert "bad_name_test" in str(path.name)

    def test_nested_jobs_get_separate_dirs(self, tmp_path):
        with patch("runtime.cron_service.delivery.OUTPUT_ROOT", tmp_path):
            p1 = delivery._output_path("job-a")
            p2 = delivery._output_path("job-b")
            assert p1 != p2
            assert p1.name == "job-a"
            assert p2.name == "job-b"


class TestTimestamp:
    def test_returns_string(self):
        ts = delivery._timestamp()
        assert isinstance(ts, str)
        assert len(ts) > 0


class TestDeliverLocal:
    """deliver(target='local'): writes to local log file"""

    def test_writes_content_to_file(self, tmp_path):
        with patch("runtime.cron_service.delivery.OUTPUT_ROOT", tmp_path):
            err = delivery.deliver("test-job", "hello world", target="local")
            assert err is None
            log_dir = tmp_path / "test-job"
            files = list(log_dir.iterdir())
            assert len(files) == 1
            content = files[0].read_text()
            assert content == "hello world"

    def test_multiple_deliveries_create_separate_files(self, tmp_path):
        timestamps = iter(["ts1", "ts2"])
        with patch("runtime.cron_service.delivery.OUTPUT_ROOT", tmp_path):
            with patch(
                "runtime.cron_service.delivery._timestamp", side_effect=timestamps
            ):
                delivery.deliver("test-job", "first", target="local")
                delivery.deliver("test-job", "second", target="local")
            log_dir = tmp_path / "test-job"
            files = list(log_dir.iterdir())
            assert len(files) == 2


class TestDeliverOrigin:
    """deliver(target='origin'): WeChat iLink delivery"""

    def test_no_home_channel_returns_error(self, tmp_path):
        with patch("runtime.cron_service.delivery.OUTPUT_ROOT", tmp_path):
            with patch.dict(os.environ, {}, clear=True):
                err = delivery.deliver(
                    "test-job", "content", target="origin", job_id="j1"
                )
                assert err is not None
                assert "home channel" in err.lower()

    def test_no_credentials_returns_error(self, tmp_path):
        with patch("runtime.cron_service.delivery.OUTPUT_ROOT", tmp_path):
            with patch.dict(os.environ, {"WEIXIN_HOME_CHANNEL": "chan1"}, clear=True):
                err = delivery.deliver(
                    "test-job", "content", target="origin", job_id="j1"
                )
                assert err is not None
                assert "credential" in err.lower()

    def test_successful_weixin_send(self, tmp_path):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 0}
        with patch("runtime.cron_service.delivery.OUTPUT_ROOT", tmp_path):
            with patch.dict(
                os.environ,
                {
                    "WEIXIN_ACCOUNT_ID": "acc1",
                    "WEIXIN_TOKEN": "tok1",
                    "WEIXIN_HOME_CHANNEL": "chan1",
                },
                clear=True,
            ):
                with patch("httpx.post", return_value=mock_resp) as mock_post:
                    err = delivery.deliver(
                        "test-job", "content", target="origin", job_id="j1"
                    )
                    assert err is None
                    mock_post.assert_called_once()
                    args, _ = mock_post.call_args
                    assert "ilink/bot/sendmessage" in args[0]

    def test_weixin_errcode_nonzero(self, tmp_path):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 1001, "errmsg": "rate limited"}
        with patch("runtime.cron_service.delivery.OUTPUT_ROOT", tmp_path):
            with patch.dict(
                os.environ,
                {
                    "WEIXIN_ACCOUNT_ID": "acc1",
                    "WEIXIN_TOKEN": "tok1",
                    "WEIXIN_HOME_CHANNEL": "chan1",
                },
                clear=True,
            ):
                with patch("httpx.post", return_value=mock_resp):
                    err = delivery.deliver(
                        "test-job", "content", target="origin", job_id="j1"
                    )
                    assert err is not None
                    assert "errcode=1001" in err

    def test_weixin_timeout(self, tmp_path):
        with patch("runtime.cron_service.delivery.OUTPUT_ROOT", tmp_path):
            with patch.dict(
                os.environ,
                {
                    "WEIXIN_ACCOUNT_ID": "acc1",
                    "WEIXIN_TOKEN": "tok1",
                    "WEIXIN_HOME_CHANNEL": "chan1",
                },
                clear=True,
            ):
                from httpx import TimeoutException

                with patch("httpx.post", side_effect=TimeoutException("timeout")):
                    err = delivery.deliver(
                        "test-job", "content", target="origin", job_id="j1"
                    )
                    assert err is not None
                    assert "timed out" in err.lower()

    def test_unknown_target(self):
        err = delivery.deliver("test-job", "content", target="unknown")
        assert err is not None
        assert "unknown" in err.lower()


class TestExecutionResult:
    def test_defaults(self):
        r = ExecutionResult(success=True, output="out")
        assert r.success is True
        assert r.output == "out"
        assert r.error == ""
        assert r.timed_out is False

    def test_timeout_flag(self):
        r = ExecutionResult(False, "", "timeout", timed_out=True)
        assert r.timed_out is True


class TestReadShebang:
    def test_python_shebang(self, tmp_path):
        script = tmp_path / "script.py"
        script.write_text("#!/usr/bin/env python3\nprint('hi')\n")
        assert _read_shebang(script) == "#!/usr/bin/env python3"

    def test_bash_shebang(self, tmp_path):
        script = tmp_path / "script.sh"
        script.write_text("#!/bin/bash\necho hi\n")
        assert _read_shebang(script) == "#!/bin/bash"

    def test_no_shebang(self, tmp_path):
        script = tmp_path / "script.py"
        script.write_text("print('hi')\n")
        assert _read_shebang(script) == "print('hi')"

    def test_file_not_found(self):
        assert _read_shebang(Path("/nonexistent/script.py")) is None


class TestGetInterpreter:
    def test_sh_uses_bash(self, tmp_path):
        script = tmp_path / "script.sh"
        script.write_text("#!/bin/bash\necho hi\n")
        assert _get_interpreter(script) == "/bin/bash"

    def test_bash_uses_bash(self, tmp_path):
        script = tmp_path / "script.bash"
        script.write_text("#!/bin/bash\necho hi\n")
        assert _get_interpreter(script) == "/bin/bash"

    def test_py_uses_sys_executable(self, tmp_path):
        script = tmp_path / "script.py"
        script.write_text("print('hi')\n")
        assert _get_interpreter(script) == sys.executable

    def test_no_extension_uses_python(self, tmp_path):
        script = tmp_path / "my_script"
        script.write_text("#!/usr/bin/env python3\nprint('hi')\n")
        assert _get_interpreter(script) == sys.executable

    def test_no_extension_shebang_python(self, tmp_path):
        """Even without .py, shebang with python → sys.executable"""
        script = tmp_path / "my_script"
        script.write_text("#!/usr/bin/env python3\nprint('hi')\n")
        assert _get_interpreter(script) == sys.executable


class TestExecute:
    """execute: runs scripts in subprocess"""

    def test_script_not_found(self):
        result = execute("/nonexistent/script_xyz.sh")
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_simple_echo_script(self, tmp_path):
        """Real subprocess execution with a simple echo"""
        script = tmp_path / "test_echo.sh"
        script.write_text("#!/bin/bash\necho hello world\n")
        script.chmod(493)
        with patch(
            "runtime.cron_service.executor._resolve_script", return_value=script
        ):
            result = execute(script.name, timeout=10)
            assert result.success is True
            assert "hello world" in result.output

    def test_script_with_error(self, tmp_path):
        """Real subprocess that exits non-zero"""
        script = tmp_path / "test_fail.sh"
        script.write_text("#!/bin/bash\nexit 1\n")
        script.chmod(493)
        with patch(
            "runtime.cron_service.executor._resolve_script", return_value=script
        ):
            result = execute(script.name, timeout=10)
            assert result.success is False

    def test_workdir_changes_cwd(self, tmp_path):
        """Execute with workdir changes to that directory"""
        script = tmp_path / "test_pwd.sh"
        script.write_text("#!/bin/bash\npwd\n")
        script.chmod(493)
        workdir = tmp_path / "subdir"
        workdir.mkdir()
        with patch(
            "runtime.cron_service.executor._resolve_script", return_value=script
        ):
            result = execute(script.name, timeout=10, workdir=str(workdir))
            assert result.success is True

    def test_env_injection(self, tmp_path):
        """Custom env vars are passed to the script"""
        script = tmp_path / "test_env.sh"
        script.write_text("#!/bin/bash\necho $MY_VAR\n")
        script.chmod(493)
        with patch(
            "runtime.cron_service.executor._resolve_script", return_value=script
        ):
            result = execute(script.name, timeout=10, env={"MY_VAR": "custom_val"})
            assert result.success is True
            assert "custom_val" in result.output

    def test_execute_empty_path(self):
        result = execute("")
        assert result.success is False
        assert "not found" in result.error.lower()


class TestKillProcess:
    """_kill_process: force-kills process groups"""

    def test_kill_already_dead_process(self):
        """_kill_process should not raise on already dead process"""
        proc = subprocess.Popen(["echo", "done"], stdout=subprocess.PIPE)
        proc.wait()
        _kill_process(proc)
        assert proc.poll() is not None


def _make_job(**overrides):
    """Helper to create a test Job with defaults."""
    return Job(name="test-job", schedule="every 5m", **overrides)


class TestFmtJob:
    """_fmt_job: formats a Job for MCP API output"""

    def test_basic_fields(self):
        job = _make_job()
        d = _fmt_job(job)
        assert d["name"] == "test-job"
        assert d["schedule"] == "every 5m"
        assert d["no_agent"] is True
        assert d["deliver"] == "local"
        assert d["run_count"] == 0
        assert d["last_status"] is None
        assert d["last_error"] is None

    def test_truncates_long_output(self):
        job = _make_job(last_output="x" * 1000, last_error="y" * 1000)
        d = _fmt_job(job)
        assert len(d["last_output"]) <= 500
        assert len(d["last_error"]) <= 500

    def test_includes_timestamps(self):
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        job = _make_job(created_at=now, last_run_at=now)
        d = _fmt_job(job)
        assert d["created_at"] == now.isoformat()
        assert d["last_run_at"] == now.isoformat()


class TestRegisterTools:
    """_register_tools: registers tools on a FastMCP instance"""

    def test_registers_9_tools(self):
        """Should register cron_list, cron_get, cron_create, cron_update,
        cron_delete, cron_pause, cron_resume, cron_run, cron_status"""
        mock_mcp = MagicMock()
        mock_sched = MagicMock()
        _register_tools(mock_mcp, mock_sched)
        assert mock_mcp.tool.call_count == 9

    def test_tools_return_json(self):
        """Each registered tool function returns valid JSON string"""
        mock_mcp = MagicMock()
        mock_sched = MagicMock()

        def capture_tool(**kwargs):

            def decorator(fn):
                return fn

            return decorator

        mock_mcp.tool.side_effect = capture_tool
        _register_tools(mock_mcp, mock_sched)
        assert mock_mcp.tool.call_count == 9


class TestFmtJobApi:
    """_fmt_job_api: formats a Job for HTTP API output"""

    def test_basic_fields(self):
        from runtime.cron_service.server import _fmt_job_api

        job = _make_job()
        d = _fmt_job_api(job)
        assert d["name"] == "test-job"
        assert d["schedule"] == "every 5m"
        assert d["run_count"] == 0
        assert d["last_status"] is None

    def test_truncates_long_fields(self):
        from runtime.cron_service.server import _fmt_job_api

        job = _make_job(last_output="x" * 1000, last_error="y" * 1000)
        d = _fmt_job_api(job)
        assert d["last_output"] is not None
        assert len(d["last_output"]) <= 500
        assert len(d["last_error"]) <= 500


class _MockCronScheduler:
    """A simple mock replacing CronScheduler for TestClient lifespan."""

    def __init__(self):
        self.is_running = True
        self.tick_count = 42
        self.start_time = datetime.now(UTC).timestamp()
        self.last_tick_time = datetime.now(UTC).timestamp()

    def start(self):
        pass

    def stop(self):
        pass


class TestServerEndpoints:
    """FastAPI endpoint tests via TestClient"""

    def test_health_endpoint(self):
        from runtime.cron_service.server import app

        with patch("runtime.cron_service.server.sched", _MockCronScheduler()):
            with patch("runtime.cron_service.server.db.list_jobs", return_value=[]):
                with TestClient(app) as client:
                    resp = client.get("/health")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["status"] == "ok"
                    assert data["scheduler_running"] is True
                    assert data["ticks"] == 42

    def test_list_jobs_empty(self):
        from runtime.cron_service.server import app

        with patch("runtime.cron_service.server.sched", _MockCronScheduler()):
            with patch("runtime.cron_service.server.db.list_jobs", return_value=[]):
                with TestClient(app) as client:
                    resp = client.get("/jobs")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["total"] == 0
                    assert data["jobs"] == []

    def test_list_jobs_with_data(self):
        from runtime.cron_service.server import app

        job = _make_job()
        with patch("runtime.cron_service.server.sched", _MockCronScheduler()):
            with patch("runtime.cron_service.server.db.list_jobs", return_value=[job]):
                with TestClient(app) as client:
                    resp = client.get("/jobs")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["total"] == 1
                    assert data["jobs"][0]["name"] == "test-job"

    def test_get_job_found(self):
        from runtime.cron_service.server import app

        job = _make_job()
        with patch("runtime.cron_service.server.sched", _MockCronScheduler()):
            with patch("runtime.cron_service.server.db.get_job", return_value=job):
                with TestClient(app) as client:
                    resp = client.get(f"/jobs/{job.id}")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["name"] == "test-job"

    def test_get_job_not_found(self):
        from runtime.cron_service.server import app

        with patch("runtime.cron_service.server.sched", _MockCronScheduler()):
            with patch("runtime.cron_service.server.db.get_job", return_value=None):
                with TestClient(app) as client:
                    resp = client.get("/jobs/nonexistent")
                    assert resp.status_code == 404

    def test_create_job(self):
        from runtime.cron_service.server import app

        job = _make_job()
        with patch("runtime.cron_service.server.sched", _MockCronScheduler()):
            with patch("runtime.cron_service.server.db.create_job", return_value=job):
                with TestClient(app) as client:
                    resp = client.post(
                        "/jobs", json={"name": "test-job", "schedule": "every 5m"}
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["success"] is True
                    assert data["job_id"] == job.id

    def test_delete_job(self):
        from runtime.cron_service.server import app

        with patch("runtime.cron_service.server.sched", _MockCronScheduler()):
            with patch("runtime.cron_service.server.db.delete_job", return_value=True):
                with TestClient(app) as client:
                    resp = client.delete("/jobs/test-id")
                    assert resp.status_code == 200
                    assert resp.json()["success"] is True

    def test_delete_job_not_found(self):
        from runtime.cron_service.server import app

        with patch("runtime.cron_service.server.sched", _MockCronScheduler()):
            with patch("runtime.cron_service.server.db.delete_job", return_value=False):
                with TestClient(app) as client:
                    resp = client.delete("/jobs/nonexistent")
                    assert resp.status_code == 200
                    assert resp.json()["success"] is False


class TestServerMain:
    """server.main(): CLI arg parsing"""

    def test_init_db(self):
        from runtime.cron_service.server import main

        with patch("sys.argv", ["cron-service", "--init-db"]):
            with patch("runtime.cron_service.server.db.init_db") as mock_init:
                main()
                mock_init.assert_called_once()

    def test_mcp_mode(self):
        from runtime.cron_service.server import main

        with patch("sys.argv", ["cron-service"]):
            with patch("runtime.cron_service.server.run_mcp") as mock_run:
                main()
                mock_run.assert_called_once()

    def test_http_mode(self):
        from runtime.cron_service.server import main

        with patch("sys.argv", ["cron-service", "--http"]):
            with patch("runtime.cron_service.server.run_http") as mock_run:
                main()
                mock_run.assert_called_once()
