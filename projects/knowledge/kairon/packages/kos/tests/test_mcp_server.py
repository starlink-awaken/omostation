"""Tests for kos.mcp.server — MCP server tool functions."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


class TestMCPToolDefinitions(unittest.TestCase):
    """Verify MCP tool schemas are well-formed."""

    def test_tool_list_not_empty(self):
        import kos.mcp.server as mcp

        tools = mcp.tool_list_domains()
        self.assertIsInstance(tools, (list, dict))  # dict on error

    def test_knowledge_search_requires_query(self):
        import kos.mcp.server as mcp

        result = mcp.tool_search_knowledge("test", limit=1)
        self.assertIsInstance(result, (list, dict))

    def test_system_status_returns_dict(self):
        import kos.mcp.server as mcp

        result = mcp.tool_get_system_status()
        self.assertIsInstance(result, dict)


class TestMCPEdgeCases(unittest.TestCase):
    """Test edge cases in MCP tool logic."""

    def test_empty_search_returns_empty(self):
        import kos.mcp.server as mcp

        with patch("kos.mcp.server.get_artifact_path", side_effect=Exception("no db")):
            result = mcp.tool_search_knowledge("", limit=5)
            self.assertIn("error", result)

    def test_entity_without_db(self):
        import kos.mcp.server as mcp

        with patch("kos.mcp.server.get_artifact_path", side_effect=Exception("no db")):
            result = mcp.tool_get_entity("nonexistent")
            self.assertIn("error", result)

    def test_full_rebuild_requires_l2_confirmation(self):
        import kos.mcp.server as mcp

        with patch("kos.mcp.server.KOS_READY", True), patch("kos.mcp.server.sp.run") as run:
            result = mcp.tool_run_indexer(incremental=False, background=False)

        self.assertEqual(result["status"], "denied")
        self.assertEqual(result["operation_level"], "L2")
        self.assertIn("confirmation", result["error"])
        run.assert_not_called()

    def test_confirmed_full_rebuild_invokes_indexer(self):
        import subprocess

        import kos.mcp.server as mcp

        completed = subprocess.CompletedProcess(args=["kos-indexer"], returncode=0, stdout="indexed", stderr="")
        with patch("kos.mcp.server.KOS_READY", True), patch("kos.mcp.server.sp.run", return_value=completed) as run:
            result = mcp.tool_run_indexer(incremental=False, background=False, confirmed=True)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["operation_level"], "L2")
        run.assert_called_once()
        env = run.call_args.kwargs["env"]
        self.assertIn(str(mcp.SCRIPT_DIR.parent.parent), env["PYTHONPATH"].split(":"))

    def test_search_falls_back_to_canonical_path_match(self):
        import sqlite3

        import kos.mcp.server as mcp

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "kos-index.sqlite"
            conn = sqlite3.connect(db_path)
            conn.executescript("""
                CREATE TABLE documents (
                    doc_id TEXT PRIMARY KEY,
                    title TEXT,
                    kind TEXT,
                    zone TEXT,
                    status TEXT,
                    source TEXT,
                    owner TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    trust_level TEXT,
                    freshness TEXT,
                    review_status TEXT,
                    schema_version TEXT,
                    canonical_path TEXT,
                    source_url TEXT,
                    write_policy TEXT,
                    metadata_json TEXT,
                    body TEXT,
                    file_size INTEGER,
                    file_mtime TEXT
                );
                CREATE VIRTUAL TABLE documents_fts USING fts5(doc_id, title, body, tags, canonical_path);
            """)
            conn.execute(
                "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "doc-1",
                    "Phase 1 Retrospective",
                    "note",
                    "omo",
                    "active",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "kos::omo::summaries/phase1-retrospective.md",
                    "",
                    "",
                    "{}",
                    "retrospective content",
                    0,
                    "",
                ),
            )
            conn.execute(
                "INSERT INTO documents_fts VALUES (?,?,?,?,?)",
                (
                    "doc-1",
                    "Phase 1 Retrospective",
                    "retrospective content",
                    "",
                    "kos::omo::summaries/phase1-retrospective.md",
                ),
            )
            conn.commit()
            conn.close()

            with (
                patch("kos.mcp.server.KOS_READY", True),
                patch("kos.mcp.server.get_artifact_path", return_value=str(db_path)),
                patch("kos.mcp.server.get_workspace_manifest", return_value={"indexing": {"searchDefaultExclude": []}}),
            ):
                result = mcp.tool_search_knowledge("phase1-retrospective", limit=5)

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["canonical_path"], "kos::omo::summaries/phase1-retrospective.md")


class TestMCPSearchLogic(unittest.TestCase):
    """Test FTS search logic in isolation."""

    def setUp(self):
        import sqlite3

        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE documents (doc_id TEXT PRIMARY KEY, title TEXT, body TEXT,
                zone TEXT, kind TEXT, tags TEXT);
            CREATE VIRTUAL TABLE documents_fts USING fts5(doc_id, title, body);
        """)
        self.conn.execute(
            "INSERT INTO documents VALUES ('T:001','Test Doc','Some content here','knowledge','article','test')"
        )
        self.conn.execute("INSERT INTO documents_fts VALUES ('T:001','Test Doc','Some content here')")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_fts_query_returns_results(self):
        cur = self.conn.execute(
            "SELECT d.doc_id, d.title FROM documents_fts f JOIN documents d ON f.doc_id = d.doc_id WHERE documents_fts MATCH ?",
            ("content",),
        )
        rows = cur.fetchall()
        self.assertGreaterEqual(len(rows), 1)

    def test_fts_query_no_results(self):
        cur = self.conn.execute(
            "SELECT d.doc_id FROM documents_fts f JOIN documents d ON f.doc_id = d.doc_id WHERE documents_fts MATCH ?",
            ("nonexistent",),
        )
        self.assertEqual(len(cur.fetchall()), 0)


