from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT = WORKSPACE / "bin" / "gac" / "ci-local-fast.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("ci_local_fast", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _command(*, returncode: int = 0, stdout: str = "ok", stderr: str = "") -> tuple[str, ...]:
    source = (
        "import sys; "
        f"print({stdout!r}); "
        f"print({stderr!r}, file=sys.stderr) if {bool(stderr)!r} else None; "
        f"raise SystemExit({returncode})"
    )
    return (sys.executable, "-c", source)


def test_run_check_preserves_producer_exit_code_and_prefixes_both_streams(tmp_path: Path) -> None:
    module = _load_module()
    output = io.StringIO()
    check = module.Check(
        key="gac",
        title="GaC local gate",
        command=_command(returncode=23, stdout="out", stderr="err"),
    )

    returncode = module.run_check(check, cwd=tmp_path, output=output)

    assert returncode == 23
    assert "[gac] out" in output.getvalue()
    assert "[gac] err" in output.getvalue()


@pytest.mark.parametrize("failed_key", ["gac", "hygiene", "ruff", "html", "yaml"])
def test_suite_fails_closed_for_each_blocking_producer(
    failed_key: str, tmp_path: Path
) -> None:
    module = _load_module()
    output = io.StringIO()
    checks = tuple(
        module.Check(
            key=key,
            title=key,
            command=_command(returncode=17 if key == failed_key else 0, stdout=key),
        )
        for key in ("gac", "hygiene", "ruff", "html", "yaml")
    )

    returncode = module.run_suite(checks, cwd=tmp_path, output=output)

    assert returncode == 1
    assert f"❌ {failed_key}: exit 17" in output.getvalue()
    assert "全部 blocking checks 通过" not in output.getvalue()


def test_suite_reports_green_only_when_every_blocking_check_passes(tmp_path: Path) -> None:
    module = _load_module()
    output = io.StringIO()
    checks = (
        module.Check(key="gac", title="gac", command=_command()),
        module.Check(key="yaml", title="yaml", command=_command()),
    )

    returncode = module.run_suite(checks, cwd=tmp_path, output=output)

    assert returncode == 0
    assert output.getvalue().count("✅ ci-local-fast: 全部 blocking checks 通过") == 1


def test_ruff_baseline_allows_known_debt_and_reports_resolved_entries(tmp_path: Path) -> None:
    module = _load_module()
    baseline = {
        ("projects/omo/src/omo/legacy.py", "F541", "f-string without any placeholders"): 2,
        ("projects/omo/src/omo/fixed.py", "E741", "Ambiguous variable name: `l`"): 1,
    }
    diagnostics = [
        {
            "filename": str(tmp_path / "projects/omo/src/omo/legacy.py"),
            "code": "F541",
            "message": "f-string without any placeholders",
        }
    ]

    comparison = module.compare_ruff_diagnostics(diagnostics, baseline, root=tmp_path)

    assert comparison.new == {}
    assert comparison.known == {
        ("projects/omo/src/omo/legacy.py", "F541", "f-string without any placeholders"): 1
    }
    assert comparison.resolved == {
        ("projects/omo/src/omo/legacy.py", "F541", "f-string without any placeholders"): 1,
        ("projects/omo/src/omo/fixed.py", "E741", "Ambiguous variable name: `l`"): 1,
    }


def test_ruff_baseline_rejects_new_diagnostic(tmp_path: Path) -> None:
    module = _load_module()
    diagnostic = {
        "filename": str(tmp_path / "projects/omo/src/omo/new.py"),
        "code": "F821",
        "message": "Undefined name `missing`",
    }

    comparison = module.compare_ruff_diagnostics([diagnostic], {}, root=tmp_path)

    assert comparison.new == {
        ("projects/omo/src/omo/new.py", "F821", "Undefined name `missing`"): 1
    }
    assert comparison.known == {}
    assert comparison.resolved == {}


def test_ruff_baseline_cannot_grow_beyond_hard_cap(tmp_path: Path) -> None:
    module = _load_module()
    baseline_path = tmp_path / "ruff.yaml"
    baseline_path.write_text(
        """\
version: 1
policy:
  growth_policy: forbidden
  hard_cap: 26
  captured_diagnostic_count: 27
diagnostics:
  - path: projects/omo/src/omo/legacy.py
    code: F541
    message: f-string without any placeholders
    count: 27
""",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="exceeds hard cap 26"):
        module._load_ruff_baseline(baseline_path)


def test_ruff_baseline_cannot_replace_an_approved_bucket_at_same_cap(tmp_path: Path) -> None:
    module = _load_module()
    payload = yaml.safe_load(module.BASELINE_PATH.read_text(encoding="utf-8"))
    payload["diagnostics"][0]["path"] = "projects/omo/src/omo/replacement.py"
    baseline_path = tmp_path / "ruff.yaml"
    baseline_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(RuntimeError, match="contains unapproved bucket"):
        module._load_ruff_baseline(baseline_path)


def test_make_plan_ignores_ci_local_runner_environment_override() -> None:
    env = os.environ.copy()
    env["CI_LOCAL_RUNNER"] = "true"
    proc = subprocess.run(
        ["make", "--no-print-directory", "--dry-run", "ci-local-fast"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
        env=env,
    )
    combined = proc.stdout + proc.stderr

    assert proc.returncode == 0
    assert "bin/gac/ci-local-fast.py" in combined
    assert "\ntrue\n" not in combined
