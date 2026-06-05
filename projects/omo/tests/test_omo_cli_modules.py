"""Tests for new OMO CLI modules (goal, state, knowledge, delivery, standard, i0, alert, event, dashboard)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Set cwd to Workspace root for .omo/ discovery
_WS = os.path.expanduser("~/Workspace")
if os.path.exists(_WS):
    os.chdir(_WS)
sys.path.insert(0, os.path.expanduser("~/Workspace/projects/omo/src"))

from omo.cli import main


class TestGoalCLI:
    def test_goal_list(self):
        r = main(["goal", "list"])
        assert r == 0

    def test_goal_status_json(self):
        r = main(["goal", "status"])
        assert r == 0

    def test_goal_create_and_progress(self):
        # Create temp goal (will be cleaned below)
        r = main(["goal", "create", "--id", "TEST-G1", "--desc", "Test goal"])
        assert r == 0
        r = main(["goal", "progress", "--id", "TEST-G1", "--pct", "50"])
        assert r == 0
        # Verify it appears in list
        import yaml
        gf = Path(".omo/goals/current.yaml")
        data = yaml.safe_load(gf.read_text())
        goals = [g for g in data.get("goals", []) if g.get("id") == "TEST-G1"]
        assert len(goals) == 1
        assert goals[0]["progress"] == 50.0
        # Clean up
        data["goals"] = [g for g in data["goals"] if g.get("id") != "TEST-G1"]
        from omo.omo_io import write_yaml_atomic
        write_yaml_atomic(gf, data)


class TestStateCLI:
    def test_state_show(self):
        r = main(["state", "show"])
        assert r == 0

    def test_state_health(self):
        r = main(["state", "health"])
        assert r == 0


class TestKnowledgeCLI:
    def test_knowledge_list(self):
        r = main(["knowledge", "list"])
        assert r == 0

    def test_knowledge_add_and_cleanup(self):
        # Add a test doc then clean up
        r = main(["knowledge", "add", "--plane", "test", "--title", "CLI test doc", "--content", "Test content"])
        assert r == 0
        test_file = Path(".omo/_knowledge/test/cli-test-doc.md")
        assert test_file.exists()
        test_file.unlink()
        # Remove empty test dir
        test_dir = Path(".omo/_knowledge/test")
        if test_dir.exists() and not list(test_dir.iterdir()):
            test_dir.rmdir()


class TestDeliveryCLI:
    def test_delivery_list(self):
        r = main(["delivery", "list"])
        assert r == 0


class TestStandardCLI:
    def test_standard_list(self):
        r = main(["standard", "list"])
        assert r == 0


class TestObservabilityCLI:
    def test_log_stats(self):
        r = main(["log", "stats"])
        assert r == 0

    def test_log_tail(self):
        r = main(["log", "tail", "--lines", "3"])
        assert r == 0

    def test_alert_check(self):
        r = main(["alert", "check"])
        assert r == 0

    def test_metric(self):
        r = main(["metric"])
        assert r == 0
