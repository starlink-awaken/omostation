"""Tests for SSOT config_loader module.

Covers: ConfigLoader class, load_domain function, parsing, caching.
"""

import json
from pathlib import Path

import pytest
from sot_bridge.ssot_kernel.config_loader import ConfigLoader, load_domain
from sot_bridge.ssot_kernel.meta_model import (
    DomainConfig,
    Entity,
    Fact,
    Inference,
    MetaType,
    Rule,
)

YAML_AVAILABLE = False
try:
    import yaml  # noqa: F401

    YAML_AVAILABLE = True
except ImportError:
    pass


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def domain_dir(tmp_path: Path) -> Path:
    """Create a minimal domain directory with YAML files."""
    d = tmp_path / "test_domain"
    d.mkdir()
    # domain.yaml
    (d / "domain.yaml").write_text("domain:\n  name: test-domain\n  version: 1.0")
    # entities.yaml
    (d / "entities.yaml").write_text(
        "entities:\n  - id: ORG-001\n    type: Organization\n    name: TestOrg\n"
    )
    # facts.yaml
    (d / "facts.yaml").write_text(
        "policy:\n"
        "  - id: POL-001\n"
        "    title: Test Policy\n"
        "    value: must follow rule\n"
        "data:\n"
        "  - id: DAT-001\n"
        "    title: Test Data\n"
        "    value: 100\n"
        "    unit: km\n"
    )
    # inferences.yaml
    (d / "inferences.yaml").write_text(
        "inferences:\n"
        "  - id: INF-001\n"
        "    title: Test Inference\n"
        "    derives_from:\n"
        "      - DAT-001\n"
        "    logic: direct\n"
        "    conclusion: conclusion\n"
    )
    # rules.yaml
    (d / "rules.yaml").write_text(
        "rules:\n"
        "  - id: R-001\n"
        "    pattern: contradiction\n"
        "    name: Test Rule\n"
        "    premises:\n"
        "      - condition: test\n"
    )
    # relations.yaml
    (d / "relations.yaml").write_text(
        "relations:\n  - source_id: ORG-001\n    target_id: ORG-001\n    relation_type: part_of\n"
    )
    return d


@pytest.fixture
def domain_dir_json(tmp_path: Path) -> Path:
    """Create a domain directory with JSON files (alternative format)."""
    d = tmp_path / "json_domain"
    d.mkdir()
    (d / "domain.json").write_text(json.dumps({"domain": {"name": "json-domain"}}))
    (d / "entities.json").write_text(
        json.dumps(
            {"entities": [{"id": "ORG-001", "type": "Organization", "name": "Org1"}]}
        )
    )
    (d / "facts.json").write_text(
        json.dumps({"policy": [{"id": "POL-001", "title": "P1"}], "data": []})
    )
    return d


@pytest.fixture
def empty_domain_dir(tmp_path: Path) -> Path:
    """Create a domain directory with valid but empty files."""
    d = tmp_path / "empty_domain"
    d.mkdir()
    (d / "domain.yaml").write_text("domain:\n  name: empty")
    (d / "entities.yaml").write_text("entities: []")
    (d / "facts.yaml").write_text("policy: []\ndata: []")
    (d / "inferences.yaml").write_text("inferences: []")
    (d / "rules.yaml").write_text("rules: []")
    (d / "relations.yaml").write_text("relations: []")
    return d


# ── Tests ───────────────────────────────────────────────────────────────────


