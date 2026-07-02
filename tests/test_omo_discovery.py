from __future__ import annotations

from pathlib import Path

import yaml

from omo.omo_discovery import discover_task_blueprints, instantiate_task_template
from omo.omo_task_schema import validate_task_file


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_discover_task_blueprints_writes_truth_registry(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "alpha.md").write_text(
        """---
omo:
  blueprint:
    id: BP-ALPHA
    title: Durable runtime packet
    phase: 6
    milestone: W2
    risk_level: L1
    allowed_operation_level: L1
    source_docs:
      - .omo/_knowledge/design/plans/archive/phase6-wave1-execution-plan.md
    deliverables:
      - .omo/_knowledge/summaries/phase6/phase6-wave2-closeout.md
    evidence_required:
      - discovery registry reconciled
    test_plan:
      - python3 -m pytest .omo/tests/test_omo_discovery.py -q
---

# Alpha
""",
        encoding="utf-8",
    )

    registry = discover_task_blueprints(tmp_path, docs)

    registry_path = (
        tmp_path / ".omo" / "_truth" / "task-center" / "discovery-registry.yaml"
    )
    assert registry_path.exists()
    artifact_path = (
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "task-center"
        / "discovery"
    )
    assert any(
        path.name.startswith("discovery-registry-")
        for path in artifact_path.glob("*.yaml")
    )
    assert registry["entries"] == [
        {
            "blueprint_id": "BP-ALPHA",
            "title": "Durable runtime packet",
            "phase": 6,
            "milestone": "W2",
            "source_doc": "docs/alpha.md",
        }
    ]


def test_discover_task_blueprints_accepts_multi_document_frontmatter(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "multi.md").write_text(
        """---
status: active
owner: governance
---
omo:
  blueprint:
    id: BP-MULTI
    title: Multi-doc blueprint
    phase: 7
    milestone: W3
    risk_level: L2
    allowed_operation_level: L1
    source_docs:
      - .omo/_knowledge/design/plans/archive/phase7-program-plan.md
---

# Multi
""",
        encoding="utf-8",
    )

    registry = discover_task_blueprints(tmp_path, docs)

    assert registry["entries"] == [
        {
            "blueprint_id": "BP-MULTI",
            "title": "Multi-doc blueprint",
            "phase": 7,
            "milestone": "W3",
            "source_doc": "docs/multi.md",
        }
    ]


def test_instantiate_task_template_creates_valid_blocked_task_packet(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "template.md").write_text(
        """---
omo:
  blueprint:
    id: BP-DISCOVERY
    title: Discovery packet
    phase: 6
    milestone: W2
    risk_level: L1
    allowed_operation_level: L1
    source_docs:
      - .omo/_knowledge/design/plans/archive/phase6-program-plan.md
    deliverables:
      - .omo/_knowledge/summaries/phase6/phase6-wave2-closeout.md
    evidence_required:
      - packet instantiated from blueprint
    test_plan:
      - python3 -m pytest .omo/tests/test_omo_discovery.py -q
---
""",
        encoding="utf-8",
    )
    discover_task_blueprints(tmp_path, docs)

    result = instantiate_task_template(
        tmp_path,
        blueprint_id="BP-DISCOVERY",
        task_id="P6-G2-DISCOVERY-TEMPLATES-PACKET",
        title="Land the discovery and templates packet",
    )

    task_path = tmp_path / result["task_ref"]
    assert task_path.exists()
    task = _load_yaml(task_path)
    assert task["id"] == "P6-G2-DISCOVERY-TEMPLATES-PACKET"
    assert task["status"] == "blocked"
    assert task["phase"] == 6
    assert task["milestone"] == "W2"
    assert task["source_docs"] == [
        ".omo/_knowledge/design/plans/archive/phase6-program-plan.md",
        "docs/template.md",
    ]
    assert any(
        path.name.startswith("P6-G2-DISCOVERY-TEMPLATES-PACKET-blocked-")
        for path in (
            tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "tasks"
        ).glob("*.yaml")
    )
    assert validate_task_file(task_path) == []


def test_instantiate_task_template_accepts_multi_document_registry(tmp_path: Path):
    registry_path = (
        tmp_path / ".omo" / "_truth" / "task-center" / "discovery-registry.yaml"
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "entries: []\n"
        "blueprints:\n"
        "  BP-MULTI:\n"
        "    id: BP-MULTI\n"
        "    phase: 8\n"
        "    milestone: W4\n"
        "    risk_level: L1\n"
        "    allowed_operation_level: L0\n"
        "    source_doc: docs/multi.md\n"
        "    source_docs:\n"
        "      - .omo/_knowledge/design/plans/archive/phase8-program-plan.md\n"
        "    deliverables:\n"
        "      - .omo/_knowledge/summaries/phase8/phase8-closeout.md\n"
        "    evidence_required:\n"
        "      - instantiated from multi-doc registry\n",
        encoding="utf-8",
    )

    result = instantiate_task_template(
        tmp_path,
        blueprint_id="BP-MULTI",
        task_id="P8-G1-MULTI-DOC-BLUEPRINT",
        title="Instantiate multi-doc discovery registry blueprint",
    )

    task_path = tmp_path / result["task_ref"]
    task = _load_yaml(task_path)
    assert task["id"] == "P8-G1-MULTI-DOC-BLUEPRINT"
    assert task["phase"] == 8
    assert task["source_docs"] == [
        ".omo/_knowledge/design/plans/archive/phase8-program-plan.md",
        "docs/multi.md",
    ]
