"""agora.mcp.resolver.services_internal — internal transport 拆分 (P111).

TASK-F7114ABA 治本: services.py 1352L 按 transport 类型分文件.
5 个 internal service (transport="internal") 拆到本模块, services.py
降至 <1300L (继续 P111 第二步: stdio + mcp_stdio).

业务 (5 entries): 同进程 importlib 调用的服务, 不启动子进程:
- bos://memory/local/all-search — P2 多区聚合搜索
- bos://governance/omo/audit — OMO 治理审计
- bos://governance/omo/inspect — OMO 系统检查
- bos://meta/discover — 发现所有可用 BOS 资源
- bos://memory/vault/search — L4 Vault 知识库搜索

模式: 顶层 re-export (PFC) 保持 `from .services import _INTERNAL_SERVICES` 不破.
调用方 `from agora.mcp.resolver.services import _INTERNAL_SERVICES` 等.
"""

from __future__ import annotations

from .services import BosService

__all__ = ["_INTERNAL_SERVICES"]


# ── Internal transport 服务 (同进程 importlib, 无子进程)
# 模式: module_path + func_name 触发 importlib + getattr 调用.
_INTERNAL_SERVICES: list[BosService] = [
    BosService(
        uri="bos://memory/local/all-search",
        domain="memory",
        package="memory",
        action="all-search",
        transport="internal",
        module_path="agora.mcp.bos_resolver",
        func_name="_memory_all_search",
        description="P2 多区聚合搜索 — cockpit local + KOS + vault",
    ),
    BosService(
        uri="bos://governance/omo/audit",
        domain="governance",
        package="omo",
        action="audit",
        transport="internal",
        module_path="omo.omo_audit",
        func_name="run_governance_audit",
        description="OMO 治理审计 (internal — 同进程 importlib)",
    ),
    BosService(
        uri="bos://governance/omo/inspect",
        domain="governance",
        package="omo",
        action="inspect",
        transport="internal",
        module_path="omo.omo_inspect",
        func_name="run_full_inspection",
        description="OMO 系统检查 (internal 同进程)",
    ),
    BosService(
        uri="bos://meta/discover",
        domain="meta",
        package="meta",
        action="discover",
        transport="internal",
        module_path="agora.mcp.bos_resolver",
        func_name="_meta_discover",
        description="发现所有可用 BOS 资源和入口",
    ),
    BosService(
        uri="bos://memory/vault/search",
        domain="memory",
        package="memory",
        action="vault-search",
        transport="internal",
        module_path="agora.mcp.bos_resolver",
        func_name="_memory_vault_search",
        description="L4 Vault 知识库搜索",
    ),
    BosService(
        uri="bos://persona/bdsk/evaluate",
        domain="persona",
        package="agora",
        action="evaluate",
        transport="internal",
        module_path="agora.server.tools_bos",
        func_name="persona_bdsk_evaluate",
        description="B.D.S.K. 虚拟董事会并发对抗与结构化方案评审网关 (Persona Evaluate)",
    ),
]
