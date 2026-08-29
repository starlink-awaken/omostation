#!/usr/bin/env python3
"""
omlxc 全栈算力体系与多节点异构协同综合基准演练 (ADR-0205)
"""

import json
import sys
import time
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT / "projects" / "omlxc" / "src"))

from omlxc.dataplane.cluster_partition import HeterogeneousClusterRouter
from omlxc.dataplane.power_profile import PowerProfileGovernor, PowerSource
from omlxc.dataplane.priority_queue import PriorityVRAMScheduler, QueuedInferenceRequest, TaskPriority
from omlxc.dataplane.vram_budget import (
    DEFAULT_ARCH_PROFILES,
    VRAMPressureTier,
    enforce_tiered_headroom_admission,
    reclaim_metal_memory_pool,
)
from omlxc.dataplane.dflash_backend import DFlashBackendManager


def run_full_cluster_benchmark():
    print("\n" + "=" * 80)
    print(" 🌟 omostation (omlxc) 全栈本地算力体系综合基准与调优演练")
    print("=" * 80)

    # 1. 异构三节点算力分工与流水线对账
    print("\n【模块 1】异构三节点算力分工与路由对账...")
    test_models = [
        ("embed-bge-m3", "知识检索与向量化"),
        ("baai-bge-reranker-v2-m3-mlx-fp16", "长文档重排序"),
        ("vision", "图像与文档 OCR 视觉解析"),
        ("qwen-3.8-27b-dflash", "核心业务决策与 70 tok/s 极速公文"),
        ("coding", "复杂系统架构与代码重构"),
    ]
    for model_id, desc in test_models:
        decision = HeterogeneousClusterRouter.route_model(model_id)
        print(f" -> [{desc}] {model_id:32} ➔ 节点: {decision.target_node_name}")
        print(f"    理由: {decision.affinity_reason}")

    # 2. 全量模型显存预算与 75% 柔性门禁评估
    print("\n【模块 2】全量模型显存预算画像与 75% 柔性门禁 (128GB Unified Memory)...")
    print(f" {'模型名称':<28} | {'基础显存':<10} | {'32k 上下文':<12} | {'门禁评级':<10} | {'安全余量':<12}")
    print("-" * 80)
    for model_id, meta in DEFAULT_ARCH_PROFILES.items():
        res = enforce_tiered_headroom_admission(
            model_id=model_id,
            requested_tokens=32768,
            current_used_vram_mb=meta.weights_vram_mb,
            total_node_vram_mb=131072.0,
        )
        total_mb = res.total_projected_mb
        margin_gb = res.system_reserved_mb / 1024.0
        print(f" {model_id:<28} | {meta.weights_vram_mb/1024.0:6.1f} GB | {total_mb/1024.0:6.1f} GB   | {res.pressure_tier.value.upper():<10} | {margin_gb:6.1f} GB")

    # 3. 多 Agent 动态优先级调度与前台零等待抢占
    print("\n【模块 3】多 Agent 动态优先级调度与前台零等待抢占仿真...")
    scheduler = PriorityVRAMScheduler(total_node_vram_mb=131072.0)
    scheduler.set_vram_baseline(40000.0)

    p0_req = QueuedInferenceRequest("req-p0", "qwen-3.8-27b-dflash", TaskPriority.P0_INTERACTIVE, 4096)
    p1_req = QueuedInferenceRequest("req-p1", "coding", TaskPriority.P1_PIPELINE, 8192)
    p2_req = QueuedInferenceRequest("req-p2", "embed-bge-m3", TaskPriority.P2_BACKGROUND, 16384)

    p0_pass, _, p0_reason = scheduler.evaluate_admission(p0_req)
    p1_pass, _, p1_reason = scheduler.evaluate_admission(p1_req)
    scheduler.set_vram_baseline(95000.0)  # 模拟高压环境
    p2_pass, _, p2_reason = scheduler.evaluate_admission(p2_req)

    print(f" -> P0 前台即时交互 (夏明星/微信)  : {'✅ 立即抢占执行' if p0_pass else '❌ 排队'} ({p0_reason})")
    print(f" -> P1 业务流水线 (Agent SOP)     : {'✅ 正常调度' if p1_pass else '❌ 排队'} ({p1_reason})")
    print(f" -> P2 后台离线索引 (向量更新)    : {'✅ 允许' if p2_pass else '⏸️ 自动避让延后'} ({p2_reason})")

    # 4. 电源自适应 (AC / Battery) 性能画像
    print("\n【模块 4】电源自适应功耗管理...")
    for source in [PowerSource.AC, PowerSource.BATTERY]:
        prof = PowerProfileGovernor.get_profile(source)
        print(f" -> [{prof.source.value.upper()} 模式]: spec_steps={prof.spec_draft_n_max} | 批大小={prof.max_batch_size} | 功耗节约={prof.power_reduction_pct}%")
        print(f"    策略: {prof.description}")

    # 5. Metal 显存回收
    print("\n【模块 5】Metal 缓存池与垃圾回收...")
    reclaim = reclaim_metal_memory_pool()
    print(f" -> Metal 显存释放状态: {reclaim['metal_cleared']} | GC 回收对象: {reclaim['gc_collected']}")

    print("\n" + "=" * 80)
    print(" 🎉 omlxc 全栈本地算力体系优化已全面就绪！")
    print("=" * 80)


if __name__ == "__main__":
    run_full_cluster_benchmark()
