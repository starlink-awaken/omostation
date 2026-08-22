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
    PoliciesConfig,
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


def test_lm_studio_adapter_gets_idle_ttl_as_load_default() -> None:
    """数据面 ensure_loaded 触发的加载必须带默认 TTL, 否则模型无限期驻留
    直到手动卸载或机器重启 (2026-08-22 实测: mac-mini 上出现 TTL 为空的
    孤儿 qwythos 残留, 根因是 composition.py 此前只注入 context_length,
    从未注入 ttl_seconds)。"""
    config = _config(16384).model_copy(
        update={"policies": PoliciesConfig(idle_ttl_seconds=1800)}
    )
    adapters = build_configured_adapters(config)
    adapter = adapters["lms"]
    assert adapter._load_options.context_length == 16384  # type: ignore[attr-defined]
    assert adapter._load_options.ttl_seconds == 1800  # type: ignore[attr-defined]


def test_idle_ttl_zero_does_not_produce_invalid_ttl_seconds() -> None:
    """idle_ttl_seconds=0 是策略里"显式声明不设超时"的合法值, 但
    LmsLoadOptions.ttl_seconds 要求 ge=1 —— 0 必须被过滤掉, 不能直接
    透传导致 schema 校验炸掉。"""
    config = _config(16384).model_copy(update={"policies": PoliciesConfig(idle_ttl_seconds=0)})
    adapters = build_configured_adapters(config)
    adapter = adapters["lms"]
    assert adapter._load_options.ttl_seconds is None  # type: ignore[attr-defined]
    assert adapter._load_options.context_length == 16384  # type: ignore[attr-defined]


def test_no_context_limit_but_idle_ttl_still_creates_load_options() -> None:
    """没有 placement context_limit 时也不能因此丢掉 TTL 注入 —— 两个
    维度是独立的, 缺一个不该拖累另一个。"""
    config = _config().model_copy(update={"policies": PoliciesConfig(idle_ttl_seconds=900)})
    adapters = build_configured_adapters(config)
    adapter = adapters["lms"]
    assert adapter._load_options.context_length is None  # type: ignore[attr-defined]
    assert adapter._load_options.ttl_seconds == 900  # type: ignore[attr-defined]
