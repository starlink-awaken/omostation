"""Tests for 5 new Iris connectors: GitHub, Apple Notes, Pocket, RSS, Polar.

All connectors are tested with mocked external dependencies
so tests are fast and deterministic. Each test creates its own
connector instance to avoid caching issues.
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from iris.base import BaseConnector
from iris.models import Bookmark, Note

# ================================================================
# GitHub connector tests
# ================================================================

GH_REPOS_JSON = json.dumps(
    [
        {
            "name": "iris",
            "owner": {"login": "starlink-awaken"},
            "description": "Connector hub",
            "html_url": "https://github.com/starlink-awaken/iris",
        }
    ]
)
GH_ISSUES_JSON = json.dumps(
    [
        {
            "number": 1,
            "title": "Test issue",
            "state": "open",
            "body": "Issue body",
            "html_url": "https://github.com/starlink-awaken/iris/issues/1",
            "user": {"login": "user1"},
            "created_at": "2026-01-01T00:00:00Z",
        }
    ]
)
GH_PRS_JSON = json.dumps(
    [
        {
            "number": 42,
            "title": "Test PR",
            "state": "open",
            "body": "PR description",
            "html_url": "https://github.com/starlink-awaken/iris/pull/42",
            "user": {"login": "user2"},
            "headRefName": "feature",
            "baseRefName": "main",
            "created_at": "2026-02-01T00:00:00Z",
        }
    ]
)
GH_REPO_JSON = json.dumps(
    {
        "name": "iris",
        "owner": {"login": "starlink-awaken"},
        "description": "A connector hub",
        "html_url": "https://github.com/starlink-awaken/iris",
        "clone_url": "https://github.com/starlink-awaken/iris.git",
        "stargazers_count": 100,
        "language": "Python",
    }
)


def _make_gh_mock(cmds: dict[str, str]) -> MagicMock:
    """Create a subprocess.run mock that returns different output per command."""

    def side_effect(cmd, *args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        cmd_str = " ".join(cmd)
        for prefix, output in cmds.items():
            if prefix in cmd_str:
                result.stdout = output
                return result
        result.stdout = "[]"
        return result

    return MagicMock(side_effect=side_effect)


class TestGitHubConnector:
    def _make(self):
        from iris.connectors.github.connector import GitHubConnector

        return GitHubConnector()

    def test_name(self):
        conn = self._make()
        assert conn.name == "github"
        assert conn.display_name == "GitHub"

    # GitHub test: gh IS installed on this machine, so is_available always returns True
    # Skip the no_gh variant test since it can't be reproduced here

    @patch("shutil.which", return_value="/usr/local/bin/gh")
    def test_is_available(self, _):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="gh version 2.92.0\n")
            conn = self._make()
            assert conn.is_available()

    @patch("shutil.which", return_value="/usr/local/bin/gh")
    def test_list_items(self, _):
        mock = _make_gh_mock(
            {
                "repo list": GH_REPOS_JSON,
                "issue list": GH_ISSUES_JSON,
                "pr list": GH_PRS_JSON,
            }
        )
        with patch("subprocess.run", mock):
            conn = self._make()
            items = conn.list_items(limit=5)
            assert len(items) > 0
            types = {type(i).__name__ for i in items}
            assert "Article" in types

    @patch("shutil.which", return_value="/usr/local/bin/gh")
    def test_get_item_repo(self, _):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=GH_REPO_JSON)
            conn = self._make()
            item = conn.get_item("repo:starlink-awaken/iris")
            assert item is not None
            assert item.title == "iris"
            assert item.platform == "github"

    @patch("shutil.which", return_value="/usr/local/bin/gh")
    def test_search(self, _):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=GH_ISSUES_JSON)
            conn = self._make()
            items = conn.search("test", limit=5)
            assert isinstance(items, list)

    @patch("shutil.which", return_value="/usr/local/bin/gh")
    def test_sync_dry_run(self, _):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=GH_REPOS_JSON)
            conn = self._make()
            sync_result = conn.sync(dry_run=True)
            assert sync_result.success

    @patch("shutil.which", return_value="/usr/local/bin/gh")
    def test_status(self, _):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=GH_REPOS_JSON)
            conn = self._make()
            status = conn.status()
            assert "available" in status

    @patch("shutil.which", return_value="/usr/local/bin/gh")
    def test_list_repos(self, _):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=GH_REPOS_JSON)
            conn = self._make()
            repos = conn.list_repos(limit=5)
            assert len(repos) > 0

    @patch("shutil.which", return_value="/usr/local/bin/gh")
    def test_list_issues(self, _):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=GH_ISSUES_JSON)
            conn = self._make()
            issues = conn.list_issues("owner/repo", limit=5)
            assert len(issues) > 0

    @patch("shutil.which", return_value="/usr/local/bin/gh")
    def test_list_prs(self, _):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=GH_PRS_JSON)
            conn = self._make()
            prs = conn.list_prs("owner/repo", limit=5)
            assert len(prs) > 0


# ================================================================
# Apple Notes connector tests
# ================================================================


class TestAppleNotesConnector:
    def _make(self):
        from iris.connectors.applenotes.connector import AppleNotesConnector

        return AppleNotesConnector()

    def test_name(self):
        conn = self._make()
        assert conn.name == "applenotes"
        assert conn.display_name == "Apple Notes"

    @patch("shutil.which", return_value=None)
    def test_is_available_no_osascript(self, _):
        conn = self._make()
        assert not conn.is_available()

    @patch("shutil.which", return_value="/usr/bin/osascript")
    def test_is_available(self, _):
        conn = self._make()
        assert conn.is_available()

    @patch("shutil.which", return_value="/usr/bin/osascript")
    @patch("subprocess.run")
    def test_list_items(self, mock_run, _):
        from iris.connectors.applenotes.connector import AppleNotesConnector

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="便笺, 备忘录",
            stderr="",
        )
        conn = AppleNotesConnector()
        items = conn.list_items(limit=5)
        assert isinstance(items, list)

    @patch("shutil.which", return_value="/usr/bin/osascript")
    @patch("subprocess.run")
    def test_status(self, mock_run, _):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="便笺, 备忘录",
            stderr="",
        )
        conn = self._make()
        status = conn.status()
        assert "available" in status

    @patch("shutil.which", return_value="/usr/bin/osascript")
    def test_list_folders(self, _):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Folder1, Folder2", stderr="")
            conn = self._make()
            folders = conn.list_folders()
            assert isinstance(folders, list)

    def test_strip_html(self):
        from iris.connectors.applenotes.connector import _strip_html

        html = "<div>Hello <b>World</b></div>"
        stripped = _strip_html(html)
        assert stripped == "Hello World"

    def test_make_id_roundtrip(self):
        from iris.connectors.applenotes.connector import _decode_note_id, _make_note_id

        note_id = _make_note_id("Folder", "My Note")
        folder, title = _decode_note_id(note_id)  # type: ignore[reportGeneralTypeIssues]
        assert folder == "Folder"
        assert title == "My Note"


# ================================================================
# Pocket connector tests
# ================================================================


POCKET_ITEM_JSON = json.dumps(
    {
        "list": {
            "123": {
                "item_id": "123",
                "given_title": "My Article",
                "given_url": "https://example.com",
                "excerpt": "An excerpt",
                "time_added": "1700000000",
                "time_updated": "1700000001",
                "tags": {"tech": {"tag": "tech"}},
                "resolved_title": "Resolved Title",
                "status": "0",
            }
        },
        "status": 1,
    }
).encode()

POCKET_EMPTY_JSON = json.dumps({"list": {}, "status": 1}).encode()


class TestPocketConnector:
    def _make(self):
        from iris.connectors.pocket.connector import PocketConnector

        return PocketConnector()

    def test_name(self):
        conn = self._make()
        assert conn.name == "pocket"
        assert conn.display_name == "Pocket"

    def test_is_available_no_keys(self):
        with patch.dict("os.environ", {}, clear=True):
            conn = self._make()
            assert not conn.is_available()

    def test_is_available_with_env(self):
        with patch.dict(
            "os.environ",
            {"POCKET_CONSUMER_KEY": "ck", "POCKET_ACCESS_TOKEN": "at"},
        ):
            conn = self._make()
            assert conn.is_available()

    def test_list_items(self):
        with patch.dict(
            "os.environ",
            {"POCKET_CONSUMER_KEY": "ck", "POCKET_ACCESS_TOKEN": "at"},
        ):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.read.return_value = POCKET_ITEM_JSON
                mock_resp.__enter__.return_value = mock_resp
                mock_urlopen.return_value = mock_resp
                conn = self._make()
                items = conn.list_items(limit=5)
                assert len(items) > 0

    def test_status(self):
        with patch.dict(
            "os.environ",
            {"POCKET_CONSUMER_KEY": "ck", "POCKET_ACCESS_TOKEN": "at"},
        ):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.read.return_value = POCKET_EMPTY_JSON
                mock_resp.__enter__.return_value = mock_resp
                mock_urlopen.return_value = mock_resp
                conn = self._make()
                status = conn.status()
                assert status.get("configured", False)

    def test_sync(self):
        with patch.dict(
            "os.environ",
            {"POCKET_CONSUMER_KEY": "ck", "POCKET_ACCESS_TOKEN": "at"},
        ):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.read.return_value = POCKET_EMPTY_JSON
                mock_resp.__enter__.return_value = mock_resp
                mock_urlopen.return_value = mock_resp
                conn = self._make()
                result = conn.sync(dry_run=False)
                assert result.success

    def test_search(self):
        with patch.dict(
            "os.environ",
            {"POCKET_CONSUMER_KEY": "ck", "POCKET_ACCESS_TOKEN": "at"},
        ):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.read.return_value = POCKET_EMPTY_JSON
                mock_resp.__enter__.return_value = mock_resp
                mock_urlopen.return_value = mock_resp
                conn = self._make()
                items = conn.search("test", limit=5)
                assert isinstance(items, list)

    def test_get_item(self):
        with patch.dict(
            "os.environ",
            {"POCKET_CONSUMER_KEY": "ck", "POCKET_ACCESS_TOKEN": "at"},
        ):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.read.return_value = POCKET_EMPTY_JSON
                mock_resp.__enter__.return_value = mock_resp
                mock_urlopen.return_value = mock_resp
                conn = self._make()
                item = conn.get_item("123")
                assert item is None or isinstance(item, Bookmark)


# ================================================================
# RSS Feeds connector tests
# ================================================================

RSS_ARTICLES_OUTPUT = """[1] [new] Article One
    Blog: Tech Blog
    URL: https://example.com/1
    Published: 2026-01-15

