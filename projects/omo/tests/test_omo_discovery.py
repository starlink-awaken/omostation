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

    registry_path = tmp_path / ".omo" / "_truth" / "task-center" / "discovery-registry.yaml"
    assert registry_path.exists()
    assert registry["entries"] == [
        {
            "blueprint_id": "BP-ALPHA",
            "title": "Durable runtime packet",
            "phase": 6,
            "milestone": "W2",
            "source_doc": "docs/alpha.md",
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
    assert task["source_docs"] == [".omo/_knowledge/design/plans/archive/phase6-program-plan.md", "docs/template.md"]
    assert validate_task_file(task_path) == []
