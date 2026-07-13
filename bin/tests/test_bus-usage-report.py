"""Tests for bin/bus-usage-report.py — the P74 dormant-adapter detector.

Round 5 follow-up: when bus-usage-report is wired into gac-local-gate,
it MUST be tested so the gate doesn't silently break.

The detector scans projects under a given root for production
bus-foundation calls. We test it end-to-end with a tmp_path fixture
that contains synthetic project trees.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "bin" / "bus-usage-report.py"


def test_no_projects_dir_is_error(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "does not exist" in result.stderr


def test_active_consumer_is_detected(tmp_path: Path) -> None:
    proj = tmp_path / "projects" / "demo-project"
    proj.mkdir(parents=True)
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "demo-project"\ndependencies = ["bus-foundation"]\n'
    )
    src = proj / "src" / "demo_project"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "main.py").write_text(
        "from bus_foundation.facade import event as bus_event\n\n"
        "def publish_something():\n"
        "    bus_event.publish(topic='demo:thing', payload={})\n"
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--json"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"unexpected fail: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["dormant"] == 0
    assert data["active"] >= 1
    demo = next(r for r in data["reports"] if r["project"] == "demo-project")
    assert demo["production_calls"] >= 1


def test_dormant_consumer_is_flagged(tmp_path: Path) -> None:
    proj = tmp_path / "projects" / "lazy-project"
    proj.mkdir(parents=True)
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "lazy-project"\ndependencies = ["bus-foundation"]\n'
    )
    src = proj / "src" / "lazy_project"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "main.py").write_text(
        "# imports bus-foundation but never calls publish/subscribe/emit\n"
        "import bus_foundation\n\n"
        "def helper():\n"
        "    return bus_foundation.__version__\n"
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "DORMANT" in result.stdout or "dormant" in result.stdout.lower()


def test_test_only_usage_does_not_count(tmp_path: Path) -> None:
    proj = tmp_path / "projects" / "test-only-project"
    proj.mkdir(parents=True)
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "test-only-project"\ndependencies = ["bus-foundation"]\n'
    )
    src = proj / "src" / "test_only_project"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("# no bus usage here\n")
    tests = proj / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text(
        "from bus_foundation.facade import event as bus_event\n"
        "bus_event.publish(topic='test:thing', payload={})\n"
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 1


def test_nested_package_layout_is_supported(tmp_path: Path) -> None:
    monorepo = tmp_path / "projects" / "aetherforge" / "packages" / "swarm"
    monorepo.mkdir(parents=True)
    (monorepo / "pyproject.toml").write_text(
        '[project]\nname = "swarm"\ndependencies = ["bus-foundation"]\n'
    )
    src = monorepo / "src" / "swarm"
    src.mkdir(parents=True)
    (src / "_compat.py").write_text(
        "from bus_foundation import publish\n\n"
        "def _bus_publish(topic, payload):\n"
        "    return publish(topic, payload)\n"
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--json"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr={result.stderr!r}"
    data = json.loads(result.stdout)
    projects_found = {r["project"] for r in data["reports"]}
    assert "swarm" in projects_found


def test_bus_foundation_library_itself_is_skipped(tmp_path: Path) -> None:
    bf = tmp_path / "projects" / "bus-foundation"
    bf.mkdir(parents=True)
    (bf / "pyproject.toml").write_text(
        '[project]\nname = "bus-foundation"\ndependencies = []\n'
    )
    bf_src = bf / "src" / "bus_foundation"
    bf_src.mkdir(parents=True)
    (bf_src / "__init__.py").write_text("")
    real = tmp_path / "projects" / "real-consumer"
    real.mkdir(parents=True)
    (real / "pyproject.toml").write_text(
        '[project]\nname = "real-consumer"\ndependencies = ["bus-foundation"]\n'
    )
    src = real / "src" / "real_consumer"
    src.mkdir(parents=True)
    (src / "main.py").write_text(
        "from bus_foundation.facade import event as bus_event\n"
        "bus_event.publish(topic='demo:x', payload={})\n"
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--json"],
        capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    projects_found = {r["project"] for r in data["reports"]}
    assert "bus-foundation" not in projects_found
    assert "real-consumer" in projects_found
