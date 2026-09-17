import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_value_metrics_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_value_metrics_reads_registry_backed_delivery_soft_gate(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    value_dir = tmp_path / ".omo/_truth"
    registry_dir = value_dir / "registry"
    registry_dir.mkdir(parents=True)
    (value_dir / "x3-value-stack.yaml").write_text(
        "domains:\n  CARDS:\n    x1_audit:\n      implemented: true\n  OMO:\n    x1_audit:\n      implemented: true\n",
        encoding="utf-8",
    )
    (registry_dir / "x3-delivery-soft-gate.yaml").write_text(
        "status: deprecated\ndeprecated: true\nsuperseded_by: BET-Y1Q1-T1-01\nx3_delivery_soft_gate:\n  enabled: false\n",
        encoding="utf-8",
    )

    report = module.collect_value_metrics()

    assert report["x3-value-stack"]["available"] is True
    assert report["x3-value-stack"]["domain_count"] == 2
    assert report["x3-delivery-soft-gate"]["available"] is True
    assert report["x3-delivery-soft-gate"]["status"] == "deprecated"
    assert report["x3-delivery-soft-gate"]["enabled"] is False
    assert report["x3-delivery-soft-gate"]["superseded_by"] == "BET-Y1Q1-T1-01"


def test_value_metrics_reads_domains_after_frontmatter(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    value_dir = tmp_path / ".omo/_truth"
    value_dir.mkdir(parents=True)
    (value_dir / "x3-value-stack.yaml").write_text(
        """---
status: active
---

documentation_contract:
  ssot_role: authoritative_value_source

domains:
  CARDS:
    x1_audit:
      implemented: true
  OMO:
    x1_audit:
      implemented: true
""",
        encoding="utf-8",
    )
    (value_dir / "registry").mkdir()
    (value_dir / "registry/x3-delivery-soft-gate.yaml").write_text(
        "status: deprecated\nx3_delivery_soft_gate:\n  enabled: false\n",
        encoding="utf-8",
    )

    report = module.collect_value_metrics()

    assert report["x3-value-stack"]["available"] is True
    assert report["x3-value-stack"]["domain_count"] == 2
    assert report["x3-value-stack"]["entries"] == 2


def test_value_metrics_fail_closed_when_source_missing(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    report = module.collect_value_metrics()
    assert report["x3-value-stack"]["available"] is False
    assert report["x3-delivery-soft-gate"]["available"] is False
