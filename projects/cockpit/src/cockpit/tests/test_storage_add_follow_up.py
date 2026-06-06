from __future__ import annotations

from pathlib import Path

from cockpit import storage


def test_add_follow_up_appends_correctly(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")

    rid = storage.save_research("topic", "summary", "body", source_count=1)

    storage.add_follow_up(rid, "追问一?", "这是答案一")
    storage.add_follow_up(rid, "追问二?", "这是答案二")

    record = storage.get_research(rid)
    assert record is not None
    assert len(record["follow_ups"]) == 2
    assert record["follow_ups"][0]["question"] == "追问一?"
    assert record["follow_ups"][0]["answer"] == "这是答案一"
    assert record["follow_ups"][1]["question"] == "追问二?"
    assert record["follow_ups"][1]["answer"] == "这是答案二"


def test_add_follow_up_nonexistent_research_does_not_raise(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")

    # 对不存在的研究 ID 调用，不应抛出异常
    storage.add_follow_up(9999, "question?", "answer.")
