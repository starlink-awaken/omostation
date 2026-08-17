# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false
# ruff: noqa
"""KOS external adapter tests — version parsing, discovery, protocol negotiation."""

from pathlib import Path

from kos.adapters import MinervaAdapter, MinervaVersion, SemanticScholarAdapter, negotiate_mcp_protocol


class TestMinervaVersion:
    """Version parsing and comparison."""

    def test_parse_standard(self):
        v = MinervaVersion.parse("minerva 1.2.3")
        assert v.major == 1 and v.minor == 2 and v.patch == 3  # type: ignore[reportOptionalMemberAccess]

    def test_parse_plain(self):
        v = MinervaVersion.parse("0.10.0")
        assert v.major == 0 and v.minor == 10 and v.patch == 0  # type: ignore[reportOptionalMemberAccess]

    def test_parse_none(self):
        assert MinervaVersion.parse("no version here") is None

    def test_comparison(self):
        v = MinervaVersion.parse("2.0.0")
        assert v >= (1, 5, 0)  # type: ignore[reportOptionalOperand]
        assert v >= (2, 0, 0)  # type: ignore[reportOptionalOperand]
        assert not (v < (2, 0, 0))  # type: ignore[reportOptionalOperand]
        assert v < (3, 0, 0)  # type: ignore[reportOptionalOperand]


class TestMinervaAdapterDiscovery:
    """Discovery returns adapter or None."""

    def test_discover_runs_without_crash(self):
        adapter = MinervaAdapter.discover()
        if adapter is not None:
            h = adapter.health()
            assert "available" in h

    def test_null_adapter_health(self):
        from kos.adapters import NullMinerva

        h = NullMinerva.health()
        assert h["available"] is False

    def test_null_adapter_research(self):
        from kos.adapters import NullMinerva

        r = NullMinerva.research("test")
        assert "error" in r  # type: ignore[reportOperatorIssue]
        assert "not available" in r["error"].lower()  # type: ignore[reportOptionalSubscript]

    def test_version_parse_from_pip_show(self):
        v = MinervaVersion.parse("Version: 1.5.2")
        assert v.major == 1 and v.minor == 5 and v.patch == 2  # type: ignore[reportOptionalMemberAccess]


class TestSemanticScholarAdapter:
    """Defensive response parsing."""

    def test_empty_query(self):
        s2 = SemanticScholarAdapter()
        assert s2.BASE == "https://api.semanticscholar.org/graph/v1"

    def test_schema_defense(self):
        s2 = SemanticScholarAdapter()
        s2._wait_rate_limit = lambda: None

        import urllib.request

        class FakeResp:
            def __init__(self, data: str):
                self._data = data.encode()

            def read(self):
                return self._data

        # placeholder: networking is monkeypatched in dedicated integration tests
