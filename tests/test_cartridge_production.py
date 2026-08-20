"""Tests for Production Domain Cartridges (weijian-governance & family-hub) (ADR-0203)."""

from pathlib import Path
import pytest
from cockpit.cartridge import CartridgeRuntime

# Locate workspace root
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


def test_weijian_governance_cartridge_inspection_and_run():
    """Verify inspection and execution of weijian-governance cartridge."""
    cartridge_file = WORKSPACE_ROOT / "domains" / "cartridges" / "weijian-governance.cartridge"
    assert cartridge_file.exists(), f"Cartridge not found: {cartridge_file}"

    runtime = CartridgeRuntime(cartridge_file)
    manifest = runtime.inspect()
    assert manifest.cartridge_id == "cartridge-weijian-v1"
    assert manifest.domain == "work-weijian"
    assert "等保三级测评" in manifest.intent_patterns
    assert manifest.manifest_hash != ""

    # 测试意图沙箱执行
    result = runtime.execute(user_intent="请对区属良乡医院HIS升级项目进行等保三级测评立项审核")
    assert result["status"] == "success"
    assert result["matched_pattern"] == "等保三级测评"
    assert any("RULE-WEIJIAN-DATA-01" in p for p in result["policies_enforced"])


def test_family_hub_cartridge_inspection_and_run():
    """Verify inspection and execution of family-hub cartridge."""
    cartridge_file = WORKSPACE_ROOT / "domains" / "cartridges" / "family-hub.cartridge"
    assert cartridge_file.exists(), f"Cartridge not found: {cartridge_file}"

    runtime = CartridgeRuntime(cartridge_file)
    manifest = runtime.inspect()
    assert manifest.cartridge_id == "cartridge-family-hub-v1"
    assert manifest.domain == "family-hub"
    assert "家庭月度财务对账" in manifest.intent_patterns

    # 测试意图沙箱执行
    result = runtime.execute(user_intent="请对本月家庭月度财务对账数据进行汇总分析")
    assert result["status"] == "success"
    assert result["matched_pattern"] == "家庭月度财务对账"
