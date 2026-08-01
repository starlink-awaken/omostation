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

from omo.omo_debt_cli import cmd_debt_close, cmd_debt_desc, cmd_debt_list
from omo.omo_delivery import cmd_delivery_archive, cmd_delivery_list
from omo.omo_evidence import cmd_evidence_list
from omo.omo_goal import (
    cmd_goal_create,
    cmd_goal_list,
    cmd_goal_progress,
    cmd_goal_status,
)
from omo.omo_i0 import cmd_i0_routes, cmd_i0_status
from omo.omo_knowledge import cmd_knowledge_add, cmd_knowledge_list
from omo.omo_paths import OMO_ROOT, find_omo_dir
from omo.omo_standard import cmd_standard_add, cmd_standard_list
from omo.omo_state import (
    cmd_state_health,
    cmd_state_refresh,
    cmd_state_show,
    cmd_state_sync,
    cmd_state_sync_tasks,
)
from omo.omo_task import (
    cmd_task_create,
    cmd_task_done,
    cmd_task_list,
    cmd_task_refresh_evidence,
)

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
                {
                    "id": "G31.1",
                    "desc": "Fix tests",
                    "progress": 50.0,
                    "status": "active",
                },
                {
                    "id": "G31.2",
                    "desc": "Clean debt",
                    "progress": 100.0,
                    "status": "done",
                },
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
                {
                    "id": "G31.1",
                    "desc": "Fix tests",
                    "progress": 100.0,
                    "status": "done",
                },
                {
                    "id": "G31.2",
                    "desc": "Clean debt",
                    "progress": 0.0,
                    "status": "pending",
                },
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

    def test_cmd_goal_status_accepts_multi_document_yaml(
        self, capsys, tmp_path: Path
    ) -> None:
        omo_dir = tmp_path
        goals_dir = omo_dir / "goals"
        goals_dir.mkdir()
        (goals_dir / "current.yaml").write_text(
            "---\nstatus: active\ncurrent_wave: W1\n---\n---\nphase: 31\ngoals:\n"
            "  - id: G31.1\n    status: done\n"
            "  - id: G31.2\n    status: pending\n",
            encoding="utf-8",
        )
        ret = cmd_goal_status(omo_dir)
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["phase"] == 31
        assert data["wave"] == "W1"
        assert data["done"] == 1

    def test_cmd_goal_create(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        goals_dir = omo_dir / "goals"
        goals_dir.mkdir()
        goal_data = {"phase": 31, "goals": []}
        (goals_dir / "current.yaml").write_text(yaml.dump(goal_data))
        ret = cmd_goal_create(omo_dir, "G31.3", "New goal", "reviewer:goal:create")
        assert ret == 0
        captured = capsys.readouterr()
        assert "Governed goal G31.3 created" in captured.out
        updated = yaml.safe_load((goals_dir / "current.yaml").read_text())
        assert len(updated["goals"]) == 1
        assert updated["goals"][0]["id"] == "G31.3"
        assert updated["goals"][0]["source_ref"] == "reviewer:goal:create"
        artifact = (
            omo_dir.parent
            / "runtime"
            / "omo"
            / "_delivery"
            / "ingress"
            / "goals"
            / "G31.3.yaml"
        )
        assert artifact.exists()
        registry = yaml.safe_load(
            (
                omo_dir.parent
                / "runtime"
                / "omo"
                / "_delivery"
                / "ingress"
                / "registry.yaml"
            ).read_text(encoding="utf-8")
        )
        assert registry["goals"]["by_source_ref"]["reviewer:goal:create"] == "G31.3"

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
        goal_data = {
            "phase": 31,
            "goals": [{"id": "G31.1", "desc": "Test", "progress": 0.0}],
        }
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
        goal_data = {
            "phase": 31,
            "goals": [{"id": "G31.1", "desc": "Test", "progress": 0.0}],
        }
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

    def test_cmd_state_show_json_accepts_multi_document_yaml(
        self, capsys, tmp_path: Path
    ) -> None:
        omo_dir = tmp_path
        state_dir = omo_dir / "state"
        state_dir.mkdir()
        (state_dir / "system.yaml").write_text(
            "---\nstatus: active\nowner: governance\n---\n---\ncurrent_phase: 31\nhealth_score: 70.0\n",
            encoding="utf-8",
        )
        ret = cmd_state_show(omo_dir, "json")
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["current_phase"] == 31
        assert data["status"] == "active"

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

    def test_cmd_state_health_prefers_canonical_projection(
        self, capsys, tmp_path: Path
    ) -> None:
        omo_dir = tmp_path
        canonical_dir = omo_dir / "state" / "runtime"
        canonical_dir.mkdir(parents=True)
        (omo_dir / "state").mkdir(exist_ok=True)
        (omo_dir / "state" / "system_health.yaml").write_text(
            yaml.dump(
                {"services": {"legacy": {"name": "Legacy", "health_check": "failed"}}}
            )
        )
        (canonical_dir / "system_health.yaml").write_text(
            yaml.dump(
                {
                    "services": {
                        "canonical": {"name": "Canonical", "health_check": "healthy"}
                    }
                }
            )
        )

        ret = cmd_state_health(omo_dir)

        assert ret == 0
        captured = capsys.readouterr()
        assert "Canonical: healthy" in captured.out
        assert "Legacy" not in captured.out

    def test_cmd_state_refresh_dual_writes_canonical_projection(
        self, capsys, tmp_path: Path
    ) -> None:
        omo_dir = tmp_path
        (omo_dir / "state").mkdir()
        result = MagicMock(
            returncode=0,
            stdout=json.dumps([{"name": "agora", "status": "running", "port": 7430}]),
        )

        with patch("subprocess.run", return_value=result):
            ret = cmd_state_refresh(omo_dir, dry_run=False)

        assert ret == 0
        canonical = omo_dir / "state" / "runtime" / "system_health.yaml"
        legacy = omo_dir / "state" / "system_health.yaml"
        assert canonical.exists()
        assert legacy.exists()
        assert yaml.safe_load(canonical.read_text()) == yaml.safe_load(
            legacy.read_text()
        )
        assert (
            yaml.safe_load(canonical.read_text())["services"]["agora"]["health_check"]
            == "healthy"
        )
        assert (
            "system_health.yaml refreshed: 1 services updated"
            in capsys.readouterr().out
        )

    def test_cmd_state_sync_tasks_fixes_drift(self, capsys, tmp_path: Path) -> None:
        """sync-tasks 从 tasks/ 真实文件数重算计数 (治本手动维护漂移, OPT-7)."""
        omo_dir = tmp_path
        state_dir = omo_dir / "state"
        state_dir.mkdir(parents=True)
        for sub, n in (("done", 2), ("planned", 1), ("active", 1)):
            d = omo_dir / "tasks" / sub
            d.mkdir(parents=True)
            for i in range(n):
                (d / f"TASK-{sub}{i}.yaml").write_text(
                    f"id: TASK-{sub}{i}\ntitle: {sub}任务{i}\nstatus: done\n",
                    encoding="utf-8",
                )
        # 故意写漂移的计数 + 含僵尸的 next_planned_tasks
        (state_dir / "system.yaml").write_text(
            yaml.dump(
                {
                    "completed_tasks": 0,
                    "planned_tasks": 99,
                    "active_tasks": 99,
                    "total_tasks": 0,
                    "next_planned_tasks": ["TASK-ZOMBIE-xxxx (已归档僵尸)"],
                    "current_phase": 42,
                }
            ),
            encoding="utf-8",
        )
        ret = cmd_state_sync_tasks(omo_dir, dry_run=False)
        assert ret == 0
        data = yaml.safe_load((state_dir / "system.yaml").read_text(encoding="utf-8"))
        assert data["completed_tasks"] == 2  # done 真实文件数
        assert data["planned_tasks"] == 1
        assert data["active_tasks"] == 1
        assert data["total_tasks"] == 4  # 2+1+1
        assert "TASK-ZOMBIE-xxxx" not in str(data["next_planned_tasks"])
        assert any("TASK-planned0" in s for s in data["next_planned_tasks"])
        assert data["current_phase"] == 42  # 其他字段保真
        artifacts = sorted(
            (
                omo_dir.parent / "runtime" / "omo" / "_delivery" / "ingress" / "state"
            ).glob("system-projection-*.yaml")
        )
        assert artifacts
        artifact = yaml.safe_load(artifacts[-1].read_text(encoding="utf-8"))
        assert artifact["kind"] == "system_projection_fields_written"
        assert "completed_tasks" in artifact["updated_fields"]
        captured = capsys.readouterr()
        assert "已同步" in captured.out

    def test_cmd_state_sync_tasks_dry_run(self, capsys, tmp_path: Path) -> None:
        """dry-run 不写文件, 只预览."""
        omo_dir = tmp_path
        state_dir = omo_dir / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "system.yaml").write_text(
            yaml.dump({"completed_tasks": 0}), encoding="utf-8"
        )
        ret = cmd_state_sync_tasks(omo_dir, dry_run=True)
        assert ret == 0
        data = yaml.safe_load((state_dir / "system.yaml").read_text(encoding="utf-8"))
        assert data["completed_tasks"] == 0  # 未被改写
        captured = capsys.readouterr()
        assert "dry-run" in captured.out

    def test_cmd_state_sync_tasks_clears_zombie(self, capsys, tmp_path: Path) -> None:
        """next_planned_tasks 含已归档僵尸 → sync 后从 planned/ 真实重建."""
        omo_dir = tmp_path
        state_dir = omo_dir / "state"
        planned_dir = omo_dir / "tasks" / "planned"
        planned_dir.mkdir(parents=True)
        (planned_dir / "TASK-ALIVE.yaml").write_text(
            "id: TASK-ALIVE\ntitle: 存活任务\n", encoding="utf-8"
        )
        state_dir.mkdir()
        (state_dir / "system.yaml").write_text(
            yaml.dump(
                {
                    "next_planned_tasks": [
                        "TASK-ZOMBIE (已归档僵尸数据)",
                        "TASK-STALE-OLD (28天前清理的)",
                    ]
                }
            ),
            encoding="utf-8",
        )
        ret = cmd_state_sync_tasks(omo_dir, dry_run=False)
        assert ret == 0
        data = yaml.safe_load((state_dir / "system.yaml").read_text(encoding="utf-8"))
        planned = data["next_planned_tasks"]
        assert len(planned) == 1
        assert "TASK-ALIVE" in planned[0]
        assert "ZOMBIE" not in str(planned)

    def test_cmd_state_sync_delegates_to_state_broker_json(
        self, capsys, tmp_path: Path, monkeypatch
    ) -> None:
        """state sync 统一代理到 omo_ingress_state broker."""
        omo_dir = tmp_path / ".omo"
        omo_dir.mkdir()

        def fake_sync(workspace_root: Path, *, dry_run: bool):
            assert workspace_root == tmp_path
            assert dry_run is True
            return {
                "ok": True,
                "dry_run": True,
                "changed_count": 1,
                "writes": [{"path": ".omo/state/health.yaml", "changed": True}],
            }

        monkeypatch.setattr("omo.omo_state.sync_state_projection", fake_sync)

        ret = cmd_state_sync(omo_dir, dry_run=True, fmt="json")

        assert ret == 0
        report = json.loads(capsys.readouterr().out)
        assert report["ok"] is True
        assert report["changed_count"] == 1


