import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]


def _run_validate_human_gate(*args: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            "uv",
            "run",
            "--with",
            "pyyaml",
            "python",
            str(WORKSPACE / "bin/gac/validate-human-gate.py"),
            *args,
        ],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_merge_event_is_prohibited():
    """merge_event 应被识别为 prohibited source"""
    result = _run_validate_human_gate(
        "--scene-card",
        str(WORKSPACE / "docs/scene-cards/engineering-delivery-dogfood.yaml"),
    )
    assert result.returncode == 1, result.stderr
    report = json.loads(result.stdout)
    assert report["prohibited_count"] >= 1
    assert any("merge_event" in item["source"] for item in report["prohibited_sources"])


def test_manual_adjudication_is_allowed():
    """场景卡中 manual_adjudication 不应被标记为 prohibited"""
    result = _run_validate_human_gate(
        "--scene-card",
        str(WORKSPACE / "docs/scene-cards/engineering-delivery-dogfood.yaml"),
    )
    report = json.loads(result.stdout)
    assert report["prohibited_count"] >= 1
    assert not any(item["source"] == "manual_adjudication" for item in report["prohibited_sources"])
