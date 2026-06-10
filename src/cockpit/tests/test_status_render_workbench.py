"""_render_workbench() 分支全覆盖测试。"""

from __future__ import annotations

import argparse
import io
import sqlite3
import time
from pathlib import Path

from rich.console import Console

from cockpit.commands import base as B  # noqa: N812
from cockpit.commands import status as S  # noqa: N812

# ── 保存原函数引用（避免递归）──
_ORIG_STATUS_SERVICES = B._status_services
_ORIG_HTTP_HEALTH = B._http_health
_ORIG_FIND_CLI = B._find_cli


def _make_research(
    rid: int,
    topic: str = "测试研究",
    source_count: int = 3,
    follow_ups: list | None = None,
    archived_at: float | None = None,
    created_at: float | None = None,
) -> dict:
    return {
        "id": rid,
        "topic": topic,
        "source_count": source_count,
        "follow_ups": follow_ups or [],
        "archived_at": archived_at,
        "created_at": created_at or (time.time() - 1),
    }


def _make_research_da(
    records: list[dict],
    half_life_map: dict[int, dict] | None = None,
):
    hl_map = half_life_map or {}

    class _MockDA:
        def list_research(self, limit=10, **kw):
            return records[:limit]

        def compute_half_life(self, rid):
            return hl_map.get(
                rid,
                {
                    "decay": 0.8,
                    "half_life_days": 14,
                    "days_since_active": 2.0,
                    "follow_up_count": 0,
                    "published_count": 0,
                },
            )

        def get_research_timeline(self, rid):
            return [{"created_at": str(time.time()), "event_type": "created", "description": "初始创建"}]

    return _MockDA()


def _capture_console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    c = Console(file=buf, force_terminal=False, width=120)
    return c, buf


def _create_workbench_db(tmp_path: Path, active_count: int = 0, archived_count: int = 0, quarantined_count: int = 0):
    """在 tmp_path/.workspace/data.db 中创建测试数据库。"""
    db_dir = tmp_path / ".workspace"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "data.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS research ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "topic TEXT, summary TEXT, full_text TEXT,"
        "source_count INTEGER DEFAULT 0,"
        "follow_ups TEXT DEFAULT '[]',"
        "archived_at REAL,"
        "quarantined_at REAL,"
        "created_at REAL DEFAULT (strftime('%s','now')),"
        "agent TEXT"
        ")"
    )
    for i in range(active_count):
        conn.execute("INSERT INTO research (topic, source_count) VALUES (?, ?)", (f"Active Study {i}", 2))
    for i in range(archived_count):
        conn.execute(
            "INSERT INTO research (topic, source_count, archived_at) VALUES (?, ?, ?)",
            (f"Archived Study {i}", 1, time.time() - 86400),
        )
    for i in range(quarantined_count):
        conn.execute(
            "INSERT INTO research (topic, source_count, quarantined_at) VALUES (?, ?, ?)",
            (f"Quarantined Study {i}", 1, time.time() - 86400),
        )
    conn.commit()
    conn.close()
    return db_path


# ── 测试用例 ──


def test_empty_workbench_no_research_no_services(monkeypatch):
    """无研究、无服务 → 空空如也 + 全部离线。"""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    monkeypatch.setattr(B, "_status_services", lambda: [])
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: False)
    monkeypatch.setattr(B, "_find_cli", lambda name: None)
    monkeypatch.setattr(B, "_get_data_access", lambda: _make_research_da([]))

    S._render_workbench()
    output = buf.getvalue()
    assert "工作台" in output


def test_workbench_all_healthy_with_research(monkeypatch):
    """全部服务正常 + 有研究数据。"""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    monkeypatch.setattr(B, "_status_services", lambda: _ORIG_STATUS_SERVICES())
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: True)
    monkeypatch.setattr(B, "_find_cli", lambda name: name)

    records = [
        _make_research(1, "Transformers", source_count=5),
        _make_research(2, "Attention Is All You Need", source_count=3),
    ]
    monkeypatch.setattr(B, "_get_data_access", lambda: _make_research_da(records))
    S._render_workbench()
    output = buf.getvalue()
    assert "全部正常" in output
    assert "Transformers" in output


def test_workbench_partial_services(monkeypatch):
    """部分服务异常 → 🟡 部分异常。"""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    monkeypatch.setattr(B, "_status_services", lambda: _ORIG_STATUS_SERVICES())

    call_count = [0]

    def _mock_http(url, timeout=3.0):
        call_count[0] += 1
        return call_count[0] == 1  # only first service is healthy

    monkeypatch.setattr(B, "_http_health", _mock_http)
    monkeypatch.setattr(B, "_find_cli", lambda name: name)
    monkeypatch.setattr(B, "_get_data_access", lambda: _make_research_da([]))
    S._render_workbench()
    output = buf.getvalue()
    assert "🟡" in output or "部分异常" in output


