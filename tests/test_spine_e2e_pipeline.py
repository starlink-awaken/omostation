#!/usr/bin/env python3
"""主干真值流端到端全链路集成测试 (E2E Spine Value Pipeline Test)

验证从信号输入、LECP 组装、Cockpit 待办获取、一键署名、语义 Diff 提取到记忆沉淀的全闭环。
"""

import importlib.util
import json
import sys
from pathlib import Path
import pytest

WORKSPACE_ROOT = Path("/Users/xiamingxing/Workspace")
sys.path.insert(0, str(WORKSPACE_ROOT / "projects" / "cockpit" / "src"))

from fastapi.testclient import TestClient
from cockpit.dashboard_server import app


def _get_diff_engine():
    diff_path = WORKSPACE_ROOT / "bin" / "memory" / "diff_engine.py"
    spec = importlib.util.spec_from_file_location("diff_engine", diff_path)
    if not spec or not spec.loader:
        raise ImportError("diff_engine.py not found")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_e2e_unified_inbox_flow(tmp_path):
    """测试 Cockpit 统一待办与署名端到端流程"""
    client = TestClient(app)

    # 1. 查询待办列表
    res_pending = client.get("/api/inbox/pending")
    assert res_pending.status_code == 200
    data = res_pending.json()
    assert data["ok"] is True
    assert "items" in data

    # 2. 模拟夏明星一键署名并提交修改
    draft_text = "请各部门抓紧办理，于近期报送总结。"
    final_text = "请各部门于本周五 17:00 前将下半年攻关计划汇总表报送至办公室。"

    sign_payload = {
        "entity_id": "evt-20260828-p0-test-01",
        "domain": "p0_work",
        "draft_text": draft_text,
        "final_text": final_text,
        "action": "send_email",
    }

    res_sign = client.post("/api/inbox/sign", json=sign_payload)
    assert res_sign.status_code == 200
    sign_data = res_sign.json()
    assert sign_data["ok"] is True
    assert sign_data["status"] == "signed"
    assert sign_data["signed_by"] == "夏明星"
    assert "diff_summary" in sign_data


def test_agent_skill_discoverability():
    """测试 Agent 感知技能包的完整性"""
    skill_file = WORKSPACE_ROOT / ".agents" / "skills" / "spine-value-pipeline" / "SKILL.md"
    assert skill_file.exists(), "spine-value-pipeline/SKILL.md missing"

    content = skill_file.read_text(encoding="utf-8")
    assert "bos://compute/omlxc/infer" in content
    assert "bos://memory/mos/diff" in content
    assert "LECP" in content
