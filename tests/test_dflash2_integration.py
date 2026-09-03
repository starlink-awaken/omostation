"""
DFlash 2 块扩散投机解码全链路单元与集成测试 (ADR-0205)
"""

import sys
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT / "projects" / "omlxc" / "src"))

from omlxc.dataplane.dflash_backend import DFlashBackendManager, DFlashConfig
from omlxc.dataplane.vram_budget import DEFAULT_ARCH_PROFILES, enforce_strict_headroom_admission


def test_dflash_cli_args_construction():
    """验证 DFlash 2 命令行参数构建与两拍卷积/路径选择器参数配置"""
    cfg = DFlashConfig(
        target_model_path="/Users/xiamingxing/omlx/models/Qwen3.8-27B-UD-Q4_K_XL.gguf",
        draft_model_path="/Users/xiamingxing/omlx/models/Qwen3.8-27B-DFlash2-Q8_0.gguf",
        port=8196,
        spec_draft_n_max=7,
        cache_type_k="q8_0",
        cache_type_v="q8_0",
    )
    args = cfg.build_cli_args("/usr/local/bin/llama-server")

    assert "-m" in args
    assert "-md" in args
    assert "--spec-type" in args
    assert args[args.index("--spec-type") + 1] == "draft-dflash"
    assert "--spec-draft-n-max" in args
    assert args[args.index("--spec-draft-n-max") + 1] == "7"
    assert "--cache-type-k" in args
    assert args[args.index("--cache-type-k") + 1] == "q8_0"
    assert "--flash-attn" in args


def test_dflash_thermal_adaptive_scaling():
    """验证温控自适应调节 (满血 70 tok/s ➔ 降温 45 tok/s ➔ 熔断单模型)"""
    mgr = DFlashBackendManager()

    # 1. 正常工况 -> 满血 7 步投机预测
    assert mgr.adjust_for_thermal_state("NOMINAL") == 7

    # 2. 轻度升温 -> 降至 4 步投机预测
    assert mgr.adjust_for_thermal_state("FAIR") == 4
    assert mgr.adjust_for_thermal_state("WARM") == 4

    # 3. 高温过热 -> 降至 0 (自动关闭投机分支，降级至原生单模型逐字生成)
    assert mgr.adjust_for_thermal_state("SERIOUS") == 0
    assert mgr.adjust_for_thermal_state("CRITICAL") == 0


def test_dflash_vram_budget_within_60_percent_quota():
    """验证 DFlash 2 双模型在 128G 统一内存下严格处于 60% (76.8GB) 安全线内"""
    meta = DEFAULT_ARCH_PROFILES.get("qwen-3.8-27b-dflash")
    assert meta is not None
    assert meta.weights_vram_mb == 18500.0

    # 申请 32,768 满上下文时的准入评估 (当前基线使用 22GB)
    res = enforce_strict_headroom_admission(
        model_id="qwen-3.8-27b-dflash",
        requested_tokens=32768,
        current_used_vram_mb=22500.0,
        max_hard_quota_mb=76800.0,
    )
    assert res.admitted is True
    assert res.compaction_advised is False
    assert "Admitted" in res.reason


def test_dflash_status_report():
    """验证 DFlash 2 状态报告与无损性声明"""
    mgr = DFlashBackendManager()
    report = mgr.get_status_report()
    assert report["engine"] == "DFlash 2 (Block Diffusion)"
    assert report["lossless"] is True
    assert "53.3 ~ 70.0 tokens/s" in report["estimated_throughput"]
    assert report["estimated_vram_mb"] == 22500.0
