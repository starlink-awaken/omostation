"""CLI tests for cockpit — argument parsing and command dispatch."""

from __future__ import annotations

from unittest.mock import patch

from cockpit.cli import main
from cockpit.storage import set_data_access


class MockDataAccess:
    """Minimal mock that satisfies get_data_access()."""

    def save_research(self, topic="", summary="", full_text="", source_count=0, agent=""):
        return 42

    def list_research(self, limit=10, include_quarantined=False, include_archived=False):
        return []

    def search_research(self, keyword="", limit=10):
        return []

    def get_research(self, research_id=0):
        return None

    def set_research_tags(self, research_id=0, tags=None):
        return tags or []

    def rename_research(self, research_id=0, new_topic=""):
        return True

    def quarantine_research(self, research_ids=None, reason=""):
        return [], []

    def restore_research(self, research_ids=None):
        return [], []

    def archive_research(self, research_ids=None, reason=""):
        return [], []

    def restore_archived_research(self, research_ids=None):
        return [], []

    def add_follow_up(self, research_id=0, question="", answer=""):
        pass

    def add_research_relations(self, parent_ids=None, child_id=0, relation_type=""):
        pass

    def save_published_report(self, research_id=0, style="", output_path=""):
        return 0

    def get_research_timeline(self, research_id=0):
        return []

    def get_research_dossier(self, research_id=0):
        return None

    def set_research_agent(self, research_id=0, agent_name=""):
        return True

    def compute_half_life(self, research_id=0):
        return {}

    def export_backup(self):
        return {
            "version": 1,
            "exported_at": 0.0,
            "research": [],
            "relations": [],
            "published_reports": [],
            "events": [],
        }

    def import_backup(self, data=None):
        return {"research": 0, "relations": 0, "published_reports": 0, "events": 0, "skipped": 0}

    def set_research_relations(self, *args, **kwargs):
        pass


def _setup_mock():
    set_data_access(MockDataAccess())


def test_help_command():
    """workspace help should return 0."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "help"]):
        rc = main()
    assert rc == 0


def test_demo_command():
    """workspace demo should return 0 with mock data access."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "demo"]):
        rc = main()
    assert rc == 0


def test_status_command():
    """workspace status should return 0 with mock."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "status"]):
        rc = main()
    assert rc == 0


def test_daily_command():
    """workspace daily should return 0 with mock."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "daily"]):
        rc = main()
    assert rc == 0


def test_daily_with_days():
    """workspace daily --days 7 should return 0."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "daily", "--days", "7"]):
        rc = main()
    assert rc == 0


def test_research_list_command():
    """workspace research --list should return 0."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "research", "--list"]):
        rc = main()
    assert rc == 0


def test_research_search_command():
    """workspace research --search keyword should return 0."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "research", "--search", "llm"]):
        rc = main()
    assert rc == 0


def test_research_health_command():
    """workspace research --health should return 0."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "research", "--health"]):
        rc = main()
    assert rc == 0


def test_research_follow_up_command():
    """workspace research --follow-up should return 0."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "research", "--follow-up"]):
        rc = main()
    assert rc == 0


def test_no_command_shows_banner():
    """Running workspace with no args should show welcome banner and return 0."""
    _setup_mock()
    with patch("sys.argv", ["workspace"]):
        rc = main()
    assert rc == 0
