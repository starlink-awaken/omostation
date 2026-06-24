#!/usr/bin/env python3
"""BOS URI 解析核心逻辑 — P33 Campaign 2.

BOS URI naming convention: ``bos://<domain>/<package>/<action>``
- ``domain``   : one of 5 fixed (memory, governance, analysis, persona, capability)
- ``package``  : kebab-case, matches the kairon package directory
- ``action``   : verb (search/ingest/audit/register/trigger/gate/...)

Legacy 3-segment form: ``bos://<package>/<action>`` (no explicit domain).
Used by mcp_server.py (``bos://omo/debt`` etc., P30 era). Accepted via
``BOS_URI_LEGACY_PATTERN``; domain is auto-mapped from ``LEGACY_DOMAIN_MAP``
(default: ``omo`` → ``governance``). New code SHOULD use the 4-segment form.

God Module 拆分 (2026-06): 本模块从 ``omo_bos.py`` 提取 — BOS URI 核心定义 + 解析.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# ── 路径配置 (P33-W3 暴露给外部) ──────────────────────
# kairon packages 根目录 — kairon 23 个包, 包含 kos 实体存储
_KAIRON_PACKAGES_SRC = (
    Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace")))
    / "projects"
    / "kairon"
    / "packages"
    / "kos"
    / "src"
)

# ── BOS URI 命名空间 ────────────────────────────────────────
# 5 个 domain 固定不可扩展 (北星 ADR-0007 约束)
ALLOWED_DOMAINS: tuple[str, ...] = (
    "memory",
    "governance",
    "analysis",
    "persona",
    "capability",
)

# 严格 BOS URI 模式 — kebab-case + 三段固定
# package/action: 必须以小写字母开头, 中间可含小写/数字/连字符, 末尾不能是连字符
# 拒绝: "Kos-", "-kos", "kos-", "KO", 等
_KOS_PART = r"[a-z]([a-z0-9-]*[a-z0-9])?"
BOS_URI_PATTERN = re.compile(
    r"^bos://(?P<domain>memory|governance|analysis|persona|capability)"
    r"/(?P<package>" + _KOS_PART + r")"
    r"/(?P<action>" + _KOS_PART + r")$"
)

# 3-段 legacy URI (P30 时代 mcp_server.py 既有: bos://omo/debt 等)
# 接受 bos://<package>/<action> 形式, domain 通过 LEGACY_DOMAIN_MAP 推断
BOS_URI_LEGACY_PATTERN = re.compile(
    r"^bos://(?P<package>" + _KOS_PART + r")/(?P<action>" + _KOS_PART + r")$"
)

# legacy 3-段 → 4-段 domain 隐含映射
# 多数 mcp_server.py 的 3-段 URI 属于 governance (omo, alerts, debt 等)
LEGACY_DOMAIN_MAP: dict[str, str] = {
    "omo": "governance",
    "debt": "governance",
    "alerts": "governance",
    "tasks": "governance",
    "standards": "governance",
}

Domain = Literal["memory", "governance", "analysis", "persona", "capability"]
Protocol = Literal["http", "stdio", "internal"]

# ── 持久化路径 ────────────────────────────────────────────
# P33-W1: 战役 2 起步故意走本地 JSON (避开 KOS 写入复杂)
DEFAULT_REGISTRY_PATH = (
    Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace")))
    / ".omo"
    / "_knowledge"
    / "bos-registry.json"
)


# ── 数据类 ───────────────────────────────────────────────


@dataclass
class BosRegistration:
    """BOS URI 注册记录."""

    uri: str
    domain: str
    package: str
    action: str
    endpoint: str
    protocol: Protocol = "internal"
    description: str = ""
    registered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    registered_by: str = "omo-bos-cli"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── 验证 + 解析 ────────────────────────────────────────────


def validate_bos_uri(uri: str) -> tuple[bool, str]:
    """Validate BOS URI format (4-segment new + 3-segment legacy).

    Accepted forms:
      1. ``bos://<domain>/<package>/<action>`` (new, P33 北星)
         domain ∈ {memory, governance, analysis, persona, capability}
      2. ``bos://<package>/<action>`` (legacy, P30 mcp_server.py)
         domain auto-mapped via LEGACY_DOMAIN_MAP

    Returns:
        (True, "") on valid 4-segment; (True, info_msg) on valid legacy
        (info_msg contains the auto-mapped domain); (False, error_message)
        on invalid.
    """
    if not isinstance(uri, str):
        return False, f"URI must be string, got {type(uri).__name__}"
    # 1) 4-段新格式 (北星, 北斗主用)
    m = BOS_URI_PATTERN.match(uri)
    if m:
        return True, ""
    # 2) 3-段 legacy 格式 (mcp_server.py P30 既有 URI)
    lm = BOS_URI_LEGACY_PATTERN.match(uri)
    if lm:
        pkg = lm.group("package")
        if pkg in LEGACY_DOMAIN_MAP:
            return (
                True,
                f"legacy 3-segment URI, auto-mapped to domain={LEGACY_DOMAIN_MAP[pkg]}",
            )
        return (
            False,
            f"Legacy 3-segment URI but package '{pkg}' not in domain map. "
            f"Use 4-segment form: bos://<domain>/<package>/<action>",
        )
    return (
        False,
        f"Invalid BOS URI: {uri!r}. "
        f"Expected bos://<domain>/<package>/<action> "
        f"(domain in {ALLOWED_DOMAINS}) or legacy bos://<package>/<action>",
    )


def parse_bos_uri(uri: str) -> dict[str, str]:
    """Parse BOS URI into dict (handles both 4-segment and 3-segment legacy).

    For legacy 3-segment URIs, the domain is filled from
    ``LEGACY_DOMAIN_MAP``.  Raises ``ValueError`` if the URI is invalid
    or the legacy package has no domain mapping.
    """
    valid, err = validate_bos_uri(uri)
    if not valid:
        raise ValueError(err)
    m4 = BOS_URI_PATTERN.match(uri)
    if m4:
        return m4.groupdict()
    m3 = BOS_URI_LEGACY_PATTERN.match(uri)
    assert m3 is not None  # validate_bos_uri just confirmed
    pkg = m3.group("package")
    return {
        "domain": LEGACY_DOMAIN_MAP[pkg],
        "package": pkg,
        "action": m3.group("action"),
    }


__all__ = (
    "ALLOWED_DOMAINS",
    "BOS_URI_LEGACY_PATTERN",
    "BOS_URI_PATTERN",
    "BosRegistration",
    "DEFAULT_REGISTRY_PATH",
    "Domain",
    "LEGACY_DOMAIN_MAP",
    "Protocol",
    "parse_bos_uri",
    "validate_bos_uri",
)