def test_workbench_all_offline(monkeypatch):
    """全部离线 → 🔴 全部离线。"""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    monkeypatch.setattr(B, "_status_services", lambda: _ORIG_STATUS_SERVICES())
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: False)
    monkeypatch.setattr(B, "_find_cli", lambda name: None)
    monkeypatch.setattr(B, "_get_data_access", lambda: _make_research_da([]))
    S._render_workbench()
    output = buf.getvalue()
    assert "全部离线" in output or "🔴" in output


def test_workbench_cycle_mode(monkeypatch):
    """带 cycle 参数 → 显示刷新次数。"""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    monkeypatch.setattr(B, "_status_services", lambda: _ORIG_STATUS_SERVICES())
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: True)
    monkeypatch.setattr(B, "_find_cli", lambda name: name)
    monkeypatch.setattr(B, "_get_data_access", lambda: _make_research_da([]))
    S._render_workbench(cycle=3, interval=5.0)
    output = buf.getvalue()
    assert "第 3 次刷新" in output
    assert "5" in output


def test_workbench_half_life_labels(monkeypatch):
    """半衰期三级标签：荒废 / 需保鲜 / 活跃。"""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    monkeypatch.setattr(B, "_status_services", lambda: [])
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: False)
    monkeypatch.setattr(B, "_find_cli", lambda name: None)

    records = [
        _make_research(1, "Hot Topic"),
        _make_research(2, "Warm Topic"),
        _make_research(3, "Cold Topic"),
    ]
    hl_map = {
        1: {"decay": 0.9, "half_life_days": 2, "days_since_active": 0.5, "follow_up_count": 2, "published_count": 1},
        2: {"decay": 0.4, "half_life_days": 11, "days_since_active": 6.0, "follow_up_count": 0, "published_count": 0},
        3: {"decay": 0.1, "half_life_days": 42, "days_since_active": 30.0, "follow_up_count": 0, "published_count": 0},
    }
    monkeypatch.setattr(B, "_get_data_access", lambda: _make_research_da(records, hl_map))
    S._render_workbench()
    output = buf.getvalue()
    assert "活跃" in output
    assert "需保鲜" in output or "荒废" in output


def test_recommendation_h1_active_zero(monkeypatch, tmp_path):
    """推荐 H1：active_count == 0 → 开始第一个研究。"""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    monkeypatch.setattr(B, "_status_services", lambda: [])
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: False)
    monkeypatch.setattr(B, "_find_cli", lambda name: None)
    monkeypatch.setattr(B, "_get_data_access", lambda: _make_research_da([]))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)  # 确保 SQLite DB 不存在 → active_count=0
    S._render_workbench()
    output = buf.getvalue()
    assert "开始你的第一个研究" in output or "发起第一个研究" in output


def test_recommendation_h2_active_one(monkeypatch, tmp_path):
    """推荐 H2：active_count == 1 → 继续唯一研究。"""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    services = list(_ORIG_STATUS_SERVICES()[:1])
    monkeypatch.setattr(B, "_status_services", lambda: services)
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: True)
    monkeypatch.setattr(B, "_find_cli", lambda name: name)

    # 创建带 1 条活跃研究的数据库
    _create_workbench_db(tmp_path, active_count=1)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    records = [_make_research(1, "My Single Study")]
    monkeypatch.setattr(B, "_get_data_access", lambda: _make_research_da(records))
    S._render_workbench()
    output = buf.getvalue()
    assert "继续" in output or "--open" in output


def test_recommendation_h3_active_many(monkeypatch, tmp_path):
    """推荐 H3：active_count > 1 → 浏览所有活跃研究。"""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    services = list(_ORIG_STATUS_SERVICES()[:1])
    monkeypatch.setattr(B, "_status_services", lambda: services)
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: True)
    monkeypatch.setattr(B, "_find_cli", lambda name: name)

    # 创建带 3 条活跃研究的数据库
    _create_workbench_db(tmp_path, active_count=3)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    records = [
        _make_research(1, "Study Alpha"),
        _make_research(2, "Study Beta"),
        _make_research(3, "Study Gamma"),
    ]
    monkeypatch.setattr(B, "_get_data_access", lambda: _make_research_da(records))
    S._render_workbench()
    output = buf.getvalue()
    assert "浏览所有活跃研究" in output or "--list" in output


def test_workbench_no_research_table(monkeypatch):
    """无研究 → 显示空工作台提示。"""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    monkeypatch.setattr(B, "_status_services", lambda: _ORIG_STATUS_SERVICES())
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: True)
    monkeypatch.setattr(B, "_find_cli", lambda name: name)
    monkeypatch.setattr(B, "_get_data_access", lambda: _make_research_da([]))
    S._render_workbench()
    output = buf.getvalue()
    assert "工作台空空如也" in output or "开始你的第一个研究" in output


