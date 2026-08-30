"""Regression coverage for recoverable runtime quarantine retention."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_quarantine_manifest_is_protected_from_git_cleanup():
    result = subprocess.run(
        ["git", "check-ignore", "-q", "runtime/quarantine/documents-public-runtime-20260829/manifest.json"],
        cwd=ROOT,
        check=False,
    )

    assert result.returncode == 0


def test_runner_log_quarantine_manifest_is_protected_from_git_cleanup():
    result = subprocess.run(
        [
            "git",
            "check-ignore",
            "-q",
            "runtime/quarantine/documents-root-inbox-runner-logs-20260831/manifest.json",
        ],
        cwd=ROOT,
        check=False,
    )

    assert result.returncode == 0
