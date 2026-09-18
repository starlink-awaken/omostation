#!/usr/bin/env python3
"""Hardening tests for bin/gac/agent-clone.py (HIGH-1/HIGH-2 + MEDIUMs).

Stdlib + pytest only. Covers:

* HIGH-1: git()/git_isolated()/git_authority() always pass timeout= to
  subprocess.run; TimeoutExpired maps to ToolError("git_timeout"); budgets
  are parameterizable via AGENT_CLONE_GIT_{LOCAL,NETWORK}_TIMEOUT.
* HIGH-2: atomic_publish_no_replace error branches via mocked ctypes.CDLL
  (EEXIST/ENOTEMPTY -> destination_collision, generic errno ->
  atomic_publish_failed, missing symbols / win32 ->
  atomic_publish_unsupported).
* MEDIUM: pwd guard + deferred account_home() with Path.home fallback;
  tomllib-first extract_uv_path_dependencies with fallback matrix;
  reinstall_path_dependencies per-package timeout + partial failure;
  degraded-reinstall-does-not-block-ready decision via a real CLI create.
"""

from __future__ import annotations

import errno
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

BIN_PATH = Path(__file__).resolve().parent.parent / "bin" / "gac" / "agent-clone.py"


def _load():
    spec = importlib.util.spec_from_file_location("agent_clone_hardening", BIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


agent_clone = _load()


def _completed(args=None):
    return subprocess.CompletedProcess(args or ["git"], 0, "ok\n", "")


# ---------------------------------------------------------------------------
# HIGH-1: bounded git invocations
# ---------------------------------------------------------------------------


class TestGitTimeoutThreading:
    def test_git_passes_local_timeout_by_default(self):
        seen = {}

        def fake_run(cmd, **kwargs):
            seen.update(kwargs)
            return _completed(cmd)

        with patch.object(subprocess, "run", side_effect=fake_run):
            proc = agent_clone.git(None, "version")
        assert proc.returncode == 0
        assert seen["timeout"] == agent_clone.GIT_TIMEOUT_LOCAL_SECONDS

    def test_git_isolated_passes_local_timeout_by_default(self):
        seen = {}

        def fake_run(cmd, **kwargs):
            seen.update(kwargs)
            return _completed(cmd)

        with patch.object(subprocess, "run", side_effect=fake_run):
            agent_clone.git_isolated("/tmp", "status")
        assert seen["timeout"] == agent_clone.GIT_TIMEOUT_LOCAL_SECONDS

    def test_git_authority_defaults_to_network_timeout(self):
        seen = {}

        def fake_run(cmd, **kwargs):
            seen.update(kwargs)
            return _completed(cmd)

        with patch.object(subprocess, "run", side_effect=fake_run):
            agent_clone.git_authority("ls-remote", "https://example.com/x.git")
        assert seen["timeout"] == agent_clone.GIT_TIMEOUT_NETWORK_SECONDS

    def test_explicit_timeout_overrides_default(self):
        seen = {}

        def fake_run(cmd, **kwargs):
            seen.update(kwargs)
            return _completed(cmd)

        with patch.object(subprocess, "run", side_effect=fake_run):
            agent_clone.git(None, "clone", "https://example.com/x.git", timeout=11.0)
        assert seen["timeout"] == 11.0

    @pytest.mark.parametrize("helper", ["git", "git_isolated", "git_authority"])
    def test_timeout_expired_maps_to_git_timeout(self, helper):
        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))

        with patch.object(subprocess, "run", side_effect=fake_run):
            func = getattr(agent_clone, helper)
            with pytest.raises(agent_clone.ToolError) as caught:
                if helper == "git":
                    func(None, "clone", "https://example.com/x.git")
                elif helper == "git_isolated":
                    func("/tmp", "status")
                else:
                    func("ls-remote", "https://example.com/x.git")
        assert caught.value.reason == "git_timeout"
        assert caught.value.exit_code == agent_clone.EXIT_USAGE
        assert "timeout_seconds" in caught.value.details

    def test_timeout_injection_sleep(self):
        """Stub subprocess.run to sleep past the budget, then raise like the
        real stdlib does when the timeout fires; the helper must convert it."""
        calls = {}

        def sleeping_run(cmd, **kwargs):
            calls["timeout"] = kwargs.get("timeout")
            time.sleep(0.02)  # simulate a hung endpoint, briefly
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))

        with patch.object(subprocess, "run", side_effect=sleeping_run):
            with pytest.raises(agent_clone.ToolError) as caught:
                agent_clone.git(None, "ls-remote", "https://example.com/x.git", timeout=0.01)
        assert caught.value.reason == "git_timeout"
        assert calls["timeout"] == 0.01
        assert caught.value.details["timeout_seconds"] == 0.01

    def test_budgets_parameterizable_via_env(self, monkeypatch):
        monkeypatch.setenv("AGENT_CLONE_GIT_LOCAL_TIMEOUT", "3")
        monkeypatch.setenv("AGENT_CLONE_GIT_NETWORK_TIMEOUT", "7")
        monkeypatch.setenv("AGENT_CLONE_UV_TIMEOUT", "9")
        module = _load()
        assert module.GIT_TIMEOUT_LOCAL_SECONDS == 3.0
        assert module.GIT_TIMEOUT_NETWORK_SECONDS == 7.0
        assert module.UV_REINSTALL_TIMEOUT_SECONDS == 9.0

    def test_invalid_env_falls_back_to_defaults(self, monkeypatch):
        monkeypatch.setenv("AGENT_CLONE_GIT_LOCAL_TIMEOUT", "bogus")
        monkeypatch.setenv("AGENT_CLONE_GIT_NETWORK_TIMEOUT", "-5")
        module = _load()
        assert module.GIT_TIMEOUT_LOCAL_SECONDS == 30.0
        assert module.GIT_TIMEOUT_NETWORK_SECONDS == 60.0

    def test_every_subprocess_run_in_module_carries_timeout(self):
        src = BIN_PATH.read_text(encoding="utf-8")
        missing = []
        start = 0
        while True:
            idx = src.find("subprocess.run(", start)
            if idx == -1:
                break
            window = src[idx : idx + 700]
            if "timeout=" not in window:
                missing.append(src.count("\n", 0, idx) + 1)
            start = idx + 1
        assert missing == [], f"subprocess.run without timeout= near lines {missing}"


