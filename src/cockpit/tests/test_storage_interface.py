"""验证 IDataAccess 接口和 SQLiteDataAccess 实现。"""

from cockpit.storage import IDataAccess, SQLiteDataAccess, get_data_access, set_data_access


class TestDataAccessInterface:
    def test_protocol_is_runtime_checkable(self):
        assert isinstance(SQLiteDataAccess(), IDataAccess)

    def test_set_data_access_injects_mock(self):
        class MockDataAccess:
            def save_research(self, topic="", summary="", full_text="", source_count=0, agent=""):
                return 999

            def add_follow_up(self, research_id=0, question="", answer=""):
                pass

            def list_research(self, limit=10, include_quarantined=False, include_archived=False):
                return []

            def search_research(self, keyword="", limit=10):
                return []

            def get_research(self, research_id=0):
                return None

            def set_research_tags(self, research_id=0, tags=None):
                return []

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

        orig = get_data_access()
        set_data_access(MockDataAccess())  # type: ignore[arg-type]
        try:
            da = get_data_access()
            assert da.save_research(topic="test", summary="test summary") == 999
            assert da.list_research() == []
            assert da.get_research(42) is None
        finally:
            # Reset to original
            set_data_access(orig)  # type: ignore[arg-type]
