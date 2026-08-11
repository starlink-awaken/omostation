"""Run the local pre-push checks without losing producer exit codes.

The former Make recipe piped every producer through ``sed`` under ``/bin/sh``.
POSIX pipelines report the final command's status, so a failing producer looked
green whenever ``sed`` succeeded.  This runner owns prefixing and failure
aggregation directly and keeps the broad Ruff inventory as explicit debt while
blocking diagnostics beyond the reviewed baseline.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

WORKSPACE = Path(__file__).resolve().parents[2]
BASELINE_PATH = WORKSPACE / ".omo/_truth/registry/ruff-diagnostics-baseline.yaml"
RuffKey = tuple[str, str, str]
RUFF_BASELINE_MAXIMA: dict[RuffKey, int] = {
    ("projects/omo/src/omo/omo_compass.py", "F541", "f-string without any placeholders"): 17,
    ("projects/omo/src/omo/omo_crystallizer.py", "E741", "Ambiguous variable name: `l`"): 1,
    ("projects/omo/src/omo/omo_crystallizer.py", "F541", "f-string without any placeholders"): 2,
    ("projects/omo/src/omo/omo_project_inspector.py", "F541", "f-string without any placeholders"): 4,
    ("projects/omo/src/omo/scenewatcher.py", "E741", "Ambiguous variable name: `l`"): 1,
    ("projects/omo/src/omo/scenewatcher.py", "F541", "f-string without any placeholders"): 1,
}
RUFF_BASELINE_CAP = sum(RUFF_BASELINE_MAXIMA.values())


@dataclass(frozen=True)
class Check:
    key: str
    title: str
    command: tuple[str, ...]
    blocking: bool = True


@dataclass(frozen=True)
class RuffComparison:
    known: dict[RuffKey, int]
    new: dict[RuffKey, int]
    resolved: dict[RuffKey, int]


def run_check(check: Check, *, cwd: Path, output: TextIO) -> int:
    """Run one producer, prefix combined output, and preserve its return code."""

    output.write(f"── {check.title} {'─' * max(1, 52 - len(check.title))}\n")
    try:
        proc = subprocess.Popen(
            check.command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        output.write(f"[{check.key}] unable to start: {exc}\n")
        return 127

    assert proc.stdout is not None
    output.writelines(f"[{check.key}] {line}" for line in proc.stdout)
    return proc.wait()


def run_suite(checks: tuple[Check, ...], *, cwd: Path, output: TextIO) -> int:
    """Run all checks so one failure cannot hide evidence from later checks."""

    failures: list[tuple[str, int]] = []
    for check in checks:
        returncode = run_check(check, cwd=cwd, output=output)
        output.write("\n")
        if returncode == 0:
            continue
        if check.blocking:
            failures.append((check.key, returncode))
            output.write(f"❌ {check.key}: exit {returncode}\n\n")
        else:
            output.write(
                f"⚠️ {check.key}: DEBT/ADVISORY exit {returncode}; "
                "不计为通过，也不阻断本地提交\n\n"
            )

    if failures:
        summary = ", ".join(f"{key}={returncode}" for key, returncode in failures)
        output.write(f"❌ ci-local-fast: blocking check 失败 ({summary})\n")
        return 1
    output.write("✅ ci-local-fast: 全部 blocking checks 通过\n")
    return 0


def _load_ruff_baseline(path: Path = BASELINE_PATH) -> tuple[dict[str, Any], Counter[RuffKey]]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - Make supplies pyyaml
        raise RuntimeError("pyyaml is required for the Ruff baseline") from exc

    if not path.is_file():
        raise RuntimeError(f"Ruff baseline not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if payload.get("version") != 1 or not isinstance(payload.get("policy"), dict):
        raise RuntimeError(f"invalid Ruff baseline schema: {path}")

    baseline: Counter[RuffKey] = Counter()
    for item in payload.get("diagnostics") or []:
        if not isinstance(item, dict):
            raise TypeError("Ruff baseline diagnostics must be mappings")
        key = (str(item.get("path") or ""), str(item.get("code") or ""), str(item.get("message") or ""))
        count = item.get("count")
        if not all(key) or not isinstance(count, int) or count < 1:
            raise RuntimeError(f"invalid Ruff baseline diagnostic: {item!r}")
        baseline[key] += count
    policy = payload["policy"]
    if policy.get("growth_policy") != "forbidden":
        raise RuntimeError("Ruff baseline growth_policy must be forbidden")
    if policy.get("hard_cap") != RUFF_BASELINE_CAP:
        raise RuntimeError(f"Ruff baseline hard_cap must remain {RUFF_BASELINE_CAP}")
    if policy.get("captured_diagnostic_count") != sum(baseline.values()):
        raise RuntimeError("Ruff baseline captured_diagnostic_count does not match diagnostics")
    if sum(baseline.values()) > RUFF_BASELINE_CAP:
        raise RuntimeError(
            f"Ruff baseline exceeds hard cap {RUFF_BASELINE_CAP}: {sum(baseline.values())}"
        )
    for key, count in baseline.items():
        maximum = RUFF_BASELINE_MAXIMA.get(key)
        if maximum is None:
            raise RuntimeError(f"Ruff baseline contains unapproved bucket: {key!r}")
        if count > maximum:
            raise RuntimeError(
                f"Ruff baseline bucket exceeds approved maximum {maximum}: {key!r}={count}"
            )
    return policy, baseline


def _diagnostic_counts(diagnostics: list[dict[str, Any]], *, root: Path) -> Counter[RuffKey]:
    counts: Counter[RuffKey] = Counter()
    resolved_root = root.resolve()
    for item in diagnostics:
        filename = Path(str(item.get("filename") or ""))
        absolute = filename if filename.is_absolute() else resolved_root / filename
        try:
            relpath = absolute.resolve().relative_to(resolved_root).as_posix()
        except ValueError as exc:
            raise RuntimeError(f"Ruff diagnostic outside workspace: {filename}") from exc
        key = (relpath, str(item.get("code") or ""), str(item.get("message") or ""))
        if not key[1] or not key[2]:
            raise RuntimeError(f"malformed Ruff diagnostic: {item!r}")
        counts[key] += 1
    return counts


def compare_ruff_diagnostics(
    diagnostics: list[dict[str, Any]], baseline: dict[RuffKey, int], *, root: Path
) -> RuffComparison:
    current = _diagnostic_counts(diagnostics, root=root)
    expected = Counter(baseline)
    keys = set(current) | set(expected)
    known = {key: min(current[key], expected[key]) for key in keys if min(current[key], expected[key])}
    new = {key: current[key] - expected[key] for key in keys if current[key] > expected[key]}
    resolved = {key: expected[key] - current[key] for key in keys if expected[key] > current[key]}
    return RuffComparison(known=known, new=new, resolved=resolved)


def _ruff_json(policy: dict[str, Any], *, root: Path, debt: bool) -> list[dict[str, Any]]:
    scope_key = "debt_scope" if debt else "blocking_scope"
    ignore_key = "debt_ignore" if debt else "ignore"
    scopes = [str(item) for item in policy.get(scope_key) or []]
    if not scopes:
        raise RuntimeError(f"Ruff policy has no {scope_key}")
    missing = [scope for scope in scopes if not (root / scope).exists()]
    if missing:
        raise RuntimeError(f"Ruff scope is not initialized: {', '.join(missing)}")

    command = ["ruff", "check", *scopes]
    selected = [str(item) for item in policy.get("select") or []]
    ignored = [str(item) for item in policy.get(ignore_key) or []]
    if not debt and selected:
        command.extend(("--select", ",".join(selected)))
    if ignored:
        command.extend(("--ignore", ",".join(ignored)))
    command.extend(("--output-format", "json"))
    try:
        proc = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"unable to run Ruff: {exc}") from exc
    if proc.returncode not in {0, 1}:
        raise RuntimeError(f"Ruff execution failed (exit {proc.returncode}): {proc.stderr.strip()}")
    try:
        diagnostics = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ruff returned invalid JSON: {proc.stdout[:200]!r}") from exc
    if not isinstance(diagnostics, list) or not all(isinstance(item, dict) for item in diagnostics):
        raise RuntimeError("Ruff JSON must be a list of diagnostics")
    return diagnostics


def run_ruff_gate(*, root: Path = WORKSPACE, output: TextIO = sys.stdout) -> int:
    try:
        policy, baseline = _load_ruff_baseline()
        diagnostics = _ruff_json(policy, root=root, debt=False)
        comparison = compare_ruff_diagnostics(diagnostics, baseline, root=root)
    except (RuntimeError, TypeError) as exc:
        output.write(f"ERROR: {exc}\n")
        return 2

    known_count = sum(comparison.known.values())
    resolved_count = sum(comparison.resolved.values())
    new_count = sum(comparison.new.values())
    output.write(
        f"Ruff regression gate: known_debt={known_count} resolved={resolved_count} new={new_count}\n"
    )
    output.writelines(f"NEW {path} {code} x{count}: {message}\n" for (path, code, message), count in sorted(comparison.new.items()))
    if resolved_count:
        output.write("INFO: baseline 中已有诊断已消除；后续可收缩 baseline，禁止扩容。\n")
    return 1 if new_count else 0


def run_ruff_debt_report(*, root: Path = WORKSPACE, output: TextIO = sys.stdout) -> int:
    try:
        policy, _ = _load_ruff_baseline()
        diagnostics = _ruff_json(policy, root=root, debt=True)
    except (RuntimeError, TypeError) as exc:
        output.write(f"ERROR: {exc}\n")
        return 2
    counts = Counter(str(item.get("code") or "UNKNOWN") for item in diagnostics)
    top = ", ".join(f"{code}={count}" for code, count in counts.most_common(8))
    output.write(f"Ruff full-scope debt: total={len(diagnostics)} rules={len(counts)} top=[{top}]\n")
    return 1 if diagnostics else 0


def run_html_entity_check(*, root: Path = WORKSPACE, output: TextIO = sys.stdout) -> int:
    projects = root / "projects"
    if not projects.is_dir():
        output.write(f"ERROR: projects directory missing: {projects}\n")
        return 2

    findings: list[str] = []
    excluded_dirs = {".git", ".venv", "node_modules", "tests"}
    for directory, dirnames, filenames in os.walk(projects):
        dirnames[:] = [name for name in dirnames if name not in excluded_dirs]
        for filename in filenames:
            path = Path(directory) / filename
            if path.suffix not in {".py", ".yaml", ".yml"} or filename.startswith("test_"):
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError as exc:
                output.write(f"ERROR: cannot read {path}: {exc}\n")
                return 2
            for line_number, line in enumerate(lines, start=1):
                if ("&gt;" in line or "&lt;" in line) and "replace(" not in line:
                    findings.append(f"{path.relative_to(root)}:{line_number}:{line.strip()}")

    if findings:
        output.write("发现 HTML 实体编码泄漏 (&gt; / &lt;)，请替换为 > / <\n")
        output.writelines(f"{finding}\n" for finding in findings)
        return 1
    output.write("未发现 HTML 实体编码泄漏\n")
    return 0


def build_checks(*, root: Path = WORKSPACE) -> tuple[Check, ...]:
    python = sys.executable
    script = str(Path(__file__).resolve())
    return (
        Check("gac", "GaC local gate", (python, str(root / "bin/gac/gac-local-gate.py"))),
        Check("hygiene", "dir-hygiene", (python, str(root / "bin/ssot/dir-hygiene-check.py"))),
        Check("ruff", "Ruff regression gate", (python, script, "--ruff-gate")),
        Check("ruff-debt", "Ruff full-scope debt report", (python, script, "--ruff-debt"), blocking=False),
        Check("html", "HTML entity encoding", (python, script, "--html-entities")),
        Check("yaml", "YAML syntax", (python, str(root / "bin/ssot/yaml-validate.py"))),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ruff-gate", action="store_true")
    parser.add_argument("--ruff-debt", action="store_true")
    parser.add_argument("--html-entities", action="store_true")
    args = parser.parse_args(argv)
    if args.ruff_gate:
        return run_ruff_gate()
    if args.ruff_debt:
        return run_ruff_debt_report()
    if args.html_entities:
        return run_html_entity_check()

    print("════════════════════════════════════════════════════")
    print("  ci-local-fast — 本地 CI 预检（真实退出码）")
    print("════════════════════════════════════════════════════")
    return run_suite(build_checks(), cwd=WORKSPACE, output=sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
