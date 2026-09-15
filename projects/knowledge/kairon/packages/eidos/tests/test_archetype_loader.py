"""Tests for eidos.archetype_loader."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false


class TestParseYamlFrontmatter:
    """Test _parse_yaml_frontmatter utility."""

    def test_import(self):
        from eidos.archetype_loader import _parse_yaml_frontmatter

        assert _parse_yaml_frontmatter is not None

    def test_with_valid_frontmatter(self):
        from eidos.archetype_loader import _parse_yaml_frontmatter

        content = """---
key: value
name: test
number: 42
---

Body content here
"""
        result = _parse_yaml_frontmatter(content)
        assert result == {"key": "value", "name": "test", "number": 42}

    def test_without_frontmatter(self):
        from eidos.archetype_loader import _parse_yaml_frontmatter

        content = "Just a plain text file\nNo frontmatter here"
        result = _parse_yaml_frontmatter(content)
        assert result == {}

    def test_with_empty_frontmatter(self):
        from eidos.archetype_loader import _parse_yaml_frontmatter

        content = """---
---
Body
"""
        result = _parse_yaml_frontmatter(content)
        assert result == {}

    def test_with_invalid_yaml(self):
        from eidos.archetype_loader import _parse_yaml_frontmatter

        content = """---
invalid: [unclosed list
---
Body
"""
        result = _parse_yaml_frontmatter(content)
        assert result == {}

    def test_with_non_dict_frontmatter(self):
        from eidos.archetype_loader import _parse_yaml_frontmatter

        content = """---
- list
- not
- dict
---
Body
"""
        result = _parse_yaml_frontmatter(content)
        assert result == {}


class TestArchetypeLoader:
    """Test ArchetypeLoader class."""

    def test_import(self):
        from eidos.archetype_loader import ArchetypeLoader

        assert ArchetypeLoader is not None

    def test_init_with_temp_dir(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        assert loader._root == tmp_path
        assert loader._max_cache_size == 100

    def test_init_custom_cache_size(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        loader = ArchetypeLoader(archetypes_root=tmp_path, max_cache_size=5)
        assert loader._max_cache_size == 5

    def test_get_agent_archetypes_empty(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        result = loader.get_agent_archetypes()
        assert result == {}

    def test_get_tool_archetypes_empty(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        result = loader.get_tool_archetypes()
        assert result == {}

    def test_get_law_archetypes_empty(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        result = loader.get_law_archetypes()
        assert result == {}

    def test_get_skill_archetypes_empty(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        result = loader.get_skill_archetypes()
        assert result == {}

    def test_get_agent_nonexistent(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        assert loader.get_agent("nonexistent") is None

    def test_get_tool_nonexistent(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        assert loader.get_tool("nonexistent") is None

    def test_get_law_nonexistent(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        assert loader.get_law("nonexistent") is None

    def test_list_agent_ids_empty(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        assert loader.list_agent_ids() == []

    def test_list_tool_ids_empty(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        assert loader.list_tool_ids() == []

    def test_invalidate_cache(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        loader.get_agent_archetypes()  # populate cache
        assert len(loader._cache) > 0

        loader.invalidate_cache()
        assert len(loader._cache) == 0

    def test_validate_internal_state(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        assert loader.validate_internal_state() is True

    def test_lru_cache_eviction(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        loader = ArchetypeLoader(archetypes_root=tmp_path, max_cache_size=2)
        # Access 3 different keys to trigger eviction
        loader.get_agent_archetypes()  # cache key: yaml:workers
        loader.get_tool_archetypes()  # cache key: yaml:synapses
        loader.get_law_archetypes()  # cache key: md:cells
        assert len(loader._cache) <= 2


class TestGetArchetypeLoader:
    """Test get_archetype_loader singleton."""

    def test_get_archetype_loader(self):
        from eidos.archetype_loader import get_archetype_loader

        loader = get_archetype_loader()
        assert loader is not None

    def test_singleton(self):
        from eidos.archetype_loader import get_archetype_loader

        loader1 = get_archetype_loader()
        loader2 = get_archetype_loader()
        assert loader1 is loader2


class TestArchetypeLoaderWithFiles:
    """Test ArchetypeLoader with actual YAML files."""

    def test_load_yaml_worker(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "test_agent.yaml").write_text("id: agent-1\nname: Test Agent\n")

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        agents = loader.get_agent_archetypes()
        assert "test_agent" in agents
        assert agents["test_agent"]["id"] == "agent-1"
        assert agents["test_agent"]["name"] == "Test Agent"

    def test_load_yaml_synapses(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        synapses_dir = tmp_path / "synapses"
        synapses_dir.mkdir()
        (synapses_dir / "search.yaml").write_text("tool_id: tool-search\nname: Search Tool\n")

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        tools = loader.get_tool_archetypes()
        assert "search" in tools
        assert tools["search"]["tool_id"] == "tool-search"

    def test_load_md_frontmatter(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        cells_dir = tmp_path / "cells"
        cells_dir.mkdir()
        (cells_dir / "law_of_gravity.md").write_text("---\nname: Law of Gravity\npriority: 1\n---\n\nContent here\n")

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        laws = loader.get_law_archetypes()
        assert "law_of_gravity" in laws
        assert laws["law_of_gravity"]["name"] == "Law of Gravity"
        assert laws["law_of_gravity"]["_source_file"] == "law_of_gravity.md"

    def test_load_md_without_frontmatter_skipped(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        cells_dir = tmp_path / "cells"
        cells_dir.mkdir()
        (cells_dir / "no_frontmatter.md").write_text("Plain markdown content\n")

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        laws = loader.get_law_archetypes()
        assert "no_frontmatter" not in laws

    def test_get_agent_by_id(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "agents.yaml").write_text("id: agent-alpha\nname: Alpha\n")

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        agent = loader.get_agent("agent-alpha")
        assert agent is not None
        assert agent["name"] == "Alpha"

    def test_get_tool_by_id(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        synapses_dir = tmp_path / "synapses"
        synapses_dir.mkdir()
        (synapses_dir / "tools.yaml").write_text("tool_id: tool-search\nname: Search\n")

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        tool = loader.get_tool("tool-search")
        assert tool is not None
        assert tool["name"] == "Search"

    def test_list_agent_ids_with_files(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "a1.yaml").write_text("id: agent-one\n")
        (workers_dir / "a2.yaml").write_text("id: agent-two\n")

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        ids = loader.list_agent_ids()
        assert "agent-one" in ids
        assert "agent-two" in ids

    def test_cache_hit_returns_same_data(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "agent.yaml").write_text("id: cached-agent\nname: Cached\n")

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        first = loader.get_agent_archetypes()
        # Modify file after first call — cache should be used
        (workers_dir / "agent.yaml").write_text("id: modified-agent\nname: Modified\n")
        second = loader.get_agent_archetypes()

        assert first == second
        assert second["agent"]["id"] == "cached-agent"

    def test_invalid_yaml_file_skipped(self, tmp_path):
        from eidos.archetype_loader import ArchetypeLoader

        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "bad.yaml").write_text("invalid: [yaml\n")

        loader = ArchetypeLoader(archetypes_root=tmp_path)
        agents = loader.get_agent_archetypes()
        assert agents == {}
