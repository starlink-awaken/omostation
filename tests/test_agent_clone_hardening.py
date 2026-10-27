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


AF_PROFILE = "governance-aetherforge"
AF_PATHS = sorted((*agent_clone.GOVERNANCE_SUBMODULES, "projects/aetherforge"))


class NativeProfileFixture:
    """Real Git/native CLI chain; only remote transport and runtime I/O are local.

    No identity/readiness receipts are invented. The fake GitHub endpoint is
    transported to one temporary bare repository for clone/ls-remote/fetch;
    all provenance/config/index/initialized/guard checks use real Git. Runtime
    executables belong to the fixture and never call the host OMO or services.
    """

    def __init__(self, base):
        import shutil

        self.base = base
        self.source = base / "source"
        self.clone = base / "clone"
        self.remote = base / "root.git"
        self.authority = "https://github.com/fixture-owner/fixture-root.git"
        self.real_git = shutil.which("git")
        # Inherit neither shell initialization nor host Git/runtime policy.
        self.env = {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"}
        assert self.real_git is not None, "real Git is required for native fixtures"
        exec_probe = subprocess.run(
            [self.real_git, "--exec-path"], env=self.env,
            capture_output=True, text=True, timeout=20,
        )
        assert exec_probe.returncode == 0, exec_probe.stderr
        exec_path = Path(exec_probe.stdout.strip())
        assert exec_path.is_absolute() and exec_path.is_dir()
        for name in ("git", "git-submodule", "git-submodule--helper", "git-sh-setup"):
            assert (exec_path / name).is_file(), f"Git exec directory lacks {name}"
        self.env["GIT_EXEC_PATH"] = str(exec_path)
        self.env["PATH"] = str(exec_path) + os.pathsep + self.env["PATH"]
        home = base / "home"
        home.mkdir()
        config = base / "gitconfig"
        config.write_text('[user]\n name = Fixture Author\n email = fixture@example.test\n'
                          '[commit]\n gpgsign = false\n[protocol "file"]\n allow = always\n')
        self.env.update({
            "HOME": str(home), "GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_NOSYSTEM": "1",
            "PYTHONDONTWRITEBYTECODE": "1", "AGENT_ID": "fixture-author",
            "OMOSTATION_ROOT": str(self.source), "OMOSTATION_STATE_ROOT": str(base / "state"),
            "WORKSPACE_ROOT": str(self.source), "UV_CACHE_DIR": str(base / "cache"),
            "CLAIMS_AUTHORITY_HERMETIC_UNACTIVATED": "1",
            "XDG_CONFIG_HOME": str(home / "config"), "XDG_DATA_HOME": str(home / "data"),
            "XDG_STATE_HOME": str(home / "state"),
        })
        self.source.mkdir()
        self.git(self.source, "init", "-b", "main")
        (self.source / ".gitignore").write_text(".omo/_delivery/\nruntime/\n")
        (self.source / "README.md").write_text("fixture root\n")
        (self.source / ".githooks").mkdir()
        hook = self.source / ".githooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 0\n")
        hook.chmod(0o755)
        runner = self.source / "bin/gac/managed-python"
        runner.parent.mkdir(parents=True)
        runner.write_text(
            f"#!{sys.executable}\nimport json,os,subprocess,sys\n"
            "if sys.argv[1] == 'probe':\n"
            " p = sys.argv[sys.argv.index('--profile')+1]\n"
            " if os.environ.get('FIXTURE_FAIL_RUNTIME') == p: raise SystemExit(1)\n"
            " print(json.dumps({'schema':'managed-python-runtime-receipt/v1','profile':p}))\n"
            "else:\n"
            " raise SystemExit(subprocess.call([sys.executable,'-B',*sys.argv[sys.argv.index('--')+1:]]))\n"
        )
        runner.chmod(0o755)
        (self.source / "bin/agent-workflow.py").write_text(
            "import json,os\nprint(json.dumps({'ok':not bool(os.environ.get('FIXTURE_FAIL_WORKFLOW'))}))\n"
        )
        self.children = {}
        for name in ["aetherforge", "agora", "cockpit", "ecos", "omo", "sixth"]:
            child = base / f"child-{name}"
            child.mkdir()
            self.git(child, "init", "-b", "main")
            (child / "content.txt").write_text(f"distinct {name}\n")
            self.git(child, "add", "content.txt")
            self.git(child, "commit", "-m", f"initial {name}")
            self.children[f"projects/{name}"] = child
            self.git(self.source, "-c", "protocol.file.allow=always", "submodule", "add",
                     str(child), f"projects/{name}")
        self.git(self.source, "add", ".")
        self.git(self.source, "commit", "-m", "fixture topology")
        self.git(base, "clone", "--bare", str(self.source), str(self.remote))
        # Rewrite only transport invocations. Never rewrite remote/config probes.
        wrapper_dir = base / "transport-bin"
        wrapper_dir.mkdir()
        wrapper = wrapper_dir / "git"
        wrapper.write_text(
            f"#!{sys.executable}\nimport os,sys\n"
            f"real={self.real_git!r}\nauthority={self.authority!r}\n"
            "args=sys.argv[1:]\n"
            "if authority in args and any(v in args for v in ('clone','ls-remote','fetch')):\n"
            f" args=['-c',{('url.' + self.remote.as_uri() + '.insteadOf=' + self.authority)!r},*args]\n"
            "elif any(v.startswith(('https://','ssh://','git@')) for v in args) and any(v in args for v in ('clone','ls-remote','fetch','push')):\n"
            " raise SystemExit('fixture forbids external network')\n"
            "os.execv(real,[real,*args])\n"
        )
        wrapper.chmod(0o755)
        self.env["PATH"] = str(wrapper_dir) + os.pathsep + self.env["PATH"]
        self.counter = 0

    def git(self, cwd, *args, check=True):
        proc = subprocess.run([self.real_git, "-C", str(cwd), *args], env=self.env,
                              capture_output=True, text=True, timeout=20)
        if check:
            assert proc.returncode == 0, proc.stderr
        return proc

    def cli(self, *args, check=True, env=None):
        proc = subprocess.run([sys.executable, "-B", str(BIN_PATH), *map(str, args)],
                              cwd=self.base, env={**self.env, **(env or {})},
                              capture_output=True, text=True, timeout=40)
        if check:
            assert proc.returncode == 0, proc.stderr
        return proc

    def output(self, label):
        self.counter += 1
        return self.base / f"{label}-{self.counter}.json"

    def create(self, profile=AF_PROFILE, custom=False):
        selection = [item for path in AF_PATHS for item in ("--submodule", path)] if custom else ["--profile", profile]
        return self.cli("create", "--agent-id", "fixture-author", "--delivery-attempt-id", "fixture-attempt",
                        "--source", self.authority, "--revision", "refs/heads/main",
                        "--destination", self.clone, *selection, "--json")

    def prepare(self, profile=AF_PROFILE, custom=False):
        self.create(profile, custom)
        if not custom and profile in {AF_PROFILE, "governance", "full"}:
            self.cli("provenance", "--clone", self.clone, "--expected-repository",
                     "fixture-owner/fixture-root", "--output", self.output("provenance"), "--json")
        return self.readiness()

    def readiness(self, *, check=True, env=None):
        manifest = self.output("manifest")
        self.cli("manifest", "--clone", self.clone, "--output", manifest, "--json")
        self.cli("verify", "--clone", self.clone, "--manifest", manifest, "--json")
        return self.cli("readiness", "--clone", self.clone, "--manifest", manifest,
                        "--output", self.output("readiness"), "--json", check=check, env=env)

    def guard(self, *, check=True, env=None):
        return self.cli("guard", "--workspace", self.clone, "--integration-root", self.base / "authority",
                        "--require-clone", "--json", check=check, env=env)

    def initialized(self):
        return sorted(path for path in self.children if (self.clone / path / ".git").exists())

    def identity(self):
        return self.clone / ".git/agent-clone-identity.json"

    def rejected(self, proc, reason=None):
        assert proc.returncode != 0, proc.stdout
        if reason:
            assert reason in proc.stdout + proc.stderr