# ---------------------------------------------------------------------------
# HIGH-2: atomic publish error branches
# ---------------------------------------------------------------------------


class TestAtomicPublishNoReplace:
    @staticmethod
    def _fake_libc(**attrs):
        fake = MagicMock()
        for key, value in attrs.items():
            setattr(fake, key, value)
        return fake

    def test_darwin_success(self):
        rename = MagicMock(return_value=0)
        fake = self._fake_libc(renamex_np=rename)
        with (
            patch.object(agent_clone.sys, "platform", "darwin"),
            patch("ctypes.CDLL", return_value=fake),
        ):
            assert agent_clone.atomic_publish_no_replace("/src", "/dst") is None
        rename.assert_called_once()

    def test_darwin_eexist_is_collision(self):
        rename = MagicMock(return_value=-1)
        fake = self._fake_libc(renamex_np=rename)
        with (
            patch.object(agent_clone.sys, "platform", "darwin"),
            patch("ctypes.CDLL", return_value=fake),
            patch("ctypes.get_errno", return_value=errno.EEXIST),
        ):
            with pytest.raises(agent_clone.ToolError) as caught:
                agent_clone.atomic_publish_no_replace("/src", "/dst")
        assert caught.value.reason == "destination_collision"

    def test_darwin_enotempty_is_collision(self):
        rename = MagicMock(return_value=-1)
        fake = self._fake_libc(renamex_np=rename)
        with (
            patch.object(agent_clone.sys, "platform", "darwin"),
            patch("ctypes.CDLL", return_value=fake),
            patch("ctypes.get_errno", return_value=errno.ENOTEMPTY),
        ):
            with pytest.raises(agent_clone.ToolError) as caught:
                agent_clone.atomic_publish_no_replace("/src", "/dst")
        assert caught.value.reason == "destination_collision"

    def test_darwin_generic_errno_is_publish_failed(self):
        rename = MagicMock(return_value=-1)
        fake = self._fake_libc(renamex_np=rename)
        with (
            patch.object(agent_clone.sys, "platform", "darwin"),
            patch("ctypes.CDLL", return_value=fake),
            patch("ctypes.get_errno", return_value=errno.EACCES),
        ):
            with pytest.raises(agent_clone.ToolError) as caught:
                agent_clone.atomic_publish_no_replace("/src", "/dst")
        assert caught.value.reason == "atomic_publish_failed"

    def test_darwin_missing_symbol_is_unsupported(self):
        with (
            patch.object(agent_clone.sys, "platform", "darwin"),
            patch("ctypes.CDLL", return_value=object()),
        ):
            with pytest.raises(agent_clone.ToolError) as caught:
                agent_clone.atomic_publish_no_replace("/src", "/dst")
        assert caught.value.reason == "atomic_publish_unsupported"

    def test_linux_success_and_collision(self):
        rename = MagicMock(return_value=0)
        fake = self._fake_libc(renameat2=rename)
        with (
            patch.object(agent_clone.sys, "platform", "linux"),
            patch("ctypes.CDLL", return_value=fake),
        ):
            assert agent_clone.atomic_publish_no_replace("/src", "/dst") is None
        failing = MagicMock(return_value=-1)
        fake_fail = self._fake_libc(renameat2=failing)
        with (
            patch.object(agent_clone.sys, "platform", "linux"),
            patch("ctypes.CDLL", return_value=fake_fail),
            patch("ctypes.get_errno", return_value=errno.EEXIST),
        ):
            with pytest.raises(agent_clone.ToolError) as caught:
                agent_clone.atomic_publish_no_replace("/src", "/dst")
        assert caught.value.reason == "destination_collision"

    def test_windows_is_unsupported_boundary(self):
        """Windows has no atomic no-replace directory rename on this path."""
        with patch.object(agent_clone.sys, "platform", "win32"):
            with pytest.raises(agent_clone.ToolError) as caught:
                agent_clone.atomic_publish_no_replace("C:\\src", "C:\\dst")
        assert caught.value.reason == "atomic_publish_unsupported"


