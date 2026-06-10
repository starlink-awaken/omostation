#!/usr/bin/env python3
"""Tests for OMO CLI modules: goal, state, knowledge, delivery, standard, i0, task, evidence.

Covers OMO-CLI-TEST-GAP debt remediation for:
- omo_goal
- omo_state
- omo_knowledge
- omo_delivery
- omo_standard
- omo_i0
- omo_task
- omo_evidence
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

# Ensure omo src is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from omo.omo_goal import cmd_goal_create, cmd_goal_list, cmd_goal_progress, cmd_goal_status
from omo.omo_state import cmd_state_health, cmd_state_show
from omo.omo_knowledge import cmd_knowledge_add, cmd_knowledge_list
from omo.omo_delivery import cmd_delivery_archive, cmd_delivery_list
from omo.omo_standard import cmd_standard_add, cmd_standard_list
from omo.omo_i0 import cmd_i0_routes, cmd_i0_status
from omo.omo_task import cmd_task_list
from omo.omo_evidence import cmd_evidence_list


# -- omo_goal --


class TestOmoGoal:
    def test_cmd_goal_list_no_file(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        ret = cmd_goal_list(omo_dir)
        assert ret == 0
        captured = capsys.readouterr()
        assert "No current goals found" in captured.out

    def test_cmd_goal_list(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        goals_dir = omo_dir / "goals"
        goals_dir.mkdir()
        goal_data = {
            "phase": 31,
            "theme": "Debt cleanup",
            "status": "active",
            "current_wave": "W1",
            "goals": [
                {"id": "G31.1", "desc": "Fix tests", "progress": 50.0, "status": "active"},
                {"id": "G31.2", "desc": "Clean debt", "progress": 100.0, "status": "done"},
            ],
        }
        (goals_dir / "current.yaml").write_text(yaml.dump(goal_data))
        ret = cmd_goal_list(omo_dir)
        assert ret == 0
        captured = capsys.readouterr()
        assert "Phase 31" in captured.out
        assert "Debt cleanup" in captured.out
        assert "G31.1: Fix tests" in captured.out
        assert "G31.2: Clean debt" in captured.out
        assert "2 goals total" in captured.out

    def test_cmd_goal_status(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        goals_dir = omo_dir / "goals"
        goals_dir.mkdir()
        goal_data = {
            "phase": 31,
            "current_wave": "W1",
            "goals": [
                {"id": "G31.1", "desc": "Fix tests", "progress": 100.0, "status": "done"},
                {"id": "G31.2", "desc": "Clean debt", "progress": 0.0, "status": "pending"},
            ],
        }
        (goals_dir / "current.yaml").write_text(yaml.dump(goal_data))
        ret = cmd_goal_status(omo_dir)
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total"] == 2
        assert data["done"] == 1
        assert data["pending"] == 1

    def test_cmd_goal_create(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        goals_dir = omo_dir / "goals"
        goals_dir.mkdir()
        goal_data = {"phase": 31, "goals": []}
        (goals_dir / "current.yaml").write_text(yaml.dump(goal_data))
        ret = cmd_goal_create(omo_dir, "G31.3", "New goal")
        assert ret == 0
        captured = capsys.readouterr()
        assert "G31.3 created" in captured.out
        updated = yaml.safe_load((goals_dir / "current.yaml").read_text())
        assert len(updated["goals"]) == 1
        assert updated["goals"][0]["id"] == "G31.3"

    def test_cmd_goal_create_duplicate(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        goals_dir = omo_dir / "goals"
        goals_dir.mkdir()
        goal_data = {"phase": 31, "goals": [{"id": "G31.3", "desc": "Existing"}]}
        (goals_dir / "current.yaml").write_text(yaml.dump(goal_data))
        ret = cmd_goal_create(omo_dir, "G31.3", "Duplicate")
        assert ret == 1
        captured = capsys.readouterr()
        assert "already exists" in captured.err

    def test_cmd_goal_progress(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        goals_dir = omo_dir / "goals"
        goals_dir.mkdir()
        goal_data = {"phase": 31, "goals": [{"id": "G31.1", "desc": "Test", "progress": 0.0}]}
        (goals_dir / "current.yaml").write_text(yaml.dump(goal_data))
        ret = cmd_goal_progress(omo_dir, "G31.1", 75.0)
        assert ret == 0
        captured = capsys.readouterr()
        assert "progress" in captured.out
        assert "75.0%" in captured.out
        updated = yaml.safe_load((goals_dir / "current.yaml").read_text())
        assert updated["goals"][0]["progress"] == 75.0
        assert updated["goals"][0]["status"] == "active"

    def test_cmd_goal_progress_to_done(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        goals_dir = omo_dir / "goals"
        goals_dir.mkdir()
        goal_data = {"phase": 31, "goals": [{"id": "G31.1", "desc": "Test", "progress": 0.0}]}
        (goals_dir / "current.yaml").write_text(yaml.dump(goal_data))
        ret = cmd_goal_progress(omo_dir, "G31.1", 100.0)
        assert ret == 0
        updated = yaml.safe_load((goals_dir / "current.yaml").read_text())
        assert updated["goals"][0]["status"] == "done"

    def test_cmd_goal_progress_not_found(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        goals_dir = omo_dir / "goals"
        goals_dir.mkdir()
        goal_data = {"phase": 31, "goals": []}
        (goals_dir / "current.yaml").write_text(yaml.dump(goal_data))
        ret = cmd_goal_progress(omo_dir, "G99.9", 50.0)
        assert ret == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err


# -- omo_state --


class TestOmoState:
    def test_cmd_state_show_no_file(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        ret = cmd_state_show(omo_dir, "text")
        assert ret == 0
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_cmd_state_show_text(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        state_dir = omo_dir / "state"
        state_dir.mkdir()
        state_data = {
            "current_phase": 31,
            "health_score": 70.0,
            "active_agents": 2,
            "idle_agents": 3,
            "blocked_tasks": 1,
            "code_freeze": True,
            "next_milestone": "Phase 31 W1",
        }
        (state_dir / "system.yaml").write_text(yaml.dump(state_data))
        ret = cmd_state_show(omo_dir, "text")
        assert ret == 0
        captured = capsys.readouterr()
        assert "Phase:          31" in captured.out
        assert "Health:         70.0" in captured.out
        assert "Code freeze:    True" in captured.out

    def test_cmd_state_show_json(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        state_dir = omo_dir / "state"
        state_dir.mkdir()
        state_data = {"current_phase": 31, "health_score": 70.0}
        (state_dir / "system.yaml").write_text(yaml.dump(state_data))
        ret = cmd_state_show(omo_dir, "json")
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["current_phase"] == 31

    def test_cmd_state_health_no_file(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        ret = cmd_state_health(omo_dir)
        assert ret == 0
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_cmd_state_health(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        state_dir = omo_dir / "state"
        state_dir.mkdir()
        health_data = {
            "services": {
                "agora": {"name": "Agora", "health_check": "healthy"},
                "runtime": {"name": "Runtime", "health_check": "failed"},
                "gbrain": {"name": "gbrain", "health_check": "idle"},
            }
        }
        (state_dir / "system_health.yaml").write_text(yaml.dump(health_data))
        ret = cmd_state_health(omo_dir)
        assert ret == 0
        captured = capsys.readouterr()
        assert "3 total (1 healthy, 1 degraded)" in captured.out
        assert "Agora: healthy" in captured.out
        assert "Runtime: failed" in captured.out
        assert "gbrain: idle" in captured.out


# -- omo_knowledge --


class TestOmoKnowledge:
    def test_cmd_knowledge_list_no_dir(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        ret = cmd_knowledge_list(omo_dir, None)
        assert ret == 0
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_cmd_knowledge_list(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        knowledge_dir = omo_dir / "_knowledge"
        design_dir = knowledge_dir / "design"
        design_dir.mkdir(parents=True)
        (design_dir / "test-doc.md").write_text("# Test\n\nContent")
        ret = cmd_knowledge_list(omo_dir, None)
        assert ret == 0
        captured = capsys.readouterr()
        assert "Total: 1 documents" in captured.out

    def test_cmd_knowledge_list_plane(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        knowledge_dir = omo_dir / "_knowledge" / "design"
        knowledge_dir.mkdir(parents=True)
        (knowledge_dir / "doc1.md").write_text("# Doc1\n\nContent")
        (knowledge_dir / "doc2.md").write_text("# Doc2\n\nMore")
        ret = cmd_knowledge_list(omo_dir, "design")
        assert ret == 0
        captured = capsys.readouterr()
        assert "Total: 2 documents" in captured.out

    def test_cmd_knowledge_add(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        ret = cmd_knowledge_add(omo_dir, "design", "My Doc", "Hello world", stdin=False)
        assert ret == 0
        captured = capsys.readouterr()
        assert "Created _knowledge/design/my-doc.md" in captured.out
        doc = omo_dir / "_knowledge" / "design" / "my-doc.md"
        assert doc.exists()
        assert "Hello world" in doc.read_text()

    def test_cmd_knowledge_add_duplicate(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        design_dir = omo_dir / "_knowledge" / "design"
        design_dir.mkdir(parents=True)
        (design_dir / "my-doc.md").write_text("existing")
        ret = cmd_knowledge_add(omo_dir, "design", "My Doc", "New content", stdin=False)
        assert ret == 1
        captured = capsys.readouterr()
        assert "already exists" in captured.err


# -- omo_delivery --


class TestOmoDelivery:
    def test_cmd_delivery_list_no_dir(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        ret = cmd_delivery_list(omo_dir, None)
        assert ret == 0
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_cmd_delivery_list(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        delivery_dir = omo_dir / "_delivery"
        delivery_dir.mkdir()
        (delivery_dir / "report.md").write_text("# Report")
        (delivery_dir / "data.json").write_text('{"key": "value"}')
        (delivery_dir / "config.yaml").write_text("key: value")
        ret = cmd_delivery_list(omo_dir, None)
        assert ret == 0
        captured = capsys.readouterr()
        assert "report.md" in captured.out
        assert "data.json" in captured.out
        assert "config.yaml" in captured.out
        assert "Total: 3 delivery artifacts" in captured.out

    def test_cmd_delivery_list_phase_filter(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        delivery_dir = omo_dir / "_delivery"
        delivery_dir.mkdir()
        (delivery_dir / "phase28-report.md").write_text("# P28")
        (delivery_dir / "phase29-report.md").write_text("# P29")
        ret = cmd_delivery_list(omo_dir, "phase28")
        assert ret == 0
        captured = capsys.readouterr()
        assert "phase28-report.md" in captured.out
        assert "phase29-report.md" not in captured.out

    def test_cmd_delivery_archive(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        delivery_dir = omo_dir / "_delivery"
        delivery_dir.mkdir()
        (delivery_dir / "phase27-a.md").write_text("A")
        (delivery_dir / "phase27-b.md").write_text("B")
        ret = cmd_delivery_archive(omo_dir, "phase27")
        assert ret == 0
        captured = capsys.readouterr()
        assert "Archived 2 artifacts" in captured.out
        assert not (delivery_dir / "phase27-a.md").exists()
        archive_dir = omo_dir / "_archive" / "delivery" / "phase27"
        assert (archive_dir / "phase27-a.md").exists()
        assert (archive_dir / "phase27-b.md").exists()


# -- omo_standard --


class TestOmoStandard:
    def test_cmd_standard_list_no_dir(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        ret = cmd_standard_list(omo_dir)
        assert ret == 0
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_cmd_standard_list(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        standards_dir = omo_dir / "standards"
        standards_dir.mkdir()
        (standards_dir / "rule1.md").write_text("# Rule 1")
        (standards_dir / "config.yaml").write_text("key: value")
        ret = cmd_standard_list(omo_dir)
        assert ret == 0
        captured = capsys.readouterr()
        assert "1 markdown, 1 YAML" in captured.out
        assert "rule1.md" in captured.out
        assert "config.yaml" in captured.out

    def test_cmd_standard_add(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        standards_dir = omo_dir / "standards"
        standards_dir.mkdir()
        ret = cmd_standard_add(omo_dir, "New Standard", "This is the content.", stdin=False)
        assert ret == 0
        captured = capsys.readouterr()
        assert "Created standards/new-standard.md" in captured.out
        doc = standards_dir / "new-standard.md"
        assert doc.exists()
        assert "# New Standard" in doc.read_text()

    def test_cmd_standard_add_duplicate(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        standards_dir = omo_dir / "standards"
        standards_dir.mkdir()
        (standards_dir / "new-standard.md").write_text("existing")
        ret = cmd_standard_add(omo_dir, "New Standard", "Content", stdin=False)
        assert ret == 1
        captured = capsys.readouterr()
        assert "already exists" in captured.err


# -- omo_i0 --


class TestOmoI0:
    def test_cmd_i0_status_unreachable(self, capsys) -> None:
        with patch("omo.omo_i0.urlopen", side_effect=Exception("Connection refused")):
            ret = cmd_i0_status()
        assert ret == 0
        captured = capsys.readouterr()
        assert "Agora Hub:" in captured.out
        assert "unreachable" in captured.out

    def test_cmd_i0_status_running(self, capsys) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"routes": 42, "service_count": 5}).encode()
        with patch("omo.omo_i0.urlopen", return_value=mock_resp):
            ret = cmd_i0_status()
        assert ret == 0
        captured = capsys.readouterr()
        assert "Agora Hub:" in captured.out
        assert "running" in captured.out

    def test_cmd_i0_routes(self, capsys) -> None:
        services = [
            {"name": "kos", "status": "healthy", "tools": [1, 2, 3]},
            {"name": "minerva", "status": "idle", "tools": []},
        ]
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(services).encode()
        with patch("omo.omo_i0.urlopen", return_value=mock_resp):
            ret = cmd_i0_routes()
        assert ret == 0
        captured = capsys.readouterr()
        assert "kos" in captured.out
        assert "minerva" in captured.out
        assert "2 services" in captured.out

    def test_cmd_i0_routes_failed(self, capsys) -> None:
        with patch("omo.omo_i0.urlopen", side_effect=Exception("timeout")):
            ret = cmd_i0_routes()
        assert ret == 0
        captured = capsys.readouterr()
        assert "Route query failed" in captured.out


# -- omo_task --


class TestOmoTask:
    def test_cmd_task_list_no_dir(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        ret = cmd_task_list(omo_dir, None)
        assert ret == 0
        captured = capsys.readouterr()
        assert "Total: 0 tasks" in captured.out

    def test_cmd_task_list(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        active_dir = omo_dir / "tasks" / "active"
        active_dir.mkdir(parents=True)
        (active_dir / "task-01.yaml").write_text("id: T1\ntitle: Test task 1\n")
        (active_dir / "task-02.yaml").write_text("id: T2\ntitle: Test task 2\n")
        done_dir = omo_dir / "tasks" / "done"
        done_dir.mkdir(parents=True)
        (done_dir / "task-03.yaml").write_text("id: T3\ntitle: Done task\n")
        ret = cmd_task_list(omo_dir, None)
        assert ret == 0
        captured = capsys.readouterr()
        assert "active (2 tasks)" in captured.out
        assert "done (1 tasks)" in captured.out
        assert "id: T1" in captured.out
        assert "Total: 3 tasks" in captured.out

    def test_cmd_task_list_status_filter(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        active_dir = omo_dir / "tasks" / "active"
        active_dir.mkdir(parents=True)
        (active_dir / "task-01.yaml").write_text("id: T1\n")
        done_dir = omo_dir / "tasks" / "done"
        done_dir.mkdir(parents=True)
        (done_dir / "task-02.yaml").write_text("id: T2\n")
        ret = cmd_task_list(omo_dir, "active")
        assert ret == 0
        captured = capsys.readouterr()
        assert "id: T1" in captured.out
        assert "id: T2" not in captured.out


# -- omo_evidence --


class TestOmoEvidence:
    def test_cmd_evidence_list_no_dir(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        ret = cmd_evidence_list(omo_dir, None)
        assert ret == 0
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_cmd_evidence_list(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        evidence_dir = omo_dir / "evidence"
        sub_dir = evidence_dir / "divergence"
        sub_dir.mkdir(parents=True)
        (sub_dir / "test.md").write_text("# Evidence")
        ret = cmd_evidence_list(omo_dir, None)
        assert ret == 0
        captured = capsys.readouterr()
        assert "test.md" in captured.out
        assert "Total: 1 evidence files" in captured.out

    def test_cmd_evidence_list_category(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        evidence_dir = omo_dir / "evidence"
        p15 = evidence_dir / "phase15"
        p15.mkdir(parents=True)
        (p15 / "report.md").write_text("# Report")
        p16 = evidence_dir / "phase16"
        p16.mkdir(parents=True)
        (p16 / "data.md").write_text("# Data")
        ret = cmd_evidence_list(omo_dir, "phase15")
        assert ret == 0
        captured = capsys.readouterr()
        assert "report.md" in captured.out
        assert "data.md" not in captured.out
