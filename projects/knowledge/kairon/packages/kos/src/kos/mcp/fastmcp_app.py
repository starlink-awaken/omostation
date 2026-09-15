#!/usr/bin/env python3
"""kos FastMCP app — 42 工具 @app.tool 注册 (协议统一, 替代 run_stdio 手写 stdio).

2026-07-13 kos MCP 迁移 (mcp-unification-plan.md 模式 B): 从头建 FastMCP app,
注册本体 27 tool_ 函数 + 命名空间 15 (self/collab/consensus HANDLERS).
参数映射源自 server.py run_stdio 的 dispatch lambda (a.get → def 参数默认值).
main 走 _create_fastmcp_app().run() (FastMCP stdio), run_stdio 保留兼容/测试.
"""

from __future__ import annotations

from typing import Any


def _create_fastmcp_app() -> Any:
    """构建 kos FastMCP app (42 工具注册). 返回 FastMCP app, main 调 app.run()."""
    try:
        from fastmcp import FastMCP
    except ImportError:
        return None

    # 本体 tool_ 函数 + 命名空间 HANDLERS (延迟 import 解循环 / 减启动开销)
    from kos.collab.mcp import COLLAB_HANDLERS
    from kos.consensus.mcp import CONSENSUS_HANDLERS
    from kos.mcp.server import (
        tool_build_context,
        tool_check_subscription,
        tool_db_vacuum,
        tool_entity_explore,
        tool_fact_check,
        tool_full_sync,
        tool_get_entity,
        tool_get_entity_timeline,
        tool_get_knowledge,
        tool_get_stats,
        tool_get_system_status,
        tool_graph_search,
        tool_knowledge_ask,
        tool_list_domains,
        tool_mcp_market_discover,
        tool_memory_stats,
        tool_onto,
        tool_research_now,
        tool_research_pipeline,
        tool_run_indexer,
        tool_search_entity,
        tool_search_knowledge,
        tool_semantic_scholar,
        tool_semantic_search,
        tool_subscribe_topic,
        tool_sync_gbrain,
        tool_verify_claim,
        tool_viz_render,
    )
    from kos.mcp.tools_schema import TOOLS_SCHEMA
    from kos.self.mcp import SELF_HANDLERS

    def _desc(name: str) -> str:
        return str(TOOLS_SCHEMA.get(name, {}).get("description", name))

    app = FastMCP("kos-mcp")

    # ── 本体 27 tool ──────────────────────────────────────
    @app.tool(name="search_knowledge", description=_desc("search_knowledge"))
    def _search_knowledge(query: str, domains: str = "", limit: int = 10, match_mode: str = "OR") -> dict:
        return tool_search_knowledge(query, domains, limit, match_mode)

    @app.tool(name="get_knowledge", description=_desc("get_knowledge"))
    def _get_knowledge(kos_id: str) -> dict:
        return tool_get_knowledge(kos_id)

    @app.tool(name="get_system_status", description=_desc("get_system_status"))
    def _get_system_status() -> dict:
        return tool_get_system_status()

    @app.tool(name="list_domains", description=_desc("list_domains"))
    def _list_domains() -> dict:
        return tool_list_domains()

    @app.tool(name="cross_domain_sync", description=_desc("cross_domain_sync"))
    def _cross_domain_sync() -> dict:
        return tool_run_indexer(incremental=True, background=True)

    @app.tool(name="get_entity", description=_desc("get_entity"))
    def _get_entity(entity_id: str) -> dict:
        return tool_get_entity(entity_id)

    @app.tool(name="search_entity", description=_desc("search_entity"))
    def _search_entity(query: str, entity_type: str = "", limit: int = 10) -> dict:
        return tool_search_entity(query, entity_type, limit)

    @app.tool(name="ontology_rebuild", description=_desc("ontology_rebuild"))
    def _ontology_rebuild(confirmed: bool = False) -> dict:
        return tool_onto("rebuild", confirmed=confirmed)

    @app.tool(name="ontology_graph", description=_desc("ontology_graph"))
    def _ontology_graph(entity_type: str = "") -> dict:
        return tool_onto("graph", entity_type)

    @app.tool(name="run_indexer", description=_desc("run_indexer"))
    def _run_indexer(
        incremental: bool = True, domain: str = "", background: bool = True, confirmed: bool = False
    ) -> dict:
        return tool_run_indexer(incremental, domain, background, confirmed)

    @app.tool(name="full_sync", description=_desc("full_sync"))
    def _full_sync(background: bool = True, confirmed: bool = False) -> dict:
        return tool_full_sync(background, confirmed)

    @app.tool(name="db_vacuum", description=_desc("db_vacuum"))
    def _db_vacuum(confirmed: bool = False, cool_down_hours: int = 0) -> dict:
        return tool_db_vacuum(confirmed, cool_down_hours)

    @app.tool(name="research_now", description=_desc("research_now"))
    def _research_now(query: str, level: str = "auto", max_cost: float = 1.0) -> dict:
        return tool_research_now(query, level, max_cost)

    @app.tool(name="semantic_search", description=_desc("semantic_search"))
    def _semantic_search(query: str, limit: int = 10) -> dict:
        return tool_semantic_search(query, limit)

    @app.tool(name="semantic_scholar", description=_desc("semantic_scholar"))
    def _semantic_scholar(query: str, limit: int = 5) -> dict:
        return tool_semantic_scholar(query, limit)

    @app.tool(name="build_context", description=_desc("build_context"))
    def _build_context(query: str, mode: str = "balanced", persona: str = "", max_tokens: int = 0) -> dict:
        return tool_build_context(query, mode, persona, max_tokens)

    @app.tool(name="verify_claim", description=_desc("verify_claim"))
    def _verify_claim(claim: str) -> dict:
        return tool_verify_claim(claim)

    @app.tool(name="memory_stats", description=_desc("memory_stats"))
    def _memory_stats() -> dict:
        return tool_memory_stats()

    @app.tool(name="get_stats", description=_desc("get_stats"))
    def _get_stats() -> dict:
        return tool_get_stats()

    @app.tool(name="subscribe_topic", description=_desc("subscribe_topic"))
    def _subscribe_topic(topic: str, subscriber_id: str = "mcp-agent") -> dict:
        return tool_subscribe_topic(topic, subscriber_id)

    @app.tool(name="check_subscription", description=_desc("check_subscription"))
    def _check_subscription(sub_id: str) -> dict:
        return tool_check_subscription(sub_id)

    @app.tool(name="get_entity_timeline", description=_desc("get_entity_timeline"))
    def _get_entity_timeline(entity_id: str) -> dict:
        return tool_get_entity_timeline(entity_id)

    @app.tool(name="research_pipeline", description=_desc("research_pipeline"))
    def _research_pipeline(question: str, level: str = "auto", max_cost: float = 1.0) -> dict:
        return tool_research_pipeline(question, level, max_cost)

    @app.tool(name="fact_check", description=_desc("fact_check"))
    def _fact_check(claim: str) -> dict:
        return tool_fact_check(claim)

    @app.tool(name="sync_gbrain", description=_desc("sync_gbrain"))
    def _sync_gbrain(direction: str = "both", limit: int = 100) -> dict:
        return tool_sync_gbrain(direction, limit)

    @app.tool(name="graph_search", description=_desc("graph_search"))
    def _graph_search(query: str, max_hops: int = 3, limit: int = 10) -> dict:
        return tool_graph_search(query, max_hops, limit)

    @app.tool(name="entity_explore", description=_desc("entity_explore"))
    def _entity_explore(entity_id: str, depth: int = 2) -> dict:
        return tool_entity_explore(entity_id, depth)

    @app.tool(name="knowledge_ask", description=_desc("knowledge_ask"))
    def _knowledge_ask(question: str, include_paths: bool = True) -> dict:
        return tool_knowledge_ask(question, include_paths)

    @app.tool(name="mcp_market_discover", description=_desc("mcp_market_discover"))
    def _mcp_market_discover(source: str | None = None) -> dict:
        return tool_mcp_market_discover(source)

    @app.tool(name="viz_render", description=_desc("viz_render"))
    def _viz_render(viz_type: str = "ontology", entity_type: str | None = None) -> dict:
        return tool_viz_render(viz_type, entity_type)

    # ── 命名空间 14 tool (self.*/collab.*/consensus.*) ─────────
    # HANDLERS 已封装, @app.tool 委托. FastMCP 不支持 **kwargs, 用 arguments: dict 参数.
    @app.tool(name="self.get_profile")
    def _self_get_profile() -> dict:
        return SELF_HANDLERS["self.get_profile"]()

    @app.tool(name="self.get_current_role")
    def _self_get_current_role(arguments: dict[str, Any] | None = None) -> dict:
        return SELF_HANDLERS["self.get_current_role"](arguments or {})

    @app.tool(name="self.get_vision_summary")
    def _self_get_vision_summary() -> dict:
        return SELF_HANDLERS["self.get_vision_summary"]()

    @app.tool(name="collab.create_task")
    def _collab_create_task(arguments: dict[str, Any] | None = None) -> dict:
        return COLLAB_HANDLERS["collab.create_task"](arguments or {})

    @app.tool(name="collab.get_task")
    def _collab_get_task(arguments: dict[str, Any] | None = None) -> dict:
        return COLLAB_HANDLERS["collab.get_task"](arguments or {})

    @app.tool(name="collab.list_tasks")
    def _collab_list_tasks(arguments: dict[str, Any] | None = None) -> dict:
        return COLLAB_HANDLERS["collab.list_tasks"](arguments or {})

    @app.tool(name="collab.update_task")
    def _collab_update_task(arguments: dict[str, Any] | None = None) -> dict:
        return COLLAB_HANDLERS["collab.update_task"](arguments or {})

    @app.tool(name="collab.claim_subtask")
    def _collab_claim_subtask(arguments: dict[str, Any] | None = None) -> dict:
        return COLLAB_HANDLERS["collab.claim_subtask"](arguments or {})

    @app.tool(name="collab.add_artifact")
    def _collab_add_artifact(arguments: dict[str, Any] | None = None) -> dict:
        return COLLAB_HANDLERS["collab.add_artifact"](arguments or {})

    @app.tool(name="consensus.create")
    def _consensus_create(arguments: dict[str, Any] | None = None) -> dict:
        return CONSENSUS_HANDLERS["consensus.create"](arguments or {})

    @app.tool(name="consensus.get")
    def _consensus_get(arguments: dict[str, Any] | None = None) -> dict:
        return CONSENSUS_HANDLERS["consensus.get"](arguments or {})

    @app.tool(name="consensus.list_expired")
    def _consensus_list_expired(arguments: dict[str, Any] | None = None) -> dict:
        return CONSENSUS_HANDLERS["consensus.list_expired"](arguments or {})

    @app.tool(name="consensus.renew")
    def _consensus_renew(arguments: dict[str, Any] | None = None) -> dict:
        return CONSENSUS_HANDLERS["consensus.renew"](arguments or {})

    @app.tool(name="consensus.trace")
    def _consensus_trace(arguments: dict[str, Any] | None = None) -> dict:
        return CONSENSUS_HANDLERS["consensus.trace"](arguments or {})

    return app