# ---------------------------------------------------------------------------
# MEDIUM: pwd guard + deferred home
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh_home_cache():
    agent_clone._account_home_cache = None
    agent_clone._account_workspace_root_cache = None
    yield
    agent_clone._account_home_cache = None
    agent_clone._account_workspace_root_cache = None


class TestAccountHome:
    def test_import_does_not_require_passwd_entry(self):
        # Module already imported at collection; the guard is that import
        # works even when getpwuid would fail (asserted below via fallback).
        assert hasattr(agent_clone, "account_home")

    def test_getpwuid_failure_falls_back_to_path_home(self, fresh_home_cache, monkeypatch):
        import pwd as real_pwd

        assert real_pwd is not None

        def boom(uid):
            raise KeyError(uid)

        monkeypatch.setattr(agent_clone.pwd, "getpwuid", boom)
        assert agent_clone.account_home() == str(Path.home())

    def test_missing_pwd_module_falls_back(self, fresh_home_cache, monkeypatch):
        monkeypatch.setattr(agent_clone, "pwd", None)
        assert agent_clone.account_home() == str(Path.home())

    def test_workspace_root_derives_from_home(self, fresh_home_cache):
        assert agent_clone.account_workspace_root() == Path(agent_clone.account_home()) / "Workspace"


# ---------------------------------------------------------------------------
# MEDIUM: tomllib-first uv sources parsing
# ---------------------------------------------------------------------------


