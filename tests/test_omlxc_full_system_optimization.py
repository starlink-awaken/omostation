"""
omlxc 全栈算力体系性能优化与柔性显存治理单元/集成测试 (ADR-0205)
"""

import sys
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT / "projects" / "omlxc" / "src"))

from omlxc.dataplane.cluster_partition import (
    HeterogeneousClusterRouter,
    NodePlacementDecision,
)
from omlxc.dataplane.power_profile import (
    PowerProfileGovernor,
    PowerScalingProfile,
    PowerSource,
)
from omlxc.dataplane.priority_queue import (
    PriorityVRAMScheduler,
    QueuedInferenceRequest,
    TaskPriority,
)
from omlxc.dataplane.vram_budget import (
    VRAMPressureTier,
    enforce_strict_headroom_admission,
    enforce_tiered_headroom_admission,
)


def test_balanced_tiered_vram_admission_levels():
    """验证柔性显存阶梯策略 (Green/Yellow/Orange/Red) 与 128G 内存适度放宽保护"""
    total_128g = 131072.0  # MB

    # 1. 显存使用 20GB -> GREEN 档位 (安全放行，预留 > 100GB)
    res_green = enforce_tiered_headroom_admission(
        model_id="qwen-3.8-27b",
        requested_tokens=4096,
        current_used_vram_mb=20000.0,
        total_node_vram_mb=total_128g,
    )
    assert res_green.admitted is True
    assert res_green.pressure_tier == VRAMPressureTier.GREEN
    assert res_green.system_reserved_mb > 100000.0

    # 2. 显存使用 92GB -> YELLOW 档位 (70% 软压缩建议，但依然放行，不生硬拦截)
    res_yellow = enforce_tiered_headroom_admission(
        model_id="qwen-3.8-27b",
        requested_tokens=4096,
        current_used_vram_mb=92000.0,
        total_node_vram_mb=total_128g,
    )
    assert res_yellow.admitted is True
    assert res_yellow.pressure_tier == VRAMPressureTier.YELLOW
    assert res_yellow.compaction_advised is True

    # 3. 显存使用 108GB -> RED 档位 (超过 82% 应急红线，触发防爆拦截)
    res_red = enforce_tiered_headroom_admission(
        model_id="qwen-3.8-27b",
        requested_tokens=4096,
        current_used_vram_mb=108000.0,
        total_node_vram_mb=total_128g,
    )
    assert res_red.admitted is False
    assert res_red.pressure_tier == VRAMPressureTier.RED
    assert "Emergency limit" in res_red.reason


def test_multi_agent_priority_vram_scheduler():
    """验证多 Agent 动态优先级调度 (P0 前台秒放行, P2 后台压力让路)"""
    scheduler = PriorityVRAMScheduler(total_node_vram_mb=131072.0)
    scheduler.set_vram_baseline(30000.0)

    # 1. P0 交互式请求 (夏明星前台 / 微信秒回) -> 立即放行
    req_p0 = QueuedInferenceRequest(
        request_id="req-p0-1",
        model_id="qwen-3.8-27b-dflash",
        priority=TaskPriority.P0_INTERACTIVE,
        requested_tokens=2048,
    )
    admitted, _, reason = scheduler.evaluate_admission(req_p0)
    assert admitted is True
    assert "P0 Interactive" in reason
    assert scheduler.acquire_slot(req_p0) is True

    # 2. 显存压力升高到 93GB (YELLOW) 时，P2 后台任务自动避让
    scheduler.set_vram_baseline(93000.0)
    req_p2 = QueuedInferenceRequest(
        request_id="req-p2-1",
        model_id="embed-bge-m3",
        priority=TaskPriority.P2_BACKGROUND,
        requested_tokens=8192,
    )
    admitted_p2, _, reason_p2 = scheduler.evaluate_admission(req_p2)
    assert admitted_p2 is False
    assert "deferred" in reason_p2

    scheduler.release_slot("req-p0-1")
    status = scheduler.get_queue_status()
    assert status["active_count"] == 0


def test_power_and_battery_adaptive_scaling():
    """验证插电 (AC) 与电池 (Battery) 自适应算力与能耗切换"""
    # 1. AC 模式 -> 满血 70+ tok/s 配置
    ac_profile = PowerProfileGovernor.get_profile(force_source=PowerSource.AC)
    assert ac_profile.spec_draft_n_max == 7
    assert ac_profile.max_batch_size == 32
    assert ac_profile.power_reduction_pct == 0.0

    # 2. 电池模式 -> 4 步安全投机，功耗下降 60%
    batt_profile = PowerProfileGovernor.get_profile(force_source=PowerSource.BATTERY)
    assert batt_profile.spec_draft_n_max == 4
    assert batt_profile.max_batch_size == 8
    assert batt_profile.power_reduction_pct == 60.0


def test_heterogeneous_cluster_partition_routing():
    """验证异构三节点智能路由分工 (Mac mini 向量 / Y7000P CUDA / MBP 主脑)"""
    # 1. 向量与重排 -> 路由至 Mac mini M4 24G
    dec_embed = HeterogeneousClusterRouter.route_model("embed-bge-m3")
    assert dec_embed.target_node_id == "mac-mini-m4-24g"
    assert "background vector pipeline" in dec_embed.affinity_reason

    dec_rerank = HeterogeneousClusterRouter.route_model("baai-bge-reranker-v2-m3-mlx-fp16")
    assert dec_rerank.target_node_id == "mac-mini-m4-24g"

    # 2. 视觉与 OCR -> 路由至 Y7000P RTX4070 8G CUDA
    dec_vision = HeterogeneousClusterRouter.route_model("vision")
    assert dec_vision.target_node_id == "y7000p-rtx4070-8g"
    assert "CUDA" in dec_vision.affinity_reason

    # 3. 复杂代码与 DFlash 2 投机 -> 路由至 MBP M5 Max 128G
    dec_code = HeterogeneousClusterRouter.route_model("qwen-3.8-27b-dflash")
    assert dec_code.target_node_id == "mbp-m5-max-128g"
    assert "DFlash 2" in dec_code.affinity_reason
