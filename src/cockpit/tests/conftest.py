"""Pytest配置 — 为 CLI 测试提供 MockDataAccess 自动重置。"""

import sys
from pathlib import Path

# 确保 cockpit/ 的父目录在 sys.path 中（from cockpit.xxx import ...）
# cockpit 是一个包（有 __init__.py），所以需要它的父目录在 sys.path 中
_project_root = str(Path(__file__).resolve().parent.parent)  # cockpit/
_parent_dir = str(Path(__file__).resolve().parent.parent.parent)  # ~/Workspace/
for p in [_project_root, _parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

from cockpit.storage import set_data_access


class MockDataAccess:
    """通用测试用 Mock。测试可按需覆盖具体方法属性。"""

    def save_research(self, topic="", summary="", full_text="", source_count=0, agent=""):
        return 42

    def add_follow_up(self, research_id=0, question="", answer=""):
        pass

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


@pytest.fixture(autouse=True)
def _reset_data_access():
    """每次测试后重置 data_access，避免状态泄漏。"""
    yield
    # 重置为 None 以便下次 get_data_access() 重新创建 SQLiteDataAccess
    set_data_access(None)  # type: ignore[arg-type]
