"""BOS 自动注册 — 从 M1 Workflow 节点发现 (P46 W1)
===================================================
启动时从 L0 MOF M1 Workflow 节点 YAML 文件中提取 action，
自动注册到 BOSRouter。

用法 (在 _init_proxy 中):
    from agora.mcp.bos_auto_register import auto_register_from_m1
    auto_register_from_m1()
"""

from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger(__name__)


def auto_register_from_m1(bos_router=None) -> int:
    """从 M1 Workflow 节点 YAML 自动注册 BOS 路由。

    扫描 m1/workflow/ 下的 WORKFLOW-*.yaml，提取:
    - bos_uri → 作为路由前缀
    - cross_layer.realized_by → adapter 类型和配置
    - steps[].action → 子路由

    返回注册数量。
    """
    import yaml
    from agora.mcp.bos_router import bos_router as _br

    router = bos_router or _br
    wf_dir = Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "workflow"

    if not wf_dir.exists():
        _log.warning("M1 Workflow 目录不存在: %s", wf_dir)
        return 0

    registered = 0
    for f in sorted(wf_dir.glob("WORKFLOW-*.yaml")):
        try:
            node = yaml.safe_load(open(f))
            if not node or node.get("type") != "Workflow":
                continue

            bos_uri = node.get("bos_uri", "")
            if not bos_uri or not bos_uri.startswith("bos://"):
                continue

            # 提取实现方信息
            realized = node.get("cross_layer", {}).get("realized_by", [{}])[0]
            project = realized.get("project", "unknown")
            pkg = realized.get("package", "")

            # 决定 adapter 类型
            adapter = "poc"  # 默认 POC
            domain = node.get("domain", "")

            # 注册主路由
            router.register(bos_uri, adapter=adapter, config={
                "domain": domain,
                "project": project,
                "package": pkg,
                "workflow": node.get("name", ""),
                "steps": len(node.get("steps", [])),
                "entrypoint": realized.get("entrypoint", ""),
            })
            registered += 1

        except Exception:
            pass

    _log.info("auto_register_from_m1: registered %d workflows", registered)
    return registered
