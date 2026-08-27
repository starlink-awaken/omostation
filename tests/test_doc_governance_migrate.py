# ---
# status: active
# lifecycle: contract
# owner: governance-agent
# ssot: .omo/_truth/registry/document-governance.yaml
# verifier: pytest tests/test_doc_governance_migrate.py
# ---
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/doc-governance-migrate.py"
SPEC = importlib.util.spec_from_file_location("doc_governance_migrate", MODULE_PATH)
assert SPEC and SPEC.loader
MIGRATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATOR)


def _registry() -> dict:
    return {
        "metadata": {
            "valid_lifecycles": ["contract", "plan", "history"],
            "enum_migrations": {
                "status": {"approved": "archived"},
                "lifecycle": {"standard": "contract"},
            },
        },
        "surfaces": [
            {
                "id": "docs",
                "patterns": ["docs/**/*.md"],
                "owner": "architecture-team",
                "lifecycle": "contract",
                "ssot": "docs/SYSTEM-INDEX.md",
                "verifier": "bin/ssot/doc-governance-check.py",
                "metadata": "frontmatter",
            }
        ],
    }


def test_migrate_file_adds_metadata_only_frontmatter(tmp_path: Path) -> None:
    doc = tmp_path / "docs" / "guide.md"
    doc.parent.mkdir()
    doc.write_text("# guide\n", encoding="utf-8")

    changed, surface = MIGRATOR.migrate_file(
        doc,
        tmp_path,
        _registry(),
        date(2026, 7, 31),
        "metadata-only",
        False,
    )

    assert changed
    assert surface == "docs"
    text = doc.read_text(encoding="utf-8")
    assert "owner: architecture-team" in text
    assert "review-state: metadata-only" in text
    assert "metadata-migrated-at: 2026-07-31" in text


def test_migrate_file_normalizes_explicit_enum_mapping(tmp_path: Path) -> None:
    doc = tmp_path / "docs" / "guide.md"
    doc.parent.mkdir()
    doc.write_text(
        "---\n"
        "status: approved\n"
        "lifecycle: standard\n"
        "owner: team\n"
        "review-state: metadata-only\n"
        "metadata-migrated-at: 2026-07-30\n"
        "---\n"
        "# guide\n",
        encoding="utf-8",
    )

    changed, _ = MIGRATOR.migrate_file(
        doc,
        tmp_path,
        _registry(),
        date(2026, 7, 31),
        "content-reviewed",
        True,
    )

    assert changed
    text = doc.read_text(encoding="utf-8")
    assert "status: archived" in text
    assert "lifecycle: contract" in text
    assert "review-state: content-reviewed" in text
    assert "content-reviewed-at: 2026-07-31" in text
