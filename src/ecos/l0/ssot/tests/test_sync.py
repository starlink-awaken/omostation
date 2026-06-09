"""Tests for SSOT sync module (sync.py).

Covers: Markdown parsing, entity/fact/inference to Markdown conversion,
sync_yaml_to_markdown function, SyncReport.
"""

from pathlib import Path

from sot_bridge.ssot_kernel.meta_model import (
    Entity,
    Fact,
    Inference,
    MetaType,
)
from sot_bridge.ssot_kernel.sync import (
    SyncReport,
    _entity_to_md,
    _fact_to_md,
    _inference_to_md,
    _parse_markdown_entities,
    _parse_markdown_facts,
    _parse_markdown_inferences,
    sync_yaml_to_markdown,
)


class TestMarkdownParsing:
    def test_parse_markdown_entities(self):
        text = "## ✅ ORG-001（TestOrg）\n## 📋 ROL-002（TestRole）\nSome other content"
        ids = _parse_markdown_entities(text)
        assert "ORG-001" in ids
        assert "ROL-002" in ids

    def test_parse_markdown_entities_no_ids(self):
        ids = _parse_markdown_entities("No entities here")
        assert ids == set()

    def test_parse_markdown_facts(self):
        text = "**DAT-001**: Value = 100 km\n**POL-001**: Policy"
        ids = _parse_markdown_facts(text)
        assert "DAT-001" in ids
        assert "POL-001" in ids

    def test_parse_markdown_facts_empty(self):
        ids = _parse_markdown_facts("No facts here")
        assert ids == set()

    def test_parse_markdown_inferences(self):
        text = "**INF-001**: Conclusion\n**INF-002**: Another"
        ids = _parse_markdown_inferences(text)
        assert "INF-001" in ids
        assert "INF-002" in ids

    def test_parse_markdown_inferences_empty(self):
        ids = _parse_markdown_inferences("No inferences")
        assert ids == set()


class TestEntityToMd:
    def test_active_entity(self):
        e = Entity(
            id="ORG-001",
            name="TestOrg",
            meta_type=MetaType.DOMAIN,
            entity_type="Organization",
            source="doc",
        )
        md = _entity_to_md(e)
        assert "ORG-001" in md
        assert "✅" in md
        assert "doc" in md

    def test_draft_entity(self):
        e = Entity(
            id="ROL-001",
            name="Role1",
            meta_type=MetaType.DOMAIN,
            entity_type="Role",
            status="draft",
        )
        md = _entity_to_md(e)
        assert "ROL-001" in md
        assert "📋" in md

    def test_entity_with_attributes(self):
        e = Entity(
            id="ORG-002",
            name="Org2",
            meta_type=MetaType.DOMAIN,
            entity_type="Organization",
            attributes={"field": "value"},
        )
        md = _entity_to_md(e)
        assert "field" in md
        assert "value" in md

    def test_entity_with_metadata_refs(self):
        e = Entity(
            id="ORG-003",
            name="Org3",
            meta_type=MetaType.DOMAIN,
            entity_type="Organization",
            metadata={"facts": ["DAT-001"], "policies": ["POL-001"]},
        )
        md = _entity_to_md(e)
        assert "DAT-001" in md
        assert "POL-001" in md


class TestFactToMd:
    def test_policy_fact(self):
        f = Fact(id="POL-001", title="Test Policy", value="must follow")
        md = _fact_to_md(f)
        assert "POL-001" in md
        assert "Test Policy" in md

    def test_data_fact(self):
        f = Fact(id="DAT-001", title="Data point", value=100, unit="km")
        md = _fact_to_md(f)
        assert "DAT-001" in md
        assert "100" in md
        assert "km" in md

    def test_fact_with_source(self):
        f = Fact(id="DAT-002", title="Fact", source="report", date="2024-01-01")
        md = _fact_to_md(f)
        assert "report" in md
        assert "2024-01-01" in md

    def test_fact_with_warnings(self):
        f = Fact(id="DAT-003", title="Fact with warnings", warnings=["Outdated"])
        md = _fact_to_md(f)
        assert "⚠" in md or "Outdated" in md


class TestInferenceToMd:
    def test_inference(self):
        i = Inference(
            id="INF-001",
            title="Test Inference",
            derives_from=["DAT-001", "DAT-002"],
            logic="A > B",
            conclusion="B wins",
            theory="Game theory",
        )
        md = _inference_to_md(i)
        assert "INF-001" in md
        assert "B wins" in md
        assert "DAT-001" in md
        assert "Game theory" in md

    def test_inference_minimal(self):
        i = Inference(
            id="INF-002",
            title="Minimal",
            derives_from=[],
            logic="",
            conclusion="Nothing",
        )
        md = _inference_to_md(i)
        assert "INF-002" in md


class TestSyncReport:
    def test_empty_report(self):
        report = SyncReport()
        assert report.has_changes is False
        assert len(report.items_added) == 0
        assert len(report.errors) == 0

    def test_non_empty_report(self):
        report = SyncReport()
        report.items_added.append(("file.md", "ORG-001"))
        assert report.has_changes

    def test_print_output(self, capsys):
        report = SyncReport()
        report.print()
        captured = capsys.readouterr()
        assert "同步报告" in captured.out


class TestSyncYamlToMarkdown:
    def test_md_dir_not_found(self):
        """sync_yaml_to_markdown with nonexistent MD dir returns error."""
        report = sync_yaml_to_markdown(
            yaml_dir="/nonexistent/yaml",
            md_dir="/nonexistent/md",
            dry_run=True,
        )
        assert len(report.errors) >= 1

    def test_yaml_load_failure(self, tmp_path: Path):
        """sync_yaml_to_markdown with bad YAML dir should handle error."""
        md_dir = tmp_path / "md"
        md_dir.mkdir()
        (md_dir / "01-实体本体").mkdir(parents=True, exist_ok=True)
        (md_dir / "01-实体本体/01-组织实体.md").write_text("# Existing\n")

        report = sync_yaml_to_markdown(
            yaml_dir=str(tmp_path / "nonexistent_yaml_src"),
            md_dir=str(md_dir),
            dry_run=True,
        )
        assert len(report.errors) >= 1
