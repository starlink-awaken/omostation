"""BOS YAML 注册表加载器 — 声明式替代 POC_SERVICES 硬编码。

用法:
    from agora.mcp.resolver.bos_registry import load_from_yaml, DEFAULT_REGISTRY_PATH

    services = load_from_yaml("/path/to/bos-services.yaml")
    或
    services = load_from_yaml()  # 使用环境变量 AGORA_BOS_REGISTRY 或默认路径

环境变量:
    AGORA_BOS_REGISTRY — 覆盖 YAML 注册表路径（默认: <agora_root>/etc/bos-services.yaml）
"""

from __future__ import annotations

import os
import pathlib
import re
from typing import Any

import yaml


def _resolve_agora_root() -> pathlib.Path:
    """找到 agora 项目根目录。"""
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    env = os.environ.get("AGORA_ROOT", "")
    if env:
        return pathlib.Path(env)
    return pathlib.Path.cwd()


DEFAULT_REGISTRY_PATH = _resolve_agora_root() / "etc" / "bos-services.yaml"


# ── 从 BOS_URI_PATTERN 和 BosService 定义动态推导校验集 ──


def _get_valid_domains() -> set[str]:
    """从 BOS_URI_PATTERN 正则提取合法 domain 集合。"""
    from agora.mcp.resolver.services import BOS_URI_PATTERN

    # BOS_URI_PATTERN = r"^bos://(?P<domain>memory|governance|...)/(?P<package>...)/(?P<action>...)$"
    match = re.search(r"\(\?P<domain>([^)]+)\)", BOS_URI_PATTERN.pattern)
    if match:
        return set(match.group(1).split("|"))
    return set()


def _get_valid_transports() -> set[str]:
    """从 Transport 类型字面量推导合法 transport 集合。"""
    try:
        from agora.mcp.resolver.services import Transport

        # Transport = Literal["stdio", "internal", "http", "mcp_stdio"]
        if hasattr(Transport, "__args__"):
            return set(Transport.__args__)
    except Exception:  # defensive fallback
        pass
    # `inline` is reserved for self-identifier / i0_route:pending placeholder
    # entries (e.g. bos://agora/metrics, bos://agora/registry). They are
    # not real invokable services — callers should treat them as
    # documentation anchors. The validator admits them so the registry
    # can carry route metadata for services that haven't been wired into
    # a real transport yet.
    return {"stdio", "internal", "http", "mcp_stdio", "mcp_proxy", "inline"}


# ── 数据转换 ──


def _dict_to_bos_service(data: dict[str, Any]) -> object:
    """将 YAML dict 转换为 BosService 对象。"""
    from agora.mcp.resolver.services import BosService

    return BosService(
        uri=data["uri"],
        domain=data["domain"],
        package=data.get("package", ""),
        action=data["action"],
        transport=data.get("transport", "stdio"),
        command=data.get("command", []),
        module_path=data.get("module_path", ""),
        func_name=data.get("func_name", ""),
        http_url=data.get("http_url", ""),
        description=data.get("description", ""),
        mcp_tool=data.get("mcp_tool", "") or "",
        tools=list(data.get("tools") or []),
    )


def load_from_yaml(path: str | pathlib.Path | None = None) -> list:
    """从 YAML 文件加载 BOS 服务注册表。

    Args:
        path: YAML 文件路径。None 则使用环境变量 AGORA_BOS_REGISTRY 或默认路径。

    Returns:
        list[BosService]: 解析后的服务列表。

    Raises:
        FileNotFoundError: 指定路径不存在。
        yaml.YAMLError: YAML 格式错误。
    """
    if path is None:
        env_path = os.environ.get("AGORA_BOS_REGISTRY", "")
        path = pathlib.Path(env_path) if env_path else DEFAULT_REGISTRY_PATH
    else:
        path = pathlib.Path(path)

    if not path.exists():
        raise FileNotFoundError(f"BOS 注册表文件不存在: {path}")

    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    if not data or "services" not in data:
        raise ValueError(f"YAML 注册表缺少 'services' 根键: {path}")

    # ADR-0181 Phase 2: status=deprecated 默认不进入可路由表
    # P0-1: status=unimplemented 永远不进入可路由表（声明/执行鸿沟修复）
    # 注意: AGORA_BOS_INCLUDE_DEPRECATED=1 仅放行 deprecated (调试用),
    #       unimplemented 不受该 env 影响, 始终排除。
    include_deprecated = (
        os.environ.get("AGORA_BOS_INCLUDE_DEPRECATED", "0").strip() == "1"
    )
    if not include_deprecated:
        data["services"] = [
            s for s in data["services"] if s.get("status", "active") != "deprecated"
        ]
    # unimplemented 始终排除
    data["services"] = [
        s for s in data["services"] if s.get("status", "active") != "unimplemented"
    ]

    services = []
    for entry in data["services"]:
        svc = _dict_to_bos_service(entry)
        services.append(svc)

    return services


def registry_info(path: str | pathlib.Path | None = None) -> dict[str, Any]:
    """获取注册表统计信息。"""
    services = load_from_yaml(path)
    domains: dict[str, int] = {}
    transports: dict[str, int] = {}
    unimplemented: list[str] = []

    for s in services:
        domains[s.domain] = domains.get(s.domain, 0) + 1
        transports[s.transport] = transports.get(s.transport, 0) + 1
        if s.description.startswith("[UNIMPLEMENTED]"):
            unimplemented.append(s.uri)

    return {
        "total": len(services),
        "domains": domains,
        "transports": transports,
        "unimplemented": unimplemented,
        "unimplemented_count": len(unimplemented),
    }


def validate_registry(path: str | pathlib.Path | None = None) -> list[str]:
    """校验注册表的完整性，返回错误列表（空 = 全通过）。"""
    errors: list[str] = []
    try:
        services = load_from_yaml(path)
    except (FileNotFoundError, ValueError, yaml.YAMLError, KeyError) as e:
        return [f"加载失败: {e}"]

    # 动态推导合法值，避免硬编码漂移
    valid_domains = _get_valid_domains()
    valid_transports = _get_valid_transports()
    from agora.mcp.resolver.services import BOS_URI_PATTERN

    seen_uris: set[str] = set()

    for i, s in enumerate(services):
        if not s.uri:
            errors.append(f"[{i}] 缺少 uri")
            continue

        if s.uri in seen_uris:
            errors.append(f"[{i}] 重复 URI: {s.uri}")
            continue
        seen_uris.add(s.uri)

        # URI 格式校验
        if not BOS_URI_PATTERN.match(s.uri):
            errors.append(f"[{i}] URI 格式错误: {s.uri}")

        # domain 合法性
        if s.domain and valid_domains and s.domain not in valid_domains:
            errors.append(f"[{i}] 无效 domain: {s.domain} ({s.uri})")

        # transport 合法性
        if s.transport not in valid_transports:
            errors.append(f"[{i}] 无效 transport: {s.transport} ({s.uri})")

        # stdio 必须有 command
        if s.transport in ("stdio", "mcp_stdio") and not s.command:
            errors.append(f"[{i}] stdio 传输缺少 command: {s.uri}")

        # http 必须有 http_url
        if s.transport == "http" and not s.http_url:
            errors.append(f"[{i}] http 传输缺少 http_url: {s.uri}")

        # inline transport 是 self-identifier / i0_route:pending 占位,
        # 不需要 command / http_url; 它们只是 I0 文档锚点。

    if not errors:
        errors.append("✅ 注册表校验通过 — 0 错误")

    return errors