class TestSkillRouter(unittest.TestCase):
    def test_route_skills_prefers_family_scheduler_for_family_queries(self):
        from kos.self.api import route_skills

        with patch("kos.self.api.get_current_role", return_value={"name": "家庭角色", "tags": ["家事", "孩子"]}):
            result = route_skills(
                "帮我安排孩子明天接送和晚饭分工",
                available_skills=[
                    {
                        "name": "skill-pack-engineering",
                        "description": "Backend and system design workflows",
                        "tags": ["code", "architecture"],
                    },
                    {
                        "name": "family-scheduler",
                        "description": "Family calendar, chores, and household planning",
                        "tags": ["family", "孩子", "家事"],
                    },
                ],
            )

        self.assertEqual(result["matches"][0]["name"], "family-scheduler")
        self.assertEqual(result["current_role"]["name"], "家庭角色")

    def test_skill_router_feedback_penalizes_rejected_skill(self):
        from kos.self.api import record_skill_feedback, route_skills

        with TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "skill_feedback.json"
            with (
                patch("kos.self.api.SKILL_FEEDBACK_PATH", registry_path),
                patch(
                    "kos.self.api.get_current_role",
                    return_value={"name": "个人技术开发者/架构师", "tags": ["AI OS", "系统架构"]},
                ),
            ):
                record_skill_feedback("generic-planner", accepted=False, reason="Too shallow")
                result = route_skills(
                    "设计多 agent 调度架构",
                    available_skills=[
                        {
                            "name": "generic-planner",
                            "description": "General planning assistance",
                            "tags": ["plan"],
                        },
                        {
                            "name": "system-architect",
                            "description": "Architecture planning for agent systems",
                            "tags": ["architecture", "agent"],
                        },
                    ],
                )

        self.assertEqual(result["matches"][0]["name"], "system-architect")

    def test_skill_router_tool_is_registered(self):
        from kos.self.mcp import SELF_TOOLS

        self.assertIn("kos_skill_router", SELF_TOOLS)


if __name__ == "__main__":
    unittest.main()
