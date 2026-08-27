"""test_anti_corrosion_detector — 治理规则陈旧检测 test (防回归).

验证核心逻辑:
- detect_stale_rules() 检测陈旧规则
- suggest_fixes() 生成修复建议
- main() 正确输出结果
"""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "gac" / "anti-corrosion-detector.py"

GOV_CHECKS_CONTENT = """\
gac:
  version: '1.0'
  rules:
  - id: CR-TEST-1
    dimension: X1
    layer: L0
    name: Test rule 1
    check_type: audit_chain
    executor: [hook_pre_edit]
    lifecycle: active
    version: 1.0.0
    created_at: '2026-06-26'
  - id: CR-TEST-2
    dimension: X2
    layer: L1
    name: Test rule 2
    check_type: freshness
    executor: [omo_audit]
    lifecycle: deprecated
    version: 1.0.0
    created_at: '2026-06-26'
  - id: CR-TEST-3
    dimension: X3
    layer: L2
    name: Test rule 3
    check_type: value_roi
    executor: [ci_gate]
    lifecycle: removed
    version: 1.0.0
    created_at: '2026-06-26'
"""

LEGACY_CR_IDS_CONTENT = """\
LEGACY_CR_IDS = {
    "CR-LEGACY-1",
    "CR-LEGACY-2",
    "CR-LEGACY-3",
}
"""

ADR_CONTENT = """\
---
id: ADR-0999
title: "Test ADR"
status: PROPOSED
date: 2026-01-01
---

# ADR-0999: Test ADR

## Context

Test ADR content.
"""


def _load_module():
    """加载 anti-corrosion-detector 脚本为 module."""
    spec = importlib.util.spec_from_file_location("anti_corrosion_detector", SCRIPT)
    assert spec is not None and spec.loader is not None, f"无法加载 {SCRIPT}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_gov_checks(tmp_path: Path) -> Path:
    """造 governance-checks.yaml."""
    reg = tmp_path / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(GOV_CHECKS_CONTENT, encoding="utf-8")
    return reg


def _make_legacy_cr_ids(tmp_path: Path) -> Path:
    """造 governance-convergence-lint.py with LEGACY_CR_IDS."""
    lint = tmp_path / "bin" / "gac" / "governance-convergence-lint.py"
    lint.parent.mkdir(parents=True, exist_ok=True)
    lint.write_text(LEGACY_CR_IDS_CONTENT, encoding="utf-8")
    return lint


def _make_adr(tmp_path: Path, status: str = "PROPOSED", date: str = "2026-01-01"):
    """造 ADR 文件."""
    adr_dir = tmp_path / ".omo" / "_knowledge" / "decisions"
    adr_dir.mkdir(parents=True, exist_ok=True)
    content = ADR_CONTENT.replace("status: PROPOSED", f"status: {status}")
    content = content.replace("date: 2026-01-01", f"date: {date}")
    (adr_dir / "0999-test-adr.md").write_text(content, encoding="utf-8")


def test_detect_stale_rules_finds_deprecated(tmp_path, monkeypatch):
    """detect_stale_rules() 应检测到 deprecated 规则."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "GOV_CHECKS_YAML", tmp_path / ".omo/_truth/registry/governance-checks.yaml")
    monkeypatch.setattr(mod, "DECISIONS_DIR", tmp_path / ".omo/_knowledge/decisions")
    _make_gov_checks(tmp_path)
    findings = mod.detect_stale_rules()
    # Should find CR-TEST-2 (deprecated) and CR-TEST-3 (removed)
    stale_ids = [f["id"] for f in findings if "stale lifecycle" in f["reason"]]
    assert "CR-TEST-2" in stale_ids
    assert "CR-TEST-3" in stale_ids


def test_detect_stale_rules_finds_legacy_ids(tmp_path, monkeypatch):
    """detect_stale_rules() 应检测到 legacy CR IDs."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "GOV_CHECKS_YAML", tmp_path / ".omo/_truth/registry/governance-checks.yaml")
    monkeypatch.setattr(mod, "DECISIONS_DIR", tmp_path / ".omo/_knowledge/decisions")
    _make_gov_checks(tmp_path)
    _make_legacy_cr_ids(tmp_path)
    findings = mod.detect_stale_rules()
    legacy_ids = [f["id"] for f in findings if "Legacy CR ID" in f["reason"]]
    assert "CR-LEGACY-1" in legacy_ids
    assert "CR-LEGACY-2" in legacy_ids
    assert "CR-LEGACY-3" in legacy_ids


