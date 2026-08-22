"""build_configured_adapters 必须给 LM Studio 系后端注入受控上下文的加载选项.

背景 (2026-08-22 实测): 数据面 ensure_loaded 触发的 lms load 若不带 -c,
LM Studio 会按全局 defaultContextLength 加载 — 本机配置为 "max", 曾把
模型按 262144/852736 上下文加载, 28GB+ 权重直接打穿统一内存。
"""

from __future__ import annotations

from pathlib import Path

from omlxc.config import (
    AppConfig,
    BackendConfig,
    DaemonConfig,
    ModelConfig,
    NodeConfig,
    PlacementConfig,
    StorageConfig,
)
from omlxc.daemon.composition import build_configured_adapters
from omlxc.domain import BackendKind


def _config(*context_limits: int) -> AppConfig:
    return AppConfig(
        daemon=DaemonConfig(socket_path=Path("/tmp/omlxcd.sock")),
        storage=StorageConfig(database_path=Path("/tmp/state.db")),
        nodes=(NodeConfig(id="node", display_name="Node", platform="macos", memory_gb=16),),
        models=tuple(
            ModelConfig(id=f"m-{index}", category="llm", role="chat", engine="omlx")
            for index in range(len(context_limits))
        ),
        backends=(
            BackendConfig(
                id="lms",
                node_id="node",
                kind=BackendKind.LM_STUDIO,
                base_url="http://127.0.0.1:1234",
            ),
        ),
        placements=tuple(
            PlacementConfig(
                id=f"p-{index}",
                model_id=f"m-{index}",
                backend_id="lms",
                backend_model_id=f"bm-{index}",
                context_limit=limit,
                memory_gb=1,
            )
            for index, limit in enumerate(context_limits)
        ),
    )


def test_lm_studio_adapter_gets_min_context_limit_as_load_default() -> None:
    adapters = build_configured_adapters(_config(32768, 16384, 16384))
    adapter = adapters["lms"]
    # 私有属性断言是刻意的: 该值直接决定 ensure_loaded 的 lms load -c 参数
    assert adapter._load_options.context_length == 16384  # type: ignore[attr-defined]
    assert adapter._load_options.yes is True  # type: ignore[attr-defined]


def test_backend_without_placements_gets_no_load_options() -> None:
    adapters = build_configured_adapters(_config())
    adapter = adapters["lms"]
    assert adapter._load_options.context_length is None  # type: ignore[attr-defined]


def test_non_lm_backend_ignores_context_length() -> None:
    config = _config(16384)
    config = config.model_copy(update={"backends": (
        BackendConfig(
            id="lms",
            node_id="node",
            kind=BackendKind.OMLX_APP,
            base_url="http://127.0.0.1:8000",
        ),
    )})
    adapters = build_configured_adapters(config)
    # omlx-app 后端没有 load_options 概念, 不应因传入 context_length 而报错
    assert "lms" in adapters