# -- omo_debt --


class TestOmoDebt:
    def test_cmd_debt_list(self, capsys, tmp_path: Path) -> None:
        """list 列 debt_weight_items + resolved 状态."""
        omo_dir = tmp_path
        state_dir = omo_dir / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "system.yaml").write_text(
            yaml.dump(
                {
                    "debt_weight": 0.5,
                    "debt_weight_items": {
                        "DEBT-X": {"resolved": False, "weight": 0.0, "desc": "test X"},
                        "DEBT-Y": {"resolved": True, "weight": 0.0, "desc": "test Y"},
                    },
                    "resolved_debt_items": ["DEBT-Y"],
                }
            ),
            encoding="utf-8",
        )
        ret = cmd_debt_list(omo_dir)
        assert ret == 0
        out = capsys.readouterr().out
        assert "2 total: 1 open / 1 resolved" in out
        assert "DEBT-X" in out
        assert "DEBT-Y" in out

    def test_cmd_debt_list_accepts_multi_document_state_yaml(
        self, capsys, tmp_path: Path
    ) -> None:
        omo_dir = tmp_path
        state_dir = omo_dir / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "system.yaml").write_text(
            "---\nstatus: active\nowner: governance\n---\n---\ndebt_weight: 0.5\n"
            "debt_weight_items:\n"
            "  DEBT-X:\n"
            "    resolved: false\n"
            "    desc: test X\n"
            "  DEBT-Y:\n"
            "    resolved: true\n"
            "    desc: test Y\n",
            encoding="utf-8",
        )
        ret = cmd_debt_list(omo_dir)
        assert ret == 0
        out = capsys.readouterr().out
        assert "2 total: 1 open / 1 resolved" in out
        assert "DEBT-X" in out
        assert "DEBT-Y" in out

    def test_cmd_debt_close_marks_resolved(self, capsys, tmp_path: Path) -> None:
        """close 改 canonical debt item lifecycle_state=closed."""
        omo_dir = tmp_path
        debt_dir = omo_dir / "debt" / "items"
        debt_dir.mkdir(parents=True)
        (debt_dir / "DEBT-X.yaml").write_text(
            yaml.dump(
                {
                    "id": "DEBT-X",
                    "title": "test X",
                    "description": "test X",
                    "lifecycle_state": "identified",
                    "history": [],
                }
            ),
            encoding="utf-8",
        )
        ret = cmd_debt_close(omo_dir, "DEBT-X", dry_run=False, confirm=True)
        assert ret == 0
        data = yaml.safe_load((debt_dir / "DEBT-X.yaml").read_text(encoding="utf-8"))
        assert data["lifecycle_state"] == "closed"
        assert data["closed_at"]
        assert data["history"][-1]["action"] == "close"
        assert "已关闭" in capsys.readouterr().out

    def test_cmd_debt_close_unknown_id(self, capsys, tmp_path: Path) -> None:
        """未知 debt_id 返回 1."""
        omo_dir = tmp_path
        (omo_dir / "debt" / "items").mkdir(parents=True)
        ret = cmd_debt_close(omo_dir, "DEBT-NOPE", dry_run=False, confirm=True)
        assert ret == 1
        assert "未知" in capsys.readouterr().out

    def test_cmd_debt_close_requires_confirm(self, capsys, tmp_path: Path) -> None:
        """无 --confirm 拒绝."""
        omo_dir = tmp_path
        debt_dir = omo_dir / "debt" / "items"
        debt_dir.mkdir(parents=True)
        (debt_dir / "DEBT-X.yaml").write_text(
            yaml.dump(
                {
                    "id": "DEBT-X",
                    "title": "x",
                    "description": "x",
                    "lifecycle_state": "identified",
                    "history": [],
                }
            ),
            encoding="utf-8",
        )
        ret = cmd_debt_close(omo_dir, "DEBT-X", dry_run=False, confirm=False)
        assert ret == 1
        assert "confirm" in capsys.readouterr().out

    def test_cmd_debt_close_dry_run_no_write(self, capsys, tmp_path: Path) -> None:
        """dry-run 不写 canonical debt item."""
        omo_dir = tmp_path
        debt_dir = omo_dir / "debt" / "items"
        debt_dir.mkdir(parents=True)
        (debt_dir / "DEBT-X.yaml").write_text(
            yaml.dump(
                {
                    "id": "DEBT-X",
                    "title": "x",
                    "description": "x",
                    "lifecycle_state": "identified",
                    "history": [],
                }
            ),
            encoding="utf-8",
        )
        ret = cmd_debt_close(omo_dir, "DEBT-X", dry_run=True, confirm=False)
        assert ret == 0
        data = yaml.safe_load((debt_dir / "DEBT-X.yaml").read_text(encoding="utf-8"))
        assert data["lifecycle_state"] == "identified"

    def test_cmd_debt_desc_updates(self, capsys, tmp_path: Path) -> None:
        """desc 更新 canonical debt item description."""
        omo_dir = tmp_path
        debt_dir = omo_dir / "debt" / "items"
        debt_dir.mkdir(parents=True)
        (debt_dir / "DEBT-X.yaml").write_text(
            yaml.dump(
                {
                    "id": "DEBT-X",
                    "title": "x",
                    "description": "old lie",
                    "lifecycle_state": "identified",
                    "history": [],
                }
            ),
            encoding="utf-8",
        )
        ret = cmd_debt_desc(omo_dir, "DEBT-X", "new truth", dry_run=False)
        assert ret == 0
        data = yaml.safe_load((debt_dir / "DEBT-X.yaml").read_text(encoding="utf-8"))
        assert data["description"] == "new truth"
        assert data["history"][-1]["action"] == "update_description"
        assert "description 已更新" in capsys.readouterr().out

    def test_cmd_debt_desc_unknown_id(self, capsys, tmp_path: Path) -> None:
        """未知 debt_id 返回 1."""
        omo_dir = tmp_path
        (omo_dir / "debt" / "items").mkdir(parents=True)
        ret = cmd_debt_desc(omo_dir, "DEBT-NOPE", "x", dry_run=False)
        assert ret == 1
        assert "未知" in capsys.readouterr().out

    def test_cmd_debt_desc_dry_run_no_write(self, capsys, tmp_path: Path) -> None:
        """dry-run 不写 canonical debt item."""
        omo_dir = tmp_path
        debt_dir = omo_dir / "debt" / "items"
        debt_dir.mkdir(parents=True)
        (debt_dir / "DEBT-X.yaml").write_text(
            yaml.dump(
                {
                    "id": "DEBT-X",
                    "title": "x",
                    "description": "old",
                    "lifecycle_state": "identified",
                    "history": [],
                }
            ),
            encoding="utf-8",
        )
        ret = cmd_debt_desc(omo_dir, "DEBT-X", "new", dry_run=True)
        assert ret == 0
        data = yaml.safe_load((debt_dir / "DEBT-X.yaml").read_text(encoding="utf-8"))
        assert data["description"] == "old"


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
        artifacts = list(
            (
                omo_dir.parent
                / "runtime"
                / "omo"
                / "_delivery"
                / "ingress"
                / "knowledge"
            ).glob("design-my-doc-*.yaml")
        )
        assert len(artifacts) == 1

    def test_cmd_knowledge_add_duplicate(self, capsys, tmp_path: Path) -> None:
        omo_dir = tmp_path
        design_dir = omo_dir / "_knowledge" / "design"
        design_dir.mkdir(parents=True)
        (design_dir / "my-doc.md").write_text("existing")
        ret = cmd_knowledge_add(omo_dir, "design", "My Doc", "New content", stdin=False)
        assert ret == 1
        captured = capsys.readouterr()
        assert "already exists" in captured.err

    def test_cmd_knowledge_list_skips_missing_symlink(
        self, capsys, tmp_path: Path
    ) -> None:
        omo_dir = tmp_path
        mgmt_dir = omo_dir / "_knowledge" / "management"
        mgmt_dir.mkdir(parents=True)
        (mgmt_dir / "broken.md").symlink_to("missing-target.md")

        ret = cmd_knowledge_list(omo_dir, "management")

        assert ret == 0
        captured = capsys.readouterr()
        assert "broken.md" in captured.out
        assert "(missing)" in captured.out


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
        ret = cmd_standard_add(
            omo_dir, "New Standard", "This is the content.", stdin=False
        )
        assert ret == 0
        captured = capsys.readouterr()
        assert "Created standards/new-standard.md" in captured.out
        doc = standards_dir / "new-standard.md"
        assert doc.exists()
        assert "# New Standard" in doc.read_text()
        artifacts = list(
            (
                omo_dir.parent
                / "runtime"
                / "omo"
                / "_delivery"
                / "ingress"
                / "standards"
            ).glob("new-standard-*.yaml")
        )
        assert len(artifacts) == 1

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
        mock_resp.read.return_value = json.dumps(
            {"routes": 42, "service_count": 5}
        ).encode()
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

    def test_cmd_task_create_uses_governed_ingress(
        self, capsys, tmp_path: Path
    ) -> None:
        omo_dir = tmp_path
        ret = cmd_task_create(
            omo_dir,
            title="治理化创建任务",
            desc="不要手改 .omo",
            priority="P1",
            source_docs=["docs/plan.md"],
            test_plan=["uv run pytest tests/test_sample.py -q"],
            deliverables=["代码", "测试"],
            evidence_required=["pytest"],
            source_ref="reviewer:task:create-governed",
        )
        assert ret == 0

        planned_dir = omo_dir / "tasks" / "planned"
        task_files = sorted(planned_dir.glob("TASK-*.yaml"))
        assert len(task_files) == 1
        payload = yaml.safe_load(task_files[0].read_text(encoding="utf-8"))
        assert payload["metadata"]["broker"] == "projects/omo/src/omo/omo_ingress.py"
        assert payload["metadata"]["source_ref"] == "reviewer:task:create-governed"

        artifact = (
            omo_dir.parent
            / "runtime"
            / "omo"
            / "_delivery"
            / "ingress"
            / "tasks"
            / f"{payload['id']}.yaml"
        )
        assert artifact.exists()
        registry = yaml.safe_load(
            (
                omo_dir.parent
                / "runtime"
                / "omo"
                / "_delivery"
                / "ingress"
                / "registry.yaml"
            ).read_text(encoding="utf-8")
        )
        assert (
            registry["tasks"]["by_source_ref"]["reviewer:task:create-governed"]
            == payload["id"]
        )

        captured = capsys.readouterr()
        assert "Created governed task:" in captured.out

    def test_cmd_task_done_archives_planned(self, capsys, tmp_path: Path) -> None:
        """归档 planned 任务 → done/ + status done + completed_at (OPT-5 补齐工具测试)."""
        omo_dir = tmp_path
        planned_dir = omo_dir / "tasks" / "planned"
        planned_dir.mkdir(parents=True)
        (omo_dir / "evidence.md").write_text("# evidence\n", encoding="utf-8")
        (planned_dir / "IMPORTED-test1.yaml").write_text(
            yaml.dump(
                {
                    "id": "IMPORTED-test1",
                    "title": "归档测试",
                    "status": "candidate",
                    "task_type": "feature",
                    "risk_level": "L0",
                    "depends_on": [],
                    "source_docs": ["spec.md"],
                    "deliverables": ["代码"],
                    "assigned_to": None,
                    "dispatch_id": None,
                    "run_ref": None,
                    "approval_ref": None,
                    "review_ref": None,
                    "knowledge_refs": [],
                    "handoff_refs": [],
                    "entry_gate": [],
                    "evidence_required": ["pytest -q"],
                    "evidence_paths": ["evidence.md"],
                    "test_plan": ["pytest -q"],
                    "allowed_operation_level": "L0",
                    "human_approval_required": False,
                    "metadata": {},
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        ret = cmd_task_done(omo_dir, "IMPORTED-test1")
        assert ret == 0
        assert not (planned_dir / "IMPORTED-test1.yaml").exists()
        dst = omo_dir / "tasks" / "done" / "IMPORTED-test1.yaml"
        assert dst.exists()
        payload = yaml.safe_load(dst.read_text(encoding="utf-8"))
        assert payload["status"] == "done"
        assert payload["completed_at"]
        assert payload["metadata"]["completed_at"]
        assert payload["metadata"]["completed_via"] == "omo task done"
        artifact = (
            omo_dir.parent / "runtime" / "omo" / "_delivery" / "ingress" / "tasks"
        )
        assert list(artifact.glob("IMPORTED-test1-done-*.yaml"))
        captured = capsys.readouterr()
        assert "归档完成" in captured.out

    def test_cmd_task_done_not_found(self, capsys, tmp_path: Path) -> None:
        """未找到任务 → 返回 1."""
        ret = cmd_task_done(tmp_path, "NOPE-xxxx")
        assert ret == 1
        captured = capsys.readouterr()
        assert "未找到" in captured.out

    def test_cmd_task_refresh_evidence_updates_done_task(
        self, capsys, tmp_path: Path
    ) -> None:
        omo_dir = tmp_path
        done_dir = omo_dir / "tasks" / "done"
        done_dir.mkdir(parents=True)
        (omo_dir / "evidence.md").write_text("# evidence\n", encoding="utf-8")
        (done_dir / "TASK-DONE-1.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "TASK-DONE-1",
                    "title": "刷新 evidence",
                    "status": "done",
                    "task_type": "feature",
                    "risk_level": "L0",
                    "depends_on": [],
                    "source_docs": ["spec.md"],
                    "deliverables": ["代码"],
                    "assigned_to": None,
                    "dispatch_id": None,
                    "run_ref": None,
                    "approval_ref": None,
                    "review_ref": None,
                    "knowledge_refs": [],
                    "handoff_refs": [],
                    "entry_gate": [],
                    "evidence_required": ["pytest -q"],
                    "evidence_paths": ["missing.md"],
                    "test_plan": ["pytest -q"],
                    "allowed_operation_level": "L0",
                    "human_approval_required": False,
                    "metadata": {},
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        ret = cmd_task_refresh_evidence(
            omo_dir,
            task_id="TASK-DONE-1",
            evidence_paths=["evidence.md"],
            source_ref="tests:refresh-evidence",
        )

        assert ret == 0
        payload = yaml.safe_load(
            (done_dir / "TASK-DONE-1.yaml").read_text(encoding="utf-8")
        )
        assert payload["evidence_paths"] == ["evidence.md"]
        assert (
            payload["metadata"]["evidence_paths_refresh_source_ref"]
            == "tests:refresh-evidence"
        )
        artifacts = list(
            (
                omo_dir.parent / "runtime" / "omo" / "_delivery" / "ingress" / "tasks"
            ).glob("TASK-DONE-1-evidence-refresh-*.yaml")
        )
        assert len(artifacts) == 1
        captured = capsys.readouterr()
        assert "evidence_paths 已刷新" in captured.out


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

    def test_cmd_evidence_list_prefers_legacy_when_modern_empty(
        self, capsys, tmp_path: Path
    ) -> None:
        omo_dir = tmp_path
        modern = omo_dir / "_delivery" / "evidence"
        modern.mkdir(parents=True)
        legacy_phase = omo_dir / "_delivery" / "evidence-legacy" / "phase15"
        legacy_phase.mkdir(parents=True)
        (legacy_phase / "report.md").write_text("# Legacy Report")

        ret = cmd_evidence_list(omo_dir, "phase15")

        assert ret == 0
        captured = capsys.readouterr()
        assert "report.md" in captured.out
        assert "legacy-alias" in captured.out


class TestOmoLocator:
    def test_find_omo_dir_prefers_workspace_root_over_subrepo_shadow(self) -> None:
        start = Path(__file__).resolve().parents[1]
        assert (start / ".omo").is_dir()
        assert find_omo_dir(start) == OMO_ROOT
