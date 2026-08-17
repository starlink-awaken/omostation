"""Tests for iris CLI commands."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from iris.cli import build_parser


class TestCLI:
    def test_parser_list(self):
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"
        assert args.platform is None

    def test_parser_list_platform(self):
        parser = build_parser()
        args = parser.parse_args(["list", "obsidian", "--limit", "5"])
        assert args.command == "list"
        assert args.platform == "obsidian"
        assert args.limit == 5

    def test_parser_search(self):
        parser = build_parser()
        args = parser.parse_args(["search", "obsidian", "test query", "--limit", "3"])
        assert args.command == "search"
        assert args.platform == "obsidian"
        assert args.query == "test query"
        assert args.limit == 3

    def test_parser_get(self):
        parser = build_parser()
        args = parser.parse_args(["get", "obsidian", "some-note-id"])
        assert args.command == "get"
        assert args.platform == "obsidian"
        assert args.id == "some-note-id"

    def test_parser_status(self):
        parser = build_parser()
        args = parser.parse_args(["status"])
        assert args.command == "status"

    def test_parser_sync(self):
        parser = build_parser()
        args = parser.parse_args(["sync", "obsidian", "wxread"])
        assert args.command == "sync"
        assert args.platforms == ["obsidian", "wxread"]

    def test_parser_sync_all(self):
        parser = build_parser()
        args = parser.parse_args(["sync"])
        assert args.command == "sync"
        assert args.platforms == []

    def test_parser_sync_dry_run(self):
        parser = build_parser()
        args = parser.parse_args(["sync", "--dry-run"])
        assert args.dry_run is True

    def test_parser_config(self):
        parser = build_parser()
        args = parser.parse_args(["config"])
        assert args.command == "config"
        assert args.action == "show"

    def test_parser_config_set(self):
        parser = build_parser()
        args = parser.parse_args(["config", "set", "obsidian.vault", "/path"])
        assert args.action == "set"
        assert args.key == "obsidian.vault"
        assert args.value == "/path"

    def test_parser_init(self):
        parser = build_parser()
        args = parser.parse_args(["init"])
        assert args.command == "init"
        assert args.platform is None

    def test_parser_init_platform(self):
        parser = build_parser()
        args = parser.parse_args(["init", "--platform", "obsidian"])
        assert args.platform == "obsidian"

    def test_parser_export(self):
        parser = build_parser()
        args = parser.parse_args(["export", "obsidian", "--format", "md", "-o", "out.md"])
        assert args.command == "export"
        assert args.platform == "obsidian"
        assert args.format == "md"
        assert args.output == "out.md"

    def test_parser_adapters(self):
        parser = build_parser()
        args = parser.parse_args(["adapters"])
        assert args.command == "adapters"

    def test_parser_validate(self):
        parser = build_parser()
        args = parser.parse_args(["validate", "test.json"])
        assert args.command == "validate"
        assert args.file == "test.json"

    def test_json_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--json", "status"])
        assert args.json is True