class TestConfigLoader:
    def test_init(self, domain_dir: Path):
        loader = ConfigLoader(domain_dir, use_cache=False)
        assert str(loader.domain_dir) == str(domain_dir)

    def test_cache_path(self, domain_dir: Path):
        cp = ConfigLoader.cache_path(domain_dir)
        assert cp.name == ".ssot_cache.json"

    def test_load_domain_minimal(self, domain_dir: Path):
        """Test loading a complete domain with all YAML files."""
        loader = ConfigLoader(domain_dir, use_cache=False)
        config = loader.load()
        assert isinstance(config, DomainConfig)
        assert config.domain.get("name") == "test-domain"
        assert len(config.entities) == 1
        assert config.entities[0].id == "ORG-001"
        assert len(config.facts) == 2  # 1 policy + 1 data
        assert len(config.inferences) == 1
        assert config.inferences[0].id == "INF-001"
        assert len(config.rules) == 1
        assert config.rules[0].id == "R-001"
        assert len(config.relations) == 1
        assert config.relations[0].source_id == "ORG-001"

    def test_load_domain_empty(self, empty_domain_dir: Path):
        """Test loading an empty domain with no entities/facts."""
        loader = ConfigLoader(empty_domain_dir, use_cache=False)
        config = loader.load()
        assert config.domain.get("name") == "empty"
        assert config.entities == []
        assert config.facts == []

    def test_load_domain_not_found(self):
        loader = ConfigLoader("/nonexistent/path", use_cache=False)
        with pytest.raises(FileNotFoundError):
            loader.load()

    def test_missing_dir_fallback(self, tmp_path: Path):
        """load_domain function with nonexistent dir raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_domain(tmp_path / "no_such_dir")

    def test_json_format(self, domain_dir_json: Path):
        """Test loading JSON format domain configs."""
        loader = ConfigLoader(domain_dir_json, use_cache=False)
        config = loader.load()
        assert config.domain.get("name") == "json-domain"
        assert len(config.entities) == 1
        assert config.entities[0].id == "ORG-001"

    def test_cache_write_and_read(self, domain_dir: Path):
        """Test that cache is written and can be read back."""
        loader = ConfigLoader(domain_dir, use_cache=True)
        config1 = loader.load()
        assert config1.domain.get("name") == "test-domain"

        # Verify cache file exists
        cp = ConfigLoader.cache_path(domain_dir)
        assert cp.exists()

        # Load again from cache
        loader2 = ConfigLoader(domain_dir, use_cache=True)
        config2 = loader2.load()
        assert config2.domain.get("name") == "test-domain"
        assert len(config2.entities) == 1

    def test_cache_miss_on_change(self, domain_dir: Path):
        """Test that cache is invalidated when YAML files change."""
        loader = ConfigLoader(domain_dir, use_cache=True)
        loader.load()  # write cache

        # Modify a yaml file to change mtime
        (domain_dir / "domain.yaml").write_text("domain:\n  name: modified-domain\n")

        loader2 = ConfigLoader(domain_dir, use_cache=True)
        config = loader2.load()
        assert config.domain.get("name") == "modified-domain"


# ── Test load_domain convenience function ───────────────────────────────────


class TestLoadDomainFunction:
    def test_load_domain(self, domain_dir: Path):
        config = load_domain(domain_dir, use_cache=False)
        assert isinstance(config, DomainConfig)
        assert config.domain.get("name") == "test-domain"
        assert len(config.entities) == 1

    def test_load_domain_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_domain("/nonexistent/domain", use_cache=False)


# ── Test parsing methods directly ───────────────────────────────────────────


class TestParsing:
    def test_parse_entity(self, domain_dir: Path):
        loader = ConfigLoader(domain_dir, use_cache=False)
        e = loader._parse_entity(
            {
                "id": "ORG-002",
                "type": "Organization",
                "name": "Org2",
                "meta_type": "MET-DOMAIN",
            }
        )
        assert isinstance(e, Entity)
        assert e.id == "ORG-002"
        assert e.meta_type == MetaType.DOMAIN

    def test_parse_entity_default_meta_type(self, domain_dir: Path):
        loader = ConfigLoader(domain_dir, use_cache=False)
        e = loader._parse_entity({"id": "ORG-003", "type": "Organization"})
        assert e.meta_type == MetaType.DOMAIN  # default

    def test_parse_fact(self, domain_dir: Path):
        loader = ConfigLoader(domain_dir, use_cache=False)
        f = loader._parse_fact(
            {"id": "DAT-010", "title": "Data point", "value": 42, "unit": "kg"}, "data"
        )
        assert isinstance(f, Fact)
        assert f.value == 42
        assert f.unit == "kg"
        assert "data" in f.tags

    def test_parse_inference(self, domain_dir: Path):
        loader = ConfigLoader(domain_dir, use_cache=False)
        i = loader._parse_inference(
            {
                "id": "INF-010",
                "title": "Inf",
                "derives_from": ["DAT-001"],
                "logic": "test",
                "conclusion": "result",
            }
        )
        assert isinstance(i, Inference)
        assert i.logic == "test"
        assert i.conclusion == "result"

    def test_parse_rule(self, domain_dir: Path):
        loader = ConfigLoader(domain_dir, use_cache=False)
        r = loader._parse_rule(
            {"id": "R-010", "pattern": "contradiction", "name": "Rule10"}
        )
        assert isinstance(r, Rule)
        assert r.pattern == "contradiction"

    def test_parse_relation(self, domain_dir: Path):
        loader = ConfigLoader(domain_dir, use_cache=False)
        r = loader._parse_relation(
            {"source_id": "ORG-A", "target_id": "ORG-B", "relation_type": "part_of"}
        )
        assert r.source_id == "ORG-A"
        assert r.target_id == "ORG-B"
        assert r.relation_type == "part_of"

    def test_deduplicate_no_dup(self, domain_dir: Path):
        loader = ConfigLoader(domain_dir, use_cache=False)
        items = [
            Entity(
                id="ORG-A",
                name="A",
                meta_type=MetaType.DOMAIN,
                entity_type="Organization",
            ),
            Entity(
                id="ORG-B",
                name="B",
                meta_type=MetaType.DOMAIN,
                entity_type="Organization",
            ),
        ]
        loader._deduplicate(items, "实体")
        assert len(items) == 2

    def test_deduplicate_removes_dup(self, domain_dir: Path, capsys):
        loader = ConfigLoader(domain_dir, use_cache=False)
        items = [
            Entity(
                id="ORG-A",
                name="A",
                meta_type=MetaType.DOMAIN,
                entity_type="Organization",
            ),
            Entity(
                id="ORG-A",
                name="A-dup",
                meta_type=MetaType.DOMAIN,
                entity_type="Organization",
            ),
        ]
        loader._deduplicate(items, "实体")
        assert len(items) == 1
        captured = capsys.readouterr()
        assert "重复" in captured.out