def test_detect_stale_rules_finds_old_proposed_adr(tmp_path, monkeypatch):
    """detect_stale_rules() 应检测到长期 PROPOSED 的 ADR."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "GOV_CHECKS_YAML", tmp_path / ".omo/_truth/registry/governance-checks.yaml")
    monkeypatch.setattr(mod, "DECISIONS_DIR", tmp_path / ".omo/_knowledge/decisions")
    _make_gov_checks(tmp_path)
    # Create ADR with old date (200 days ago)
    old_date = (datetime.now(UTC) - timedelta(days=200)).strftime("%Y-%m-%d")
    _make_adr(tmp_path, status="PROPOSED", date=old_date)
    findings = mod.detect_stale_rules()
    adr_findings = [f for f in findings if "ADR" in f.get("fix", "")]
    assert len(adr_findings) > 0
    assert any("ADR-0999" in f["id"] for f in adr_findings)


def test_detect_stale_rules_ignores_active_rules(tmp_path, monkeypatch):
    """detect_stale_rules() 应忽略 active 规则."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "GOV_CHECKS_YAML", tmp_path / ".omo/_truth/registry/governance-checks.yaml")
    monkeypatch.setattr(mod, "DECISIONS_DIR", tmp_path / ".omo/_knowledge/decisions")
    # Only active rules
    content = """\
gac:
  rules:
  - id: CR-ACTIVE-1
    lifecycle: active
"""
    reg = tmp_path / ".omo/_truth/registry/governance-checks.yaml"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(content, encoding="utf-8")
    findings = mod.detect_stale_rules()
    assert len(findings) == 0


def test_suggest_fixes_groups_by_area(tmp_path, monkeypatch):
    """suggest_fixes() 应按区域分组修复建议."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "GOV_CHECKS_YAML", tmp_path / ".omo/_truth/registry/governance-checks.yaml")
    monkeypatch.setattr(mod, "DECISIONS_DIR", tmp_path / ".omo/_knowledge/decisions")
    _make_gov_checks(tmp_path)
    _make_legacy_cr_ids(tmp_path)
    old_date = (datetime.now(UTC) - timedelta(days=200)).strftime("%Y-%m-%d")
    _make_adr(tmp_path, status="PROPOSED", date=old_date)
    fixes = mod.suggest_fixes()
    areas = [f["area"] for f in fixes]
    assert "governance-checks.yaml" in areas
    assert ".omo/_knowledge/decisions/" in areas


def test_main_returns_zero_when_clean(tmp_path, monkeypatch):
    """main() 应返回 0 当没有陈旧规则."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "GOV_CHECKS_YAML", tmp_path / ".omo/_truth/registry/governance-checks.yaml")
    monkeypatch.setattr(mod, "DECISIONS_DIR", tmp_path / ".omo/_knowledge/decisions")
    monkeypatch.setattr("sys.argv", ["anti-corrosion-detector.py"])
    content = """\
gac:
  rules:
  - id: CR-ACTIVE-1
    lifecycle: active
"""
    reg = tmp_path / ".omo/_truth/registry/governance-checks.yaml"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(content, encoding="utf-8")
    assert mod.main() == 0


def test_main_returns_one_when_stale(tmp_path, monkeypatch):
    """main() 应返回 1 当有陈旧规则."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "GOV_CHECKS_YAML", tmp_path / ".omo/_truth/registry/governance-checks.yaml")
    monkeypatch.setattr(mod, "DECISIONS_DIR", tmp_path / ".omo/_knowledge/decisions")
    monkeypatch.setattr("sys.argv", ["anti-corrosion-detector.py"])
    _make_gov_checks(tmp_path)
    assert mod.main() == 1


def test_main_json_output(tmp_path, monkeypatch, capsys):
    """main() --json 应输出 JSON."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "GOV_CHECKS_YAML", tmp_path / ".omo/_truth/registry/governance-checks.yaml")
    monkeypatch.setattr(mod, "DECISIONS_DIR", tmp_path / ".omo/_knowledge/decisions")
    _make_gov_checks(tmp_path)
    monkeypatch.setattr("sys.argv", ["anti-corrosion-detector.py", "--json"])
    mod.main()
    captured = capsys.readouterr()
    import json

    result = json.loads(captured.out)
    assert "findings" in result
    assert "fixes" in result
    assert "ok" in result
    assert result["ok"] is False
