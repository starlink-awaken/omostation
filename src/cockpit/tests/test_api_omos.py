from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web.api_omos import router


@pytest.fixture
def temp_env(tmp_path, monkeypatch):
    # 创建虚假的仓库根目录以重定向 db 和 cards 物理路径
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()

    db_dir = fake_repo / "projects" / "family-hub"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "family_hub.db"

    # 初始化 sqlite3 数据库和表
    with closing(sqlite3.connect(str(db_path))) as conn:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    type TEXT,
                    reward INTEGER,
                    completed INTEGER,
                    assignee TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    role TEXT PRIMARY KEY,
                    name TEXT,
                    level INTEGER,
                    wisdomPoints INTEGER,
                    responsibilityPoints INTEGER,
                    inventory TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT,
                    type TEXT,
                    timestamp TEXT
                )
            """)
            # 插入一些测试基础数据
            cursor.execute(
                "INSERT INTO profiles (role, name, level, wisdomPoints, responsibilityPoints) VALUES ('parent', 'Dad', 1, 0, 0)"
            )
            cursor.execute(
                "INSERT INTO quests (title, type, reward, completed, assignee) VALUES ('Test Base Quest', 'wisdom', 50, 0, 'parent')"
            )

    # 替换 api_omos 模块中的 _REPO_ROOT 变量
    monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", fake_repo)

    # 同时模拟 cockpit_mcp 中的 _CARDS_DIR 为临时测试路径
    fake_cards_dir = tmp_path / "CARDS"
    fake_cards_dir.mkdir()
    monkeypatch.setattr("cockpit.scripts.cockpit_mcp._CARDS_DIR", fake_cards_dir)

    # 模拟外部 omo 交互操作为 no-op
    monkeypatch.setattr("omo.omo_ingress.create_planned_task", lambda *args, **kwargs: None)
    monkeypatch.setattr("omo.omo_ingress.complete_task", lambda *args, **kwargs: None)

    return {"db_path": db_path, "fake_cards_dir": fake_cards_dir, "fake_repo": fake_repo}


def test_get_quests(temp_env):
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/api/omos/quests")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    # 应包含我们的 Test Base Quest
    assert any(q["title"] == "Test Base Quest" for q in data["quests"])
    assert data["profiles"][0]["role"] == "parent"


def test_create_quest(temp_env):
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post("/api/omos/quests?title=NewTask&q_type=wisdom&reward=120&assignee=parent")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "quest_id" in data

    # 验证是否成功落库
    with closing(sqlite3.connect(str(temp_env["db_path"]))) as conn:
        cursor = conn.cursor()
        quest = cursor.execute("SELECT * FROM quests WHERE title = 'NewTask'").fetchone()
        assert quest is not None
        assert quest[3] == 120  # reward


def test_complete_base_quest(temp_env):
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # 查出 Quest ID
    with closing(sqlite3.connect(str(temp_env["db_path"]))) as conn:
        cursor = conn.cursor()
        quest_id = cursor.execute("SELECT id FROM quests WHERE title = 'Test Base Quest'").fetchone()[0]

    response = client.post(f"/api/omos/quests/{quest_id}/complete")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # 验证已标记为已完成且 parent 获得了对应的 50 积分
    with closing(sqlite3.connect(str(temp_env["db_path"]))) as conn:
        cursor = conn.cursor()
        quest = cursor.execute("SELECT completed FROM quests WHERE id = ?", (quest_id,)).fetchone()
        assert quest[0] == 1
        profile = cursor.execute("SELECT wisdomPoints FROM profiles WHERE role = 'parent'").fetchone()
        assert profile[0] == 50


def test_complete_card_quest_frontmatter_safety(temp_env, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # Mock _scan_cards 返回一张卡片。为了让 quest_id = 99910 + (int(digits) % 1000) 处于 [99910, 100000) 之间，
    # 我们将 id 设为 DEBT-007，这样 quest_id = 99917
    test_card = {"id": "DEBT-007", "title": "测试债务卡片", "priority": "P1", "status": "todo"}
    monkeypatch.setattr("cockpit.scripts.cockpit_mcp._scan_cards", lambda: [test_card])

    # 在 fake_cards_dir 下创建卡片的 Markdown 并填入混合了 status: todo 的正文
    card_md = temp_env["fake_cards_dir"] / "DEBT-007.md"
    card_content = (
        "---\n"
        "id: DEBT-007\n"
        "title: 测试债务卡片\n"
        "priority: P1\n"
        "status: todo\n"
        "---\n\n"
        "# 详情描述\n"
        "这是一个需要处理的卡片，在示例中有 status: todo 字样，它不应该被误杀改写为 done。\n"
    )
    card_md.write_text(card_content, encoding="utf-8")

    # 触发完成 API
    response = client.post("/api/omos/quests/99917/complete")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # 验证 markdown 文件的状态改变与内容安全性
    updated_content = card_md.read_text(encoding="utf-8")

    # Frontmatter 中的 status 应该变成 done
    assert "status: done" in updated_content
    # 正文中的 status: todo 应该完好无损，说明正则只作用于首部 Frontmatter
    assert "示例中有 status: todo 字样" in updated_content
