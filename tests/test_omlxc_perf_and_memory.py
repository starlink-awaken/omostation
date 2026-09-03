"""
omlxc 算力全栈加速与 128G 内存严苛防护单元与集成测试 (ADR-0197/ADR-0203)
"""

import sys
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT / "projects" / "omlxc" / "src"))

from omlxc.dataplane.prefix_snapshot import StaticPrefixSnapshotManager
from omlxc.dataplane.triage import (
    ComplexityTier,
    TriageClassifier,
    resolve_tier_target_model,
)
from omlxc.dataplane.vram_budget import (
    ContextCompactor,
    VRAMBudgetEstimator,
    enforce_strict_headroom_admission,
    reclaim_metal_memory_pool,
)
from omlxc.domain.protocols import ChatMessage


def test_strict_60_percent_vram_quota_admission():
    """验证 60% 物理显存硬门禁 (76.8GB) 与准入拦截"""
    # 1. 正常请求 (当前使用 20GB, 申请 4k token) -> 准入通过
    res_pass = enforce_strict_headroom_admission(
        model_id="qwen-3.8-27b",
        requested_tokens=4096,
        current_used_vram_mb=20000.0,
        max_hard_quota_mb=76800.0,
    )
    assert res_pass.admitted is True
    assert res_pass.compaction_advised is False

    # 2. 突发极端长文本请求 (当前使用 75GB, 申请 32k token) -> 触发硬上限拦截与压缩建议
    res_block = enforce_strict_headroom_admission(
        model_id="qwen-3.8-27b",
        requested_tokens=32768,
        current_used_vram_mb=76000.0,
        max_hard_quota_mb=76800.0,
    )
    assert res_block.admitted is False
    assert res_block.compaction_advised is True
    assert "Emergency limit" in res_block.reason or "quota" in res_block.reason.lower()


def test_metal_memory_pool_reclamation():
    """验证推理后 Metal 显存池主动回收机制"""
    stats = reclaim_metal_memory_pool()
    assert "gc_collected" in stats
    assert "metal_cleared" in stats


def test_static_prefix_snapshot_lifecycle(tmp_path):
    """验证 0ms TTFT 静态前缀快照的注册、校验与失效逻辑"""
    mgr = StaticPrefixSnapshotManager(root_dir=tmp_path / "snapshots")

    system_prompt_v1 = "你是由夏明星主理的 omostation 业务操作系统助手。"

    # 注册快照
    rec = mgr.register_or_update_snapshot(
        snapshot_id="test-agent-prefix",
        model_id="qwen-3.8-27b",
        prefix_text=system_prompt_v1,
    )
    assert rec.is_warm is True
    assert (tmp_path / "snapshots" / "test-agent-prefix.kv").exists()

    # 验证命中
    assert mgr.is_valid_and_warm("test-agent-prefix", system_prompt_v1) is True

    # 验证变更后哈希不匹配自动失效
    system_prompt_v2 = "你是由夏明星主理的 omostation 助手 (V2 新规则)。"
    assert mgr.is_valid_and_warm("test-agent-prefix", system_prompt_v2) is False


def test_two_tier_triage_routing():
    """验证双梯队极速分诊路由逻辑"""
    classifier = TriageClassifier()

    # 1. 短指令 -> FAST 梯队 -> 路由至 coding-fast (9B)
    msg_fast = (ChatMessage(role="user", content="请帮我拟一条 20 字微信提醒"),)
    res_fast = classifier.classify(messages=msg_fast, context_tokens=50)
    assert res_fast.tier == ComplexityTier.FAST
    assert resolve_tier_target_model(res_fast.tier) == "coding-fast"

    # 2. 深度架构/长文本指令 -> REASONING 梯队 -> 路由至 qwen-3.8-27b
    msg_deep = (ChatMessage(role="user", content="请针对分布式一致性协议与 memory leak 进行 refactor architecture 深度推演"),)
    res_deep = classifier.classify(messages=msg_deep, context_tokens=1000)
    assert res_deep.tier == ComplexityTier.REASONING
    assert resolve_tier_target_model(res_deep.tier) == "qwen-3.8-27b"
