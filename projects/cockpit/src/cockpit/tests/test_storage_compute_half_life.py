from __future__ import annotations

from pathlib import Path

from cockpit import storage


def _approx(a: float, b: float, epsilon: float = 0.02) -> bool:
    return abs(a - b) <= epsilon


def test_compute_half_life_no_record(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")
    result = storage.compute_half_life(9999)

    assert result["decay"] == 0.0
    assert result["half_life_days"] == 14
    assert result["days_since_active"] == 999


def test_compute_half_life_fresh_record_no_events(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")
    rid = storage.save_research("fresh topic", "summary", "body", source_count=1)

    result = storage.compute_half_life(rid)

    # 刚创建的记录 days_since ≈ 0 → decay ≈ 1.0
    assert _approx(result["decay"], 1.0)
    assert result["half_life_days"] == 14
    assert result["follow_up_count"] == 0
    assert result["published_count"] == 0


def test_compute_half_life_with_follow_up(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")
    rid = storage.save_research("topic", "summary", "body", source_count=1)
    storage.add_follow_up(rid, "追问?", "回答")

    result = storage.compute_half_life(rid)

    # 有追问 → follow_up_count = 1
    assert _approx(result["decay"], 1.0)
    assert result["follow_up_count"] == 1
    assert result["published_count"] == 0


def test_compute_half_life_with_published(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")
    rid = storage.save_research("topic", "summary", "body", source_count=1)
    storage.save_published_report(rid, "brief", "/tmp/report.md")

    result = storage.compute_half_life(rid)

    assert _approx(result["decay"], 1.0)
    assert result["follow_up_count"] == 0
    assert result["published_count"] == 1


def test_compute_half_life_follow_up_and_published(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")
    rid = storage.save_research("topic", "summary", "body", source_count=1)
    storage.add_follow_up(rid, "追问?", "回答")
    storage.save_published_report(rid, "memo", "/tmp/memo.md")

    result = storage.compute_half_life(rid)

    assert result["follow_up_count"] == 1
    assert result["published_count"] == 1


def test_compute_half_life_formula_verification(monkeypatch, tmp_path: Path):
    """验证半衰期核心公式 decay = 2^(-days_since / 14)。"""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")

    # 创建记录后，用已知的 created_at 替换来验证公式
    rid = storage.save_research("topic", "summary", "body", source_count=1)

    # 通过 raw SQL 将 created_at 改为 14 天前（模拟 14 天无活动）
    import sqlite3

    conn = sqlite3.connect(str(tmp_path / "data.db"))
    cursor = conn.execute("SELECT created_at FROM research WHERE id = ?", (rid,))
    fourteen_days_ago = cursor.fetchone()[0] - 14 * 86400
    conn.execute("UPDATE research SET created_at = ? WHERE id = ?", (fourteen_days_ago, rid))
    conn.commit()
    conn.close()

    result = storage.compute_half_life(rid)
    expected_decay = 2 ** (-14 / 14)  # = 0.5

    # 无追问/无发布，理论值应为 0.5
    assert _approx(result["decay"], expected_decay, epsilon=0.05)
    assert _approx(result["days_since_active"], 14.0, epsilon=1.0)
