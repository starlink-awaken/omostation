"""Tests for SSOT and eidos adapters."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import tempfile
from pathlib import Path

from iris.adapters.eidos import EidosAdapter
from iris.adapters.ssot import SSOTDomainAdapter
from iris.config import IrisConfig


class TestSSOTAdapter:
    def test_ensure_domain_creates_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = IrisConfig(config_path=Path(tmp) / "config.json")
            adapter = SSOTDomainAdapter(config)
            domain_dir = adapter.ensure_domain("test-platform", "Test Platform")
            assert domain_dir.exists()
            assert (domain_dir / "domain.yaml").exists()
            assert (domain_dir / "entities.yaml").exists()
            assert (domain_dir / "facts.yaml").exists()
            # Verify domain.yaml content
            content = (domain_dir / "domain.yaml").read_text()
            assert "Test Platform" in content

    def test_domain_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = IrisConfig(config_path=Path(tmp) / "config.json")
            adapter = SSOTDomainAdapter(config)
            assert not adapter.domain_exists("nonexistent")
            adapter.ensure_domain("exists")
            assert adapter.domain_exists("exists")

    def test_list_domains(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = IrisConfig(config_path=Path(tmp) / "config.json")
            adapter = SSOTDomainAdapter(config)
            assert adapter.list_domains() == []
            adapter.ensure_domain("a")
            adapter.ensure_domain("b")
            domains = adapter.list_domains()
            assert "a" in domains
            assert "b" in domains


class TestEidosAdapter:
    def test_eidos_available(self):
        adapter = EidosAdapter()
        # eidos is installed in this workspace
        status = adapter.status()
        assert "eidos_available" in status

    def test_validate_valid_knowledge_card(self):
        adapter = EidosAdapter()
        data = {
            "id": "test/1",
            "title": "Test",
            "content": "Hello world",
            "source": "obsidian",
            "source_type": "obsidian",
            "schema_type": "KnowledgeCard",
            "tags": [],
            "relations": [],
        }
        result = adapter.validate_knowledge_card(data)
        if adapter.is_eidos_available():
            assert result["is_valid"] is True
        else:
            assert "eidos not installed" in result["errors"][0]

    def test_validate_invalid_knowledge_card(self):
        adapter = EidosAdapter()
        data = {"id": "test/1"}  # missing required fields
        result = adapter.validate_knowledge_card(data)
        if adapter.is_eidos_available():
            assert result["is_valid"] is False
            assert len(result["errors"]) > 0
