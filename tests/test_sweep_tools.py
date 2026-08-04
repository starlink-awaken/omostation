from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYRIGHT_SCRIPT = ROOT / "bin" / "sweep" / "pyright.py"
NESTED_WITH_SCRIPT = ROOT / "bin" / "sweep" / "nested-with.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def diagnostic(path: Path, line: int, rule: str) -> dict:
    return {
        "severity": "error",
        "file": str(path),
        "rule": rule,
        "range": {"start": {"line": line}},
    }


def run_pyright(report: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PYRIGHT_SCRIPT), str(report), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_pyright_line_suppression_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "src" / "sample.py"
    source.parent.mkdir()
    source.write_text("value = missing\n")
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"generalDiagnostics": [diagnostic(source, 0, "reportUndefinedVariable")]}))

    first = run_pyright(report)
    rendered = source.read_text()
    second = run_pyright(report)

    assert first.returncode == 0
    assert rendered == "value = missing  # type: ignore[reportUndefinedVariable]\n"
    assert source.read_text() == rendered
    assert "line_suppressions=0" in second.stdout


def test_pyright_dry_run_reports_without_editing(tmp_path: Path) -> None:
    source = tmp_path / "src" / "sample.py"
    source.parent.mkdir()
    source.write_text("value = missing\n")
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"generalDiagnostics": [diagnostic(source, 0, "reportUndefinedVariable")]}))

    result = run_pyright(report, "--dry-run")

    assert result.returncode == 0
    assert source.read_text() == "value = missing\n"
    assert "files=1" in result.stdout
    assert "line_suppressions=1" in result.stdout


def test_pyright_test_header_threshold_and_metrics(tmp_path: Path) -> None:
    source = tmp_path / "tests" / "test_sample.py"
    source.parent.mkdir()
    source.write_text("first = missing\nsecond = missing\nthird = missing\n")
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "generalDiagnostics": [
                    diagnostic(source, 0, "reportUndefinedVariable"),
                    diagnostic(source, 1, "reportUndefinedVariable"),
                    diagnostic(source, 2, "reportUndefinedVariable"),
                ]
            }
        )
    )

    result = run_pyright(report)

    assert result.returncode == 0
    assert source.read_text().startswith("# pyright: reportUndefinedVariable=false\n\n")
    assert "file_suppressions=1" in result.stdout
    assert "suppression_ratio=1.000" in result.stdout


def test_pyright_package_filter_limits_edits(tmp_path: Path) -> None:
    selected = tmp_path / "projects" / "selected" / "sample.py"
    skipped = tmp_path / "projects" / "skipped" / "sample.py"
    selected.parent.mkdir(parents=True)
    skipped.parent.mkdir(parents=True)
    selected.write_text("value = missing\n")
    skipped.write_text("value = missing\n")
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "generalDiagnostics": [
                    diagnostic(selected, 0, "reportUndefinedVariable"),
                    diagnostic(skipped, 0, "reportUndefinedVariable"),
                ]
            }
        )
    )

    result = run_pyright(report, "--package", "selected")

    assert result.returncode == 0
    assert "type: ignore" in selected.read_text()
    assert skipped.read_text() == "value = missing\n"


def test_nested_with_merges_simple_contexts_and_is_idempotent() -> None:
    module = load_module(NESTED_WITH_SCRIPT, "nested_with_for_test")
    source = "with first():\n    with second():\n        value = 1\nprint(value)\n"

    rendered, merged = module.merge(source)
    second_rendered, second_merged = module.merge(rendered)

    assert rendered == "with first(), second():\n    value = 1\nprint(value)\n"
    assert merged == 1
    assert second_rendered == rendered
    assert second_merged == 0


def test_nested_with_rejects_multiline_header() -> None:
    module = load_module(NESTED_WITH_SCRIPT, "nested_with_multiline_test")
    source = "with (\n    first(),\n):\n    with second():\n        value = 1\n"

    rendered, merged = module.merge(source)

    assert rendered == source
    assert merged == 0