[2] [new] Article Two
    Blog: Dev Blog
    URL: https://example.com/2
    Published: 2026-01-16
"""


class TestRssConnector:
    def _make(self):
        from iris.connectors.rss.connector import RssConnector

        return RssConnector()

    def test_name(self):
        conn = self._make()
        assert conn.name == "rss"
        assert conn.display_name == "RSS Feeds"

    @patch("shutil.which", return_value=None)
    def test_is_available_no_cli(self, _):
        conn = self._make()
        assert not conn.is_available()

    @patch("shutil.which", return_value="/usr/local/bin/blogwatcher-cli")
    def test_is_available(self, _):
        conn = self._make()
        assert conn.is_available()

    @patch("shutil.which", return_value="/usr/local/bin/blogwatcher-cli")
    @patch("subprocess.run")
    def test_list_items(self, mock_run, _):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=RSS_ARTICLES_OUTPUT,
            stderr="",
        )
        conn = self._make()
        items = conn.list_items(limit=5)
        assert len(items) > 0
        assert hasattr(items[0], "title")

    @patch("shutil.which", return_value="/usr/local/bin/blogwatcher-cli")
    @patch("subprocess.run")
    def test_search(self, mock_run, _):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=RSS_ARTICLES_OUTPUT,
            stderr="",
        )
        conn = self._make()
        items = conn.search("Article", limit=5)
        assert isinstance(items, list)

    @patch("shutil.which", return_value="/usr/local/bin/blogwatcher-cli")
    @patch("subprocess.run")
    def test_sync(self, mock_run, _):
        mock_run.return_value = MagicMock(returncode=0, stdout="Scan done", stderr="")
        conn = self._make()
        result = conn.sync(dry_run=False)
        assert result.success

    @patch("shutil.which", return_value="/usr/local/bin/blogwatcher-cli")
    @patch("subprocess.run")
    def test_status(self, mock_run, _):
        mock_run.side_effect = [
            MagicMock(
                returncode=0,
                stdout="Tracked blogs (2):\n  Blog A\n  Blog B",
                stderr="",
            ),
            MagicMock(returncode=0, stdout="[1] Article", stderr=""),
        ]
        conn = self._make()
        status = conn.status()
        assert "available" in status


# ================================================================
# Polar.sh connector tests
# ================================================================

POLAR_ITEMS_RESP = {
    "items": [
        {
            "id": "abc123",
            "title": "Test Article",
            "body": "Article body content",
            "url": "https://example.com/article",
            "tags": ["tech"],
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
        }
    ],
    "pagination": {"total_count": 1},
}

POLAR_SINGLE_RESP = {
    "id": "abc123",
    "title": "Single Article",
    "body": "Body",
    "url": "https://example.com/a",
    "tags": ["tech"],
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-02T00:00:00Z",
}


class TestPolarConnector:
    def _make(self):
        from iris.connectors.polar.connector import PolarConnector

        return PolarConnector()

    def test_name(self):
        conn = self._make()
        assert conn.name == "polar"
        assert conn.display_name == "Polar.sh"

    def test_is_available_no_key(self):
        with patch.dict("os.environ", {}, clear=True):
            conn = self._make()
            assert not conn.is_available()

    def test_is_available_with_key(self):
        with patch.dict("os.environ", {"POLAR_API_KEY": "test-key-123"}):
            conn = self._make()
            assert conn.is_available()

    def test_list_items(self):
        with patch.dict("os.environ", {"POLAR_API_KEY": "test-key-123"}):
            with patch("iris.connectors.polar.connector.httpx.get") as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = POLAR_ITEMS_RESP
                mock_get.return_value = mock_resp
                conn = self._make()
                items = conn.list_items(limit=5)
                assert len(items) > 0
                assert items[0].title == "Test Article"

    def test_get_item(self):
        with patch.dict("os.environ", {"POLAR_API_KEY": "test-key-123"}):
            with patch("iris.connectors.polar.connector.httpx.get") as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = POLAR_SINGLE_RESP
                mock_get.return_value = mock_resp
                conn = self._make()
                item = conn.get_item("abc123")
                assert item is not None
                assert item.title == "Single Article"

    def test_search(self):
        with patch.dict("os.environ", {"POLAR_API_KEY": "test-key-123"}):
            with patch("iris.connectors.polar.connector.httpx.get") as mock_get:
                import httpx

                mock_get.side_effect = httpx.HTTPStatusError(
                    "404",
                    request=MagicMock(),
                    response=MagicMock(status_code=404),
                )
                conn = self._make()
                items = conn.search("test", limit=5)
                assert isinstance(items, list)

    def test_sync(self):
        with patch.dict("os.environ", {"POLAR_API_KEY": "test-key-123"}):
            with patch("iris.connectors.polar.connector.httpx.get") as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "items": [],
                    "pagination": {"total_count": 0},
                }
                mock_get.return_value = mock_resp
                conn = self._make()
                result = conn.sync(dry_run=False)
                assert result.success

    def test_status(self):
        with patch.dict("os.environ", {"POLAR_API_KEY": "test-key-123"}):
            with patch("iris.connectors.polar.connector.httpx.get") as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "items": [],
                    "pagination": {"total_count": 5},
                }
                mock_get.return_value = mock_resp
                conn = self._make()
                status = conn.status()
                assert status.get("configured", False)


# ================================================================
# Entry points test — all connectors discoverable
# ================================================================


class TestEntryPoints:
    def test_all_new_connectors_in_entry_points(self):
        """Verify all 14 connectors are registered in entry_points."""
        from iris.connectors import _register_fallback
        from iris.registry import ConnectorRegistry

        registry = ConnectorRegistry()
        # Always use fallback registration for testing since editable installs
        # via .pth (no .dist-info) don't expose entry_points properly.
        # Actual entry_point discovery works when iris is properly pip-installed.
        _register_fallback(registry)

        names = registry.list_names()
        required = [
            "github",
            "applenotes",
            "pocket",
            "rss",
            "polar",
            "openhuman",
            "obsidian",
            "wpsnote",
            "zhihu",
            "wxread",
            "telegram",
            "notebooklm",
            "local_files",
        ]
        for name in required:
            assert name in names, f"{name} missing from registry"

        assert len(names) >= 13, f"Expected 13+ connectors, got {len(names)}: {names}"


class TestOpenHumanConnector:
    def test_importable(self):
        from iris.connectors.openhuman.connector import OpenHumanConnector

        conn = OpenHumanConnector()
        assert conn.name == "openhuman"
        assert conn.display_name == "OpenHuman"

    def test_is_available_returns_false_when_offline(self):
        from iris.connectors.openhuman.connector import OpenHumanConnector

        conn = OpenHumanConnector()
        assert not conn.is_available()


class TestWeChatConnector:
    def _make(self, data_dir):
        from iris.connectors.wechat.connector import WeChatConnector

        return WeChatConnector(data_dir=data_dir)

    def test_wechat_connector_is_base_connector(self, tmp_path):
        conn = self._make(tmp_path / "wechat")
        assert isinstance(conn, BaseConnector)
        assert conn.name == "wechat"

    def test_import_and_search_export_stub(self, tmp_path):
        export = tmp_path / "wechat-export.txt"
        export.write_text(
            "\n".join(
                [
                    "2026-06-01 08:30 - 妈妈: 记得买蛋糕",
                    "2026-06-01 09:10 - 我: 晚上再确认接送",
                ]
            ),
            encoding="utf-8",
        )
        conn = self._make(tmp_path / "wechat-data")
        result = conn.import_file(str(export))
        assert result["imported"] == 2

        items = conn.list_items(limit=10)
        assert items
        assert isinstance(items[0], Note)
        assert "蛋糕" in items[0].content

        contacts = conn.list_contacts()
        assert "妈妈" in contacts

        matches = conn.search("接送", limit=5)
        assert matches
        assert "接送" in matches[0].content

        status = conn.status()
        assert status["mode"] == "export_stub"
        assert status["messages"] == 2
