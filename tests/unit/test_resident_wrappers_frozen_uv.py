"""Guard resident launchd wrappers against mutating tracked projects/omo/uv.lock."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

RESIDENT_WRAPPERS = (
    "lib/resident-role-tick.sh",
    "lib/resident-event-ingest.sh",
)

_UV_RUN_RE = re.compile(r"\buv\s+run\b")
_FROZEN_FLAG_RE = re.compile(r"(?:^|\s)--frozen(?:\s|$)")


def _repo_root() -> Path:
    """Resolve the active repository root via bin/lib/repo_root.py."""
    spec = importlib.util.spec_from_file_location(
        "resident_wrappers_repo_root",
        Path(__file__).resolve().parents[2] / "bin/lib/repo_root.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.code_root()


def _logical_command_lines(text: str) -> list[tuple[int, str]]:
    """Join trailing-backslash continuations for non-comment shell commands."""
    commands: list[tuple[int, str]] = []
    start_line: int | None = None
    buf: list[str] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not buf and (not stripped or stripped.startswith("#")):
            continue
        if start_line is None:
            start_line = lineno
        continued = stripped.endswith("\\")
        part = stripped[:-1].rstrip() if continued else stripped
        if part:
            buf.append(part)
        if not continued:
            commands.append((start_line, " ".join(buf)))
            start_line = None
            buf = []
    if buf and start_line is not None:
        commands.append((start_line, " ".join(buf)))
    return commands


def _find_unfrozen_uv_run_lines(text: str) -> list[tuple[int, str]]:
    """Return (start_lineno, command) for any `uv run` invocation missing --frozen."""
    hits: list[tuple[int, str]] = []
    for lineno, cmd in _logical_command_lines(text):
        if _UV_RUN_RE.search(cmd) and not _FROZEN_FLAG_RE.search(cmd):
            hits.append((lineno, cmd))
    return hits


def test_resident_wrappers_are_syntax_valid() -> None:
    root = _repo_root()
    for rel in RESIDENT_WRAPPERS:
        proc = subprocess.run(
            ["bash", "-n", str(root / rel)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"{rel}: {proc.stderr}"


def test_resident_wrappers_pass_frozen_on_every_uv_run_line() -> None:
    root = _repo_root()
    for rel in RESIDENT_WRAPPERS:
        text = (root / rel).read_text(encoding="utf-8")
        commands = _logical_command_lines(text)
        uv_commands = [(ln, cmd) for ln, cmd in commands if _UV_RUN_RE.search(cmd)]
        assert uv_commands, f"{rel} has no uv run invocation"
        unfrozen = _find_unfrozen_uv_run_lines(text)
        assert unfrozen == [], f"{rel} invokes `uv run` without --frozen: {unfrozen}"


def test_unfrozen_uv_run_detector_catches_synthetic_regression() -> None:
    """Anti-baseline: the pre-fix wrapper snippet must trigger the detector."""
    pre_fix_snippet = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'exec /opt/homebrew/bin/uv run --project "$OMO_PROJECT" \\\n'
        "  python -m omo.resident.cli ingest\n"
    )
    hits = _find_unfrozen_uv_run_lines(pre_fix_snippet)
    assert len(hits) == 1, f"expected synthetic unfrozen uv run to fail, got {hits}"
    assert hits[0][0] == 3

    fixed_snippet = pre_fix_snippet.replace("uv run --project", "uv run --frozen --project")
    assert _find_unfrozen_uv_run_lines(fixed_snippet) == []


def test_resident_wrappers_self_derive_repo_root() -> None:
    root = _repo_root()
    for rel in RESIDENT_WRAPPERS:
        text = (root / rel).read_text(encoding="utf-8")
        lines = text.splitlines()
        assert any(ln.strip().startswith("_SELF_DIR=") for ln in lines), f"{rel} missing _SELF_DIR="
        assert any(ln.strip().startswith("_REPO_ROOT=") for ln in lines), f"{rel} missing _REPO_ROOT="
        assert any(
            "$_REPO_ROOT" in ln and not ln.strip().startswith(("_SELF_DIR=", "_REPO_ROOT="))
            for ln in lines
        ), f"{rel} does not consume $_REPO_ROOT"
        assert "/Users/" not in text, f"{rel} must not hardcode a /Users/ path"
