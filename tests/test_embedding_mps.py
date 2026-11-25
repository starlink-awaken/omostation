"""BET-Y1Q4-T3-02 embedding/rerank: device, hybrid scoring, budgets, red lines."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_GUARD_SRC = ROOT / "projects/omlxc/src/omlxc/dataplane/embedding_mps.py"
if not _GUARD_SRC.is_file():
    pytest.skip(
        f"{_GUARD_SRC} 不在（projects/omlxc 未检出）—— 本模块在**模块级**加载它, "
        "缺席会让整个 tests/ 平面 collection 中断（5 errors, 一条都跑不了）。"
        "属检出形态, 不是回归",
        allow_module_level=True,
    )


EMB = _load("embedding_mps", "projects/omlxc/src/omlxc/dataplane/embedding_mps.py")
RR = _load("reranker", "projects/omlxc/src/omlxc/dataplane/reranker.py")


def _hf_model_cached(repo_id: str) -> bool:
    """HF 本地缓存探测: benchmark 测试在 HF_HUB_OFFLINE=1 下跑真模型,
    缓存缺模型时 OSError 连接失败属环境缺失而非回归 → skip 而非假失败。"""
    import os

    hub = Path(
        os.environ.get("HF_HUB_HOME")
        or os.environ.get("HF_HOME")
        or Path.home() / ".cache/huggingface"
    ) / "hub"
    return (hub / f"models--{repo_id.replace('/', '--')}").is_dir()


def _omlxc_mlx_importable() -> bool:
    """真实前提：omlxc 的 uv 环境能 import mlx.core。

    `_hf_model_cached` 只证明**模型权重在本地缓存**，不证明引擎跑得起来 ——
    本机实测 `ModuleNotFoundError: No module named 'mlx'`，流水线以
    `RuntimeError: rerank model unavailable` 红（2026-11-25）。判据问被检对象本身。
    """
    try:
        probe = subprocess.run(
            ["uv", "run", "--directory", str(ROOT / "projects" / "omlxc"),
             "python", "-c", "import mlx.core"],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


requires_fast_model = pytest.mark.skipif(
    not _hf_model_cached(EMB.MODEL_TIERS["fast"]),
    reason=f"fast tier 模型 {EMB.MODEL_TIERS['fast']} 不在 HF 本地缓存 (离线模式加载必败, 属环境缺失)",
)

requires_mlx_runtime = pytest.mark.skipif(
    not _omlxc_mlx_importable(),
    reason="omlxc 的 uv 环境无 mlx/mlx_lm (引擎降级, benchmark 无法产出报告) —— 环境缺失, 非回归",
)


def test_offline_env_enforced():
    import os

    assert os.environ.get("HF_HUB_OFFLINE") == "1"


def test_device_resolution_no_cuda_branch():
    dev = EMB.resolve_device()
    assert dev in ("mps", "cpu")


def test_model_tiers_single_source():
    assert EMB.MODEL_TIERS["fast"] == "BAAI/bge-small-zh-v1.5"
    assert EMB.MODEL_TIERS["full"] == "BAAI/bge-m3"
    assert EMB.DEFAULT_TIER == "fast"


def test_tf_weights_normalized():
    w = EMB.EmbeddingEngine._tf_weights("a a b")
    assert w == {"a": 2 / 3, "b": 1 / 3}


def _omlxc_benchmark() -> dict:
    """Heavy-engine assertions ride the omlxc venv via the verify contract itself."""
    import json
    import subprocess

    rc = subprocess.run(
        [
            "uv",
            "run",
            "--directory",
            str(ROOT / "projects/omlxc"),
            "python",
            "-m",
            "omlxc.dataplane.embedding_mps_benchmark",
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert rc.returncode == 0, rc.stdout[-400:] + rc.stderr[-400:]
    return json.loads(rc.stdout)


@requires_fast_model
@requires_mlx_runtime
def test_engine_hybrid_and_budget():
    report = _omlxc_benchmark()
    assert report["embedding"]["single_encode_ms"] <= EMB.LATENCY_BUDGET_MS["single_encode"]
    assert report["embedding"]["checks"]["hybrid_relevant_ranked"] is True


@requires_fast_model
@requires_mlx_runtime
def test_reranker_orders_and_budget():
    report = _omlxc_benchmark()
    rerank = report["rerank"]
    assert rerank["checks"]["planted_top1_ranked_first"] is True
    assert rerank["elapsed_ms"] <= RR.LATENCY_BUDGET_MS
    # reranker-large pending download → dense fallback is the documented degraded mode
    assert rerank["degraded"] is True
