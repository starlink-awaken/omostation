# ---
# status: active
# lifecycle: active
# owner: governance-agent
# ssot: .omo/_truth/registry/document-governance.yaml
# verifier: pytest tests/test_doc_governance_check.py
# ---
from __future__ import annotations

import importlib.util
import subprocess
from datetime import date
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/doc-governance-check.py"
SPEC = importlib.util.spec_from_file_location("doc_governance_check", MODULE_PATH)
assert SPEC and SPEC.loader
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def _registry(*, index: str = "docs/SYSTEM-INDEX.md") -> dict:
    return {
        "metadata": {
            "valid_statuses": ["draft", "active", "stale", "superseded", "archived"],
            "valid_lifecycles": ["contract", "entry"],
            "required_frontmatter": ["status", "lifecycle", "owner", "last-reviewed"],
        },
        "surfaces": [
            {
                "id": "docs",
                "patterns": ["docs/**/*.md"],
                "owner": "governance-team",
                "lifecycle": "contract",
                "ssot": index,
                "verifier": "bin/ssot/doc-governance-check.py",
                "metadata": "frontmatter",
                "required_frontmatter": ["status", "lifecycle", "owner", "last-reviewed"],
                "review_days": 30,
                "discoverability": "directory-index",
                "index": index,
                "workflow": "project-doc-change",
            }
        ],
        "rules": {
            "missing_frontmatter": {"severity": "warning"},
            "malformed_frontmatter": {"severity": "error"},
            "invalid_metadata": {"severity": "error"},
            "stale_review": {"severity": "warning"},
            "orphan_document": {"severity": "warning"},
            "missing_index": {"severity": "error"},
        },
    }


def test_tracked_scope_uses_git_index(tmp_path: Path) -> None:
    tracked = tmp_path / "docs" / "guide.md"
    ignored = tmp_path / "docs" / "ignored.md"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("# guide\n", encoding="utf-8")
    ignored.write_text("# ignored\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "docs/guide.md"], cwd=tmp_path, check=True)
    assert CHECKER.collect_markdown_files(tmp_path, scope="tracked") == [tracked.resolve()]


def test_frontmatter_and_freshness_are_reported(tmp_path: Path) -> None:
    index = tmp_path / "docs" / "SYSTEM-INDEX.md"
    doc = tmp_path / "docs" / "guide.md"
    index.parent.mkdir(parents=True)
    index.write_text("docs/guide.md\n", encoding="utf-8")
    doc.write_text(
        "---\nstatus: active\nlifecycle: contract\nowner: team\nlast-reviewed: 2020-01-01\n---\n# guide\n",
        encoding="utf-8",
    )
    result = CHECKER.check_file(
        doc,
        tmp_path,
        _registry(),
        {},
        date(2026, 7, 31),
    )
    rules = {finding["rule"] for finding in result}
    assert "stale_review" in rules
    assert "orphan_document" not in rules


def test_registry_requires_metadata_enums(tmp_path: Path, monkeypatch) -> None:
    registry_path = tmp_path / ".omo/_truth/registry/document-governance.yaml"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text("version: 1\nsurfaces: []\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "REGISTRY_PATH", registry_path)
    result = CHECKER.run(root=tmp_path, scope="workspace", strict=True)
    assert not result["ok"]
    assert any(finding["rule"] == "registry-integrity" for finding in result["findings"])


def test_warning_baseline_detects_budget_regression() -> None:
    registry = _registry()
    registry["warning_exceptions"] = {
        "version": 1,
        "policy": "no-new-warnings",
        "entries": [
            {
                "id": "legacy-stale-review",
                "rule": "stale_review",
                "surface": "docs",
                "max_findings": 1,
                "expires": "2026-10-31",
                "owner": "governance-team",
                "reason": "Legacy metadata migration.",
            }
        ],
    }
    findings = [
        {"path": "docs/guide.md", "rule": "stale_review", "severity": "warning"},
        {"path": "docs/other.md", "rule": "stale_review", "severity": "warning"},
    ]

    baseline, registry_findings = CHECKER.evaluate_warning_baseline(
        findings,
        registry,
        date(2026, 7, 31),
    )

    assert not registry_findings
    assert not baseline["ok"]
    assert baseline["over_budget"] == [
        {
            "bucket": "stale_review:docs",
            "count": 2,
            "max_findings": 1,
            "exception": "legacy-stale-review",
        }
    ]