class TestExtractUvPathDependencies:
    def test_tomllib_handles_compact_quoted_and_non_path_entries(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "demo"\nversion = "0.1.0"\n\n'
            "[tool.uv.sources]\n"
            'ecos={path="../ecos"}\n'
            '"my-pkg" = { path = "../my-pkg", editable = true }\n'
            'requests = ">=2"\n'
            'gitdep = { git = "https://example.com/x.git" }\n',
            encoding="utf-8",
        )
        assert agent_clone.extract_uv_path_dependencies(str(tmp_path)) == ["ecos", "my-pkg"]

    def test_invalid_toml_falls_back_to_text_scan(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.uv.sources]\necos = { path = "../ecos" }\nBROKEN [[[ \n\n[tool.ruff]\nline-length = 100\n',
            encoding="utf-8",
        )
        assert agent_clone.extract_uv_path_dependencies(str(tmp_path)) == ["ecos"]

    def test_missing_tomllib_falls_back_to_text_scan(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.uv.sources]\nagora = { path = "../agora", editable = true }\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(agent_clone, "tomllib", None)
        assert agent_clone.extract_uv_path_dependencies(str(tmp_path)) == ["agora"]

    def test_path_only_filter_excludes_git_specs(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "demo"\nversion = "0.1.0"\n\n'
            "[tool.uv.sources]\n"
            'gitdep = { git = "https://example.com/x.git" }\n',
            encoding="utf-8",
        )
        if agent_clone.tomllib is None:
            pytest.skip("requires tomllib")
        assert agent_clone.extract_uv_path_dependencies(str(tmp_path)) == []


# ---------------------------------------------------------------------------
# MEDIUM: per-package reinstall timeout + partial failure
# ---------------------------------------------------------------------------


class TestReinstallTimeouts:
    @staticmethod
    def _pyproject(tmp_path, names=("ecos", "agora")):
        body = '[project]\nname = "demo"\nversion = "0.1.0"\n\n[tool.uv.sources]\n'
        for name in names:
            body += f'{name} = {{ path = "../{name}" }}\n'
        (tmp_path / "pyproject.toml").write_text(body, encoding="utf-8")

    def test_sync_calls_carry_timeout(self, tmp_path):
        self._pyproject(tmp_path)
        timeouts = []

        def fake_run(cmd, **kwargs):
            timeouts.append(kwargs.get("timeout"))
            return MagicMock(returncode=0, stdout="uv 0.1.0", stderr="")

        with patch.object(subprocess, "run", side_effect=fake_run):
            ok, _ = agent_clone.reinstall_path_dependencies(str(tmp_path))
        assert ok is True
        assert timeouts and all(t == agent_clone.UV_REINSTALL_TIMEOUT_SECONDS for t in timeouts)

    def test_one_package_timeout_does_not_stop_others(self, tmp_path):
        self._pyproject(tmp_path)
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[:2] == ["uv", "--version"]:
                return MagicMock(returncode=0, stdout="uv 0.1.0", stderr="")
            if "ecos" in cmd:
                raise subprocess.TimeoutExpired(cmd, 5.0)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch.object(subprocess, "run", side_effect=fake_run):
            ok, msg = agent_clone.reinstall_path_dependencies(str(tmp_path), timeout=5.0)
        assert ok is False
        assert "ecos" in msg
        assert "timed out" in msg
        # agora was still attempted after ecos timed out
        assert any("agora" in c for c in calls)

    def test_uv_probe_timeout_returns_failure_without_raising(self, tmp_path):
        self._pyproject(tmp_path)

        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 1.0)

        with patch.object(subprocess, "run", side_effect=fake_run):
            ok, msg = agent_clone.reinstall_path_dependencies(str(tmp_path))
        assert ok is False


# ---------------------------------------------------------------------------
# MEDIUM decision: degraded reinstall never blocks ready:True
# ---------------------------------------------------------------------------


def _git(*args, cwd):
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc


class TestDegradedReinstallDecision:
    def test_failed_reinstall_still_publishes_ready_clone(self, tmp_path):
        """End-to-end proof of the recorded decision: uv sync cannot succeed
        (declared path dep points at a missing directory), yet create exits 0
        and the published identity keeps ready:True with degraded status."""
        source = tmp_path / "source"
        source.mkdir()
        assert subprocess.run(["git", "init", "-b", "main"], cwd=str(source), capture_output=True).returncode == 0
        _git("config", "user.name", "D1 Tester", cwd=source)
        _git("config", "user.email", "d1@example.com", cwd=source)
        _git("config", "commit.gpgsign", "false", cwd=source)
        (source / "pyproject.toml").write_text(
            '[project]\nname = "decision-src"\nversion = "0.1.0"\n'
            'dependencies = ["ecos"]\n\n'
            "[tool.uv.sources]\n"
            'ecos = { path = "../does-not-exist-ecos" }\n',
            encoding="utf-8",
        )
        (source / "a.txt").write_text("v1\n", encoding="utf-8")
        _git("add", "a.txt", "pyproject.toml", cwd=source)
        _git("commit", "-m", "initial", cwd=source)

        dest = tmp_path / "clone"
        proc = subprocess.run(
            [
                sys.executable,
                str(BIN_PATH),
                "create",
                "--agent-id",
                "tester1",
                "--delivery-attempt-id",
                "att1",
                "--source",
                str(source),
                "--destination",
                str(dest),
                "--no-submodules",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        identity_file = json.loads(proc.stdout)["identity_file"]
        identity = json.loads(Path(identity_file).read_text(encoding="utf-8"))
        assert identity["ready"] is True
        assert identity["dependency_reinstall_status"] == "degraded"