class TestAetherforgeNativeProfile:
    def test_real_chain_initializes_only_five_and_admits_owned_descendant(self, tmp_path):
        f = NativeProfileFixture(tmp_path)
        result = json.loads(f.prepare().stdout)
        assert result["status"] == "ready"
        assert f.initialized() == AF_PATHS
        assert not (f.clone / "projects/sixth/.git").exists()
        identity = json.loads(f.identity().read_text())
        assert identity["provenance_required"] is True
        assert json.loads(f.guard().stdout)["state"] == "verified_clone"
        (f.clone / "README.md").write_text("owned root descendant\n")
        f.git(f.clone, "add", "README.md")
        f.git(f.clone, "commit", "-m", "owned descendant")
        assert json.loads(f.guard().stdout)["state"] == "verified_clone"

    def test_fresh_extra_initialization_rejected_while_root_clean(self, tmp_path):
        f = NativeProfileFixture(tmp_path)
        f.prepare()
        f.git(f.clone, "-c", "protocol.file.allow=always", "submodule", "update", "--init", "--", "projects/sixth")
        assert f.git(f.clone, "status", "--porcelain").stdout == ""
        f.rejected(f.guard(check=False), "profile_initialization_mismatch")
        f.rejected(f.readiness(check=False), "profile_initialization_mismatch")

    @pytest.mark.parametrize("name", ["aetherforge", "agora", "cockpit", "ecos", "omo"])
    def test_each_child_dirty_rejected(self, tmp_path, name):
        f = NativeProfileFixture(tmp_path)
        f.prepare()
        (f.clone / f"projects/{name}/content.txt").write_text("dirty\n")
        f.rejected(f.guard(check=False))

    def test_af_origin_metadata_drift_rejected_while_root_clean(self, tmp_path):
        f = NativeProfileFixture(tmp_path)
        f.prepare()
        f.git(f.clone / "projects/aetherforge", "remote", "set-url", "origin", str(f.children["projects/sixth"]))
        assert f.git(f.clone, "status", "--porcelain").stdout == ""
        f.rejected(f.guard(check=False), "clone_readiness_mismatch")

    @pytest.mark.parametrize("change", ["missing", "null", "both-markers-missing", "readiness-profile"])
    def test_af_binding_cannot_fall_back_to_legacy(self, tmp_path, change):
        f = NativeProfileFixture(tmp_path)
        f.prepare()
        assert json.loads(f.guard().stdout)["state"] == "verified_clone"
        receipt = f.clone / ".git/agent-clone-readiness.json"
        original_receipt = receipt.read_bytes()
        data = json.loads(f.identity().read_text())
        if change in {"missing", "both-markers-missing"}:
            data.pop("profile")
            if change == "both-markers-missing":
                data.pop("readiness_profile")
        elif change == "null":
            data["profile"] = None
        else:
            data["readiness_profile"] = "governance"
        assert data["provenance_required"] is True
        f.identity().write_text(json.dumps(data))
        assert f.git(f.clone, "status", "--porcelain").stdout == ""
        clean_guard = f.guard(check=False)
        (f.clone / "projects/aetherforge/content.txt").write_text("dirty AF\n")
        dirty_guard = f.guard(check=False)
        assert receipt.read_bytes() == original_receipt
        f.rejected(clean_guard, "clone_readiness_mismatch")
        f.rejected(dirty_guard, "clone_readiness_mismatch")

    @pytest.mark.parametrize("change", ["missing", "head", "index-and-head", "committed-child-pin", "root-dirty", "provenance-flag", "receipt", "actor", "branch", "attempt", "root-origin", "author", "profile"])
    def test_live_drift_is_rejected(self, tmp_path, change):
        f = NativeProfileFixture(tmp_path)
        f.prepare()
        af = f.clone / "projects/aetherforge"
        if change == "missing":
            (af / ".git").rename(af / ".git.hidden")
        elif change in {"head", "index-and-head", "committed-child-pin"}:
            (af / "content.txt").write_text("new AF commit\n")
            f.git(af, "add", "content.txt")
            f.git(af, "commit", "-m", "new child")
            if change in {"index-and-head", "committed-child-pin"}:
                f.git(f.clone, "add", "projects/aetherforge")
            if change == "committed-child-pin":
                f.git(f.clone, "commit", "-m", "changed selected pin")
                assert f.git(f.clone, "status", "--porcelain").stdout == ""
        elif change == "root-dirty":
            (f.clone / "README.md").write_text("dirty root\n")
        elif change in {"provenance-flag", "attempt", "profile"}:
            data = json.loads(f.identity().read_text())
            if change == "provenance-flag":
                data.pop("provenance_required")
                (f.clone / ".git/agent-clone-provenance.json").unlink()
            elif change == "attempt":
                data["delivery_attempt_id"] = "other-attempt"
            else:
                data["profile"] = "governance"
            f.identity().write_text(json.dumps(data))
        elif change == "receipt":
            (f.clone / ".git/agent-clone-readiness.json").write_text("{}")
        elif change == "actor":
            f.rejected(f.guard(check=False, env={"AGENT_ID": "other-author"}))
            return
        elif change == "branch":
            f.git(f.clone, "switch", "-c", "other-branch")
        elif change == "root-origin":
            f.git(f.clone, "remote", "set-url", "--push", "origin", "https://github.com/other/root.git")
        elif change == "author":
            f.git(f.clone, "config", "user.email", "different@example.test")
        f.rejected(f.guard(check=False))

    @pytest.mark.parametrize("seam", ["FIXTURE_FAIL_RUNTIME", "FIXTURE_FAIL_WORKFLOW"])
    def test_required_runtime_readiness_is_not_bypassed(self, tmp_path, seam):
        f = NativeProfileFixture(tmp_path)
        f.create()
        f.cli("provenance", "--clone", f.clone, "--expected-repository", "fixture-owner/fixture-root",
              "--output", f.output("provenance"), "--json")
        proc = f.readiness(check=False, env={seam: "pyyaml" if seam.endswith("RUNTIME") else "1"})
        assert proc.returncode == 0, proc.stderr
        result = json.loads(proc.stdout)
        assert result["status"] == "degraded"
        expected = "managed_python_pyyaml" if seam.endswith("RUNTIME") else "workflow_entrypoint"
        assert result["degraded_checks"] == [expected]
        assert json.loads(f.identity().read_text())["ready"] is False
        f.rejected(f.guard(check=False))

    def test_same_five_custom_remains_readonly(self, tmp_path):
        f = NativeProfileFixture(tmp_path)
        f.create(custom=True)
        assert f.initialized() == AF_PATHS
        proc = f.readiness()
        result = json.loads(proc.stdout)
        assert result["status"] == "degraded"
        assert result["degraded_checks"] == ["writer_admission"]
        assert json.loads(f.identity().read_text())["ready"] is False
        f.rejected(f.guard(check=False), "not eligible")

    @pytest.mark.parametrize("profile", ["governance", "full"])
    def test_legacy_writer_profiles_keep_their_existing_sets(self, tmp_path, profile):
        f = NativeProfileFixture(tmp_path)
        assert json.loads(f.prepare(profile).stdout)["status"] == "ready"
        expected = list(agent_clone.GOVERNANCE_SUBMODULES) if profile == "governance" else sorted(f.children)
        assert f.initialized() == expected
        assert json.loads(f.guard().stdout)["state"] == "verified_clone"

    def test_root_only_remains_readonly_and_initializes_nothing(self, tmp_path):
        f = NativeProfileFixture(tmp_path)
        f.create("root-only")
        assert f.initialized() == []
        proc = f.readiness()
        result = json.loads(proc.stdout)
        assert result["status"] == "degraded"
        assert result["degraded_checks"] == ["writer_admission"]
        assert json.loads(f.identity().read_text())["ready"] is False
        f.rejected(f.guard(check=False), "not eligible")
