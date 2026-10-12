"""Integration test for family QuestBoard and eCOS points calculation workflow.

Validates the full E2E loop:
1. REST API Quest creation and OMO planned task persistence.
2. REST API Quest completion, OMO task promotion to done, and event emission.
3. eCOS Event listener matching and point calculation workflow SQLite execution.
"""

from __future__ import annotations

# 2026-10-12: 此测试连真 family-hub DB + 真 ecos 事件总线, 是手动 E2E;
# 曾在全量跑里 poll 死 socket 挂死 22h (0% CPU)。默认跳过, 显式 RUN_E2E=1 才跑。
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="手动 E2E (真 DB + 真事件总线): RUN_E2E=1 uv run pytest tests/integration/test_quest_points_e2e.py",
)

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Resolve workspace paths
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT / "projects" / "cockpit" / "src"))
sys.path.insert(0, str(WORKSPACE_ROOT / "projects" / "ecos" / "src"))
sys.path.insert(0, str(WORKSPACE_ROOT / "projects" / "omo" / "src"))
sys.path.insert(0, str(WORKSPACE_ROOT / "projects" / "bus-foundation" / "src"))

def test_quest_e2e_flow():
    # 强行清除已加载的 ecos 缓存以防 sys.modules 错配
    for mod in list(sys.modules.keys()):
        if mod == "ecos" or mod.startswith("ecos."):
            del sys.modules[mod]

    from cockpit.dashboard_server import app
    from fastapi.testclient import TestClient

    db_path = WORKSPACE_ROOT / "projects" / "ecos" / "projects" / "family-hub" / "family_hub.db"
    if not db_path.exists():
        pytest.skip(f"family-hub DB not found: {db_path}")
    client = TestClient(app)

    # 1. 查询现有任务与积分，记录初始值
    response = client.get("/api/omos/quests")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

    # 找到 "child" (宝宝) 初始的 points
    initial_wisdom = 0
    initial_responsibility = 0
    for profile in data["profiles"]:
        if profile["role"] == "child":
            initial_wisdom = profile["wisdomPoints"]
            initial_responsibility = profile["responsibilityPoints"]

    # 2. 新增一个 "responsibility" 类型 Quest
    response = client.post(
        "/api/omos/quests",
        params={
            "title": "测试每日打扫",
            "q_type": "responsibility",
            "reward": 20,
            "assignee": "child",
        },
    )
    assert response.status_code == 200
    create_res = response.json()
    assert create_res["status"] == "ok"
    quest_id = create_res["quest_id"]
    task_id = create_res["task_id"]
    assert task_id == f"QUEST-{quest_id}"

    # 验证 OMO planned/ 目录下确实产生了该任务
    task_file = WORKSPACE_ROOT / ".omo" / "tasks" / "planned" / f"{task_id}.yaml"
    assert task_file.exists()

    # 3. 标记该 Quest 完成，并捕获事件发送
    with patch("bus_foundation.facade.event.publish") as mock_publish:
        response = client.post(f"/api/omos/quests/{quest_id}/complete")
        assert response.status_code == 200
        complete_res = response.json()
        assert complete_res["status"] == "ok"
        assert complete_res["event_published"] is True

        # 验证 OMO 任务已被 complete
        done_task_file = WORKSPACE_ROOT / ".omo" / "tasks" / "done" / f"{task_id}.yaml"
        assert not task_file.exists() or done_task_file.exists()

        # 验证 QuestCompleted 事件是否被发布
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[1]
        assert call_args["topic"] == "QuestCompleted"
        payload = call_args["payload"]
        assert payload["quest_id"] == quest_id
        assert payload["assignee"] == "child"
        assert payload["reward"] == 20
        assert payload["type"] == "responsibility"

    # 4. 模拟 eCOS Event Listener 接收该事件，并拉起工作流清算
    from ecos.workflow.event_listener import execute_matched

    # 构造事件
    event = {
        "bos_uri": "QuestCompleted",
        "source": "QuestCompleted",
        "payload": {
            "quest_id": quest_id,
            "task_id": task_id,
            "assignee": "child",
            "reward": 20,
            "type": "responsibility",
        },
    }

    results = execute_matched(event)
    assert len(results) >= 1
    # 确认工作流没有失败的步骤
    print("Workflow results details:", results[0])
    assert results[0]["failed"] == 0
    assert results[0]["passed"] == 1

    # 5. 验证 SQLite 数据库积分已累加
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT responsibilityPoints FROM profiles WHERE role = 'child'")
    final_responsibility = cursor.fetchone()[0]

    cursor.execute("SELECT completed FROM quests WHERE id = ?", (quest_id,))
    quest_completed_status = cursor.fetchone()[0]
    conn.close()

    assert quest_completed_status == 1
    assert final_responsibility == initial_responsibility + 20
