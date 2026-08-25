"""Tests for Domain Cartridge Packaging, Inspection, and Execution (ADR-0203)."""

import json
from pathlib import Path

import pytest

from cockpit.cartridge import CartridgeManifest, CartridgePackager, CartridgeRuntime


def test_cartridge_pack_inspect_and_run(tmp_path: Path):
    """Verify full end-to-end cartridge lifecycle."""
    src_dir = tmp_path / "weijian_cartridge_src"
    src_dir.mkdir()

    # 1. 准备卡带源目录
    manifest_data = {
        "cartridge_id": "cartridge-weijian-v1",
        "name": "卫健委信息化审批卡带",
        "version": "1.0.0",
        "domain": "work-weijian",
        "author": "Antigravity",
        "intent_patterns": ["等保三级", "立项申报", "互联互通测评"],
        "policy_rules": ["RULE-WEIJIAN-DATA-01", "RULE-PRIVACY-A11Y"],
        "required_models": ["deepseek-r1-7b"],
    }
    (src_dir / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")
    (src_dir / "rules.txt").write_text("医疗数据不出公有云", encoding="utf-8")

    pkg_file = tmp_path / "weijian.cartridge"

    # 2. 打包卡带
    manifest = CartridgePackager.pack(source_dir=src_dir, output_file=pkg_file)
    assert pkg_file.exists()
    assert manifest.manifest_hash != ""

    # 3. 检查卡带
    runtime = CartridgeRuntime(cartridge_path=pkg_file)
    inspected = runtime.inspect()
    assert inspected.cartridge_id == "cartridge-weijian-v1"
    assert inspected.domain == "work-weijian"
    assert "等保三级" in inspected.intent_patterns

    # 4. 沙箱执行
    result = runtime.execute(user_intent="请进行良乡医院等保三级测评立项申报")
    assert result["status"] == "success"
    assert result["matched_pattern"] == "等保三级"
    assert "RULE-WEIJIAN-DATA-01" in result["policies_enforced"]
