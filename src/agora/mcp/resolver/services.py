"""BOS 服务注册表 — POC_SERVICES 定义"""

from __future__ import annotations

import os

from .services_types import (  # ISC-34 第一步: types/patterns 提取 (God Module 拆分)
    BOS_URI_DOMAIN_PATTERN,
    BOS_URI_DOMAINS,
    BOS_URI_PATTERN,
    BosService,
    Transport,
)

# re-export 保下游兼容 (from agora.mcp.resolver.services import BosService 仍工作)
__all__ = [
    "BOS_URI_DOMAINS",
    "BOS_URI_DOMAIN_PATTERN",
    "BOS_URI_PATTERN",
    "BosService",
    "Transport",
]


def _with_uv_package(service: BosService) -> list[str]:
    """Normalize legacy uv run commands for workspace packages."""
    cmd = list(service.command)
    if len(cmd) < 2 or cmd[0] != "uv" or cmd[1] != "run":
        return cmd
    if "--package" in cmd:
        return cmd
    if "--directory" not in cmd:
        return cmd
    if not service.package:
        return cmd
    return ["uv", "run", "--package", service.package, *cmd[2:]]


# ── POC_SERVICES: 声明式加载 (YAML > 硬编码 fallback) ─────────
# 1. 加载顺序: AGORA_BOS_REGISTRY 环境变量 → etc/bos-services.yaml → 硬编码 fallback
# 2. `AGORA_BOS_REGISTRY=none` 强制使用硬编码 fallback
# 3. 新增路由请编辑 etc/bos-services.yaml, 勿改本文件


def _fallback_services() -> list[BosService]:
    """硬编码 fallback + internal transport 单源 (services_fallback + services_internal)."""
    from .services_fallback import _FALLBACK_SERVICES
    from .services_internal import _INTERNAL_SERVICES

    return list(_FALLBACK_SERVICES) + list(_INTERNAL_SERVICES)


def _load_services() -> list[BosService]:
    """加载 BOS 服务注册表，优先 YAML 声明式，fallback 到硬编码。

    加载顺序:
    1. AGORA_BOS_REGISTRY 环境变量指定的 YAML 路径
    2. etc/bos-services.yaml (项目默认)
    3. _FALLBACK_SERVICES + _INTERNAL_SERVICES (硬编码，零依赖)
    """
    # env=none → 强制 fallback
    if os.environ.get("AGORA_BOS_REGISTRY", "").lower() == "none":
        return _fallback_services()

    candidates = []
    env_path = os.environ.get("AGORA_BOS_REGISTRY", "")
    if env_path:
        candidates.append(env_path)

    # 项目默认路径
    here = os.path.dirname(os.path.abspath(__file__))
    # resolver/ → mcp/ → resolver/ → agora/ → src/ → agora/ → projects/ → workspace/
    # 更健壮的方式：通过 _resolve_agora_root 找到项目根
    try:
        from agora.mcp.resolver.bos_registry import DEFAULT_REGISTRY_PATH

        default_yaml = str(DEFAULT_REGISTRY_PATH)
    except Exception:  # defensive fallback
        default_yaml = os.path.join(
            here, "..", "..", "..", "..", "etc", "bos-services.yaml"
        )
    candidates.append(os.path.normpath(default_yaml))

    for path in candidates:
        if os.path.exists(path):
            try:
                from agora.mcp.resolver.bos_registry import load_from_yaml

                return load_from_yaml(path)
            except Exception as exc:  # defensive fallback
                import logging

                logging.getLogger(__name__).warning(
                    "BOS YAML 加载失败 (%s), 使用 fallback: %s", path, exc
                )
                break

    return _fallback_services()


POC_SERVICES: list[BosService] = _load_services()