def test_workbench_archived_research(monkeypatch):
    """已归档研究 → 📦 已归档标签。"""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    monkeypatch.setattr(B, "_status_services", lambda: [])
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: False)
    monkeypatch.setattr(B, "_find_cli", lambda name: None)

    records = [
        _make_research(1, "Archived Study", archived_at=time.time() - 86400),
    ]
    monkeypatch.setattr(B, "_get_data_access", lambda: _make_research_da(records))
    S._render_workbench()
    output = buf.getvalue()
    assert "已归档" in output


def test_sqlite_error_in_workbench(monkeypatch, tmp_path):
    """SQLite DB 损坏 → sqlite3.Error 被静默处理 (lines 81-82)."""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    monkeypatch.setattr(B, "_status_services", lambda: [])
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: False)
    monkeypatch.setattr(B, "_find_cli", lambda name: None)
    monkeypatch.setattr(B, "_get_data_access", lambda: _make_research_da([]))
    # 创建损坏的 SQLite 文件
    db_dir = tmp_path / ".workspace"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "data.db"
    db_path.write_text("not a valid sqlite database")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    S._render_workbench()
    output = buf.getvalue()
    # 虽然 DB 损坏，工作台仍应正常渲染
    assert "工作台" in output


def test_days_since_ge_7_shows_archivable_badge(monkeypatch):
    """days_since >= 7 → 可归档标签 (line 127)."""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    monkeypatch.setattr(B, "_status_services", lambda: [])
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: False)
    monkeypatch.setattr(B, "_find_cli", lambda name: None)

    old_time = time.time() - 10 * 86400  # 10 天前
    records = [_make_research(1, "Old Study", created_at=old_time)]

    class _OldTimelineDA:
        def list_research(self, limit=10, **kw):
            return records[:limit]

        def compute_half_life(self, rid):
            return {
                "decay": 0.8,
                "half_life_days": 14,
                "days_since_active": 2.0,
                "follow_up_count": 0,
                "published_count": 0,
            }

        def get_research_timeline(self, rid):
            return [{"created_at": str(old_time), "event_type": "created", "description": "初始创建"}]

    monkeypatch.setattr(B, "_get_data_access", lambda: _OldTimelineDA())
    S._render_workbench()
    output = buf.getvalue()
    assert "可归档" in output


def test_days_since_ge_3_shows_freshness_badge(monkeypatch):
    """days_since >= 3 且 < 7 → 待保鲜标签 (line 129)."""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    monkeypatch.setattr(B, "_status_services", lambda: [])
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: False)
    monkeypatch.setattr(B, "_find_cli", lambda name: None)

    mid_time = time.time() - 5 * 86400  # 5 天前
    records = [_make_research(2, "Mid Study", created_at=mid_time)]

    class _MidTimelineDA:
        def list_research(self, limit=10, **kw):
            return records[:limit]

        def compute_half_life(self, rid):
            return {
                "decay": 0.6,
                "half_life_days": 10,
                "days_since_active": 1.0,
                "follow_up_count": 0,
                "published_count": 0,
            }

        def get_research_timeline(self, rid):
            return [{"created_at": str(mid_time), "event_type": "created", "description": "初始创建"}]

    monkeypatch.setattr(B, "_get_data_access", lambda: _MidTimelineDA())
    S._render_workbench()
    output = buf.getvalue()
    assert "待保鲜" in output


def test_workbench_service_health_recommendation(monkeypatch):
    """部分服务离线 → 推荐中显示 ⚠️ 提示。"""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    monkeypatch.setattr(B, "_status_services", lambda: _ORIG_STATUS_SERVICES())
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: False)
    monkeypatch.setattr(B, "_find_cli", lambda name: None)
    monkeypatch.setattr(B, "_get_data_access", lambda: _make_research_da([]))
    S._render_workbench()
    output = buf.getvalue()
    assert "服务离线" in output or "全部离线" in output


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_status --json 输出路径
# ═══════════════════════════════════════════════════════════════════════════════


def test_cmd_status_json(monkeypatch):
    """status --json 输出 JSON 格式状态。"""
    c, buf = _capture_console()
    monkeypatch.setattr(B, "_get_console", lambda: c)
    monkeypatch.setattr(B, "_get_err", lambda: c)
    monkeypatch.setattr(
        S,
        "_status_services",
        lambda: [
            ("Agora", ":7430", "agora", "http://localhost:7430/health", "MCP Hub"),
        ],
    )
    monkeypatch.setattr(B, "_http_health", lambda url, timeout=3.0: True)
    monkeypatch.setattr(B, "_find_cli", lambda name: "/usr/local/bin/agora")
    monkeypatch.setattr(B, "_get_data_access", lambda: _make_research_da([]))

    code = S.cmd_status(argparse.Namespace(watch=False, interval=5.0, json=True))

    output = buf.getvalue()
    assert code == 0
    assert '"status": "ok"' in output
    assert '"services"' in output
    assert '"research_stats"' in output
