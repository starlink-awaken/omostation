import json
import sqlite3
import sys
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _create_research_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE research (
            id INTEGER PRIMARY KEY,
            topic TEXT NOT NULL,
            summary TEXT,
            source_count INTEGER DEFAULT 0,
            created_at REAL NOT NULL,
            follow_ups TEXT DEFAULT '[]',
            quarantined_at REAL,
            quarantine_reason TEXT,
            tags TEXT DEFAULT '[]',
            archived_at REAL,
            archive_reason TEXT,
            full_text TEXT DEFAULT '',
            agent TEXT DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        INSERT INTO research (topic, summary, created_at, tags, full_text, agent)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "OPC 路线图收口方案",
            "补齐 P5 P6 P7 的证据与实现",
            1718080000.0,
            '["opc", "roadmap"]',
            "OPC 路线图包括 P5 场景 P6 loop P7 release train",
            "opc-agent",
        ),
    )
    conn.commit()
    conn.close()


def _create_cards_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE cards (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            title TEXT NOT NULL,
            domain TEXT NOT NULL,
            priority TEXT NOT NULL,
            summary TEXT DEFAULT '',
            content TEXT DEFAULT '',
            parent_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deadline TEXT,
            review_due TEXT,
            tags TEXT DEFAULT '[]',
            extra TEXT DEFAULT '{}'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO cards (id, type, status, title, domain, priority, summary, content, created_at, updated_at, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "TASK-FAMILY-001",
            "task",
            "open",
            "奶奶血压复查安排",
            "family",
            "P1",
            "安排本周复查并准备历史记录",
            "关注血压波动和用药",
            "2026-06-01T00:00:00Z",
            "2026-06-12T00:00:00Z",
            '["family", "health"]',
        ),
    )
    conn.commit()
    conn.close()


def test_work_assistant_uses_research_sources_and_archives(tmp_path, monkeypatch, capsys):
    from cockpit.commands import scenario

    research_db = tmp_path / "research.db"
    _create_research_db(research_db)
    monkeypatch.setattr(scenario, "_research_db_path", lambda: research_db)
    monkeypatch.setattr(scenario, "_workspace_root", lambda: tmp_path)

    args = Namespace(scenario_sub="assistant", query="OPC 路线图", limit=10)
    rc = scenario.cmd_scenario(args)
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["source_count"] >= 1
    assert payload["sources"][0]["source"] == "cockpit:research"
    archive_path = Path(payload["archive_path"])
    assert archive_path.exists()
    archived = json.loads(archive_path.read_text(encoding="utf-8"))
    assert archived["query"] == "OPC 路线图"


def test_family_health_falls_back_to_cards_db(tmp_path, monkeypatch):
    from cockpit.commands import scenario

    documents_db = tmp_path / "data" / "驾驶舱" / "documents.db"
    documents_db.parent.mkdir(parents=True, exist_ok=True)
    documents_db.touch()
    cards_db = tmp_path / "data" / "cards" / "cards.db"
    _create_cards_db(cards_db)
    monkeypatch.setattr(scenario, "_workspace_root", lambda: tmp_path)

    payload = scenario._f3_family_health(query="奶奶血压复查要准备什么")
    assert payload["privacy_class"] == "confidential"
    assert payload["source_count"] >= 1
    assert payload["sources"][0]["source"] == "cards:family"
    assert payload["next_action"]["level"] == "attention"


def test_workspace_root_auto_detects_repo_root(tmp_path, monkeypatch):
    from cockpit.commands import scenario

    (tmp_path / ".omo").mkdir()
    nested = tmp_path / "projects" / "cockpit"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.delenv("WORKSPACE", raising=False)

    assert scenario._workspace_root() == tmp_path
