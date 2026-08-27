import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "check-submodule-rewind.py"


def run_check(args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if args:
        cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


class TestBasicFunctionality:
    def test_current_main_passes(self):
        result = run_check()
        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_json_output(self):
        result = run_check(["--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["violations"] == []

    def test_verbose_output(self):
        result = run_check(["--verbose"])
        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_json_schema(self):
        result = run_check(["--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "ok" in data
        assert "violations" in data
        assert "details" in data
        assert isinstance(data["violations"], list)
        assert isinstance(data["details"], list)

    def test_json_has_warns_and_counts(self):
        result = run_check(["--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "warns" in data
        assert "tolerance_counts" in data
        assert isinstance(data["warns"], list)
        assert isinstance(data["tolerance_counts"], dict)

    def test_warn_threshold_flag(self):
        result = run_check(["--warn-threshold", "999"])
        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_tolerance_layer_regression(self):
        import importlib.util
        import inspect

        spec = importlib.util.spec_from_file_location(
            "check_submodule_rewind",
            REPO_ROOT / "bin" / "gac" / "check-submodule-rewind.py",
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        params = list(inspect.signature(mod.is_descendant_or_equal).parameters.keys())
        assert params[0] == "descendant_candidate"
        assert params[1] == "ancestor_candidate"


class TestGetPreviousPointer:
    """get_previous_pointer must return the submodule gitlink pointer value at the
    last commit that touched the path — NOT the main-repo commit SHA.

    Regression: the old implementation returned `git log -1 --format=%H -- <path>`
    (the main-repo commit SHA), which never exists in the submodule's object store.
    That forced is_descendant_or_equal into the sha-missing tolerance layer and
    masked every real rewind.
    """

    def _load_module(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "check_submodule_rewind",
            REPO_ROOT / "bin" / "gac" / "check-submodule-rewind.py",
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        return mod

    def _last_touching_commit(self, path: str) -> str:
        out = subprocess.run(
            ["git", "log", "--first-parent", "-1", "--format=%H", "--", path],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        ).stdout.strip()
        assert out, f"no commit touches {path}"
        return out

    def _gitlink_at(self, commit: str, path: str) -> str:
        out = subprocess.run(
            ["git", "ls-tree", commit, "--", path],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        ).stdout.strip()
        # format: 160000 commit <sha>\t<path>
        parts = out.split()
        assert len(parts) >= 3 and parts[0] == "160000" and parts[1] == "commit", (
            f"expected gitlink line, got: {out!r}"
        )
        return parts[2]

    def test_returns_gitlink_pointer_not_commit_sha(self):
        mod = self._load_module()
        path = "projects/ecos"
        commit = self._last_touching_commit(path)
        expected_pointer = self._gitlink_at(commit, path)

        result = mod.get_previous_pointer(path)

        assert result is not None
        # The returned value MUST be the gitlink pointer, not the main-repo commit SHA.
        assert result == expected_pointer, (
            f"get_previous_pointer returned {result!r} but expected gitlink pointer "
            f"{expected_pointer!r} at commit {commit}"
        )
        assert result != commit, (
            f"get_previous_pointer returned the main-repo commit SHA {result!r}; "
            "it must return the submodule pointer value instead"
        )

    def test_returns_40_hex_sha(self):
        import re

        mod = self._load_module()
        result = mod.get_previous_pointer("projects/ecos")
        assert result is not None
        assert re.fullmatch(r"[0-9a-f]{40}", result), f"not a 40-hex SHA: {result!r}"


class TestToleranceLayerDetection:
    """Verify tolerance layer reasons are populated in JSON output."""

    def test_details_have_reason_field(self):
        result = run_check(["--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        for detail in data["details"]:
            assert "reason" in detail
            assert detail["reason"] != ""

    def test_valid_reasons_are_known(self):
        KNOWN_REASONS = {
            "same-commit",
            "sha-missing",
            "default-branch",
            "any-ref",
            "force-pushed-away",
            "feature-branch",
            "detached-head-tip",
            "rewind-or-unrelated",
        }
        result = run_check(["--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        for detail in data["details"]:
            reason_prefix = detail["reason"].split(":")[0]
            assert reason_prefix in KNOWN_REASONS, f"Unknown reason: {detail['reason']}"
