import json
import subprocess
import sys
from pathlib import Path

import pytest

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
