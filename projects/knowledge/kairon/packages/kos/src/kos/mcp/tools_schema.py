#!/usr/bin/env python3
# ruff: noqa
"""KOS MCP Tools Schema — 所有 MCP tool 的声明式 schema 定义.

从 mcp/server.py run_stdio 内联 TOOLS dict 抽出 (wave 6, server.py 1396->~1100).
tool 实现 (tool_*) 留 server.py, schema 定义集中此模块 (单一定义, 双引用: tools/list + tools/call).
"""

from __future__ import annotations

from typing import Any

# 核心 tool schema (server.py 原 TOOLS dict 主体)
TOOLS_SCHEMA: dict[str, dict[str, Any]] = {
    "search_knowledge": {
        "description": "Cross-domain full-text and metadata search across all KOS knowledge domains (gongwen, guozhuan, obsidian, family, wpsnote). Returns ranked results with snippets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "domains": {"type": "string", "description": "Comma-separated domain filter"},
                "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
                "match_mode": {
                    "type": "string",
                    "description": "AND (all terms) or OR (any term). Default: OR",
                    "default": "OR",
                },
            },
            "required": ["query"],
        },
    },
    "get_knowledge": {
        "description": "Get a specific knowledge object by KOS ID (format: domain::path or doc_id).",
        "inputSchema": {
            "type": "object",
            "properties": {"kos_id": {"type": "string", "description": "KOS ID or doc_id"}},
            "required": ["kos_id"],
        },
    },
    "get_system_status": {
        "description": "Get KOS system health overview: domain status, retrieval index stats, recent changes.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    "list_domains": {
        "description": "List all registered KOS knowledge domains.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    "cross_domain_sync": {
        "description": "Trigger a cross-domain state synchronization.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domains": {"type": "string", "description": "Comma-separated domains to sync (default: all)"}
            },
            "required": [],
        },
    },
    "get_entity": {
        "description": "Get entity details by ID (P:name, O:name, J:name, C:name). Returns entity card with relations.",
        "inputSchema": {
            "type": "object",
            "properties": {"entity_id": {"type": "string", "description": "Entity ID (e.g. P:xia-mingxing)"}},
            "required": ["entity_id"],
        },
    },
    "search_entity": {
        "description": "Search entities by name, type, or description.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Entity name or keyword"},
                "entity_type": {"type": "string", "description": "Filter: Person, Organization, Project"},
                "limit": {"type": "integer", "description": "Max results", "default": 10},
            },
            "required": ["query"],
        },
    },
    "ontology_rebuild": {
        "description": "Rebuild entity index: clear + extract + enrich. One-command full ontology refresh. L2 operation — requires confirmed=true.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "confirmed": {
                    "type": "boolean",
                    "description": "Explicit confirmation for L2 destructive operation.",
                    "default": False,
                }
            },
            "required": [],
        },
    },
    "ontology_graph": {
        "description": "Generate Mermaid entity relationship graph. Optionally filter by entity type.",
        "inputSchema": {
            "type": "object",
            "properties": {"entity_type": {"type": "string", "description": "Filter: Person, Organization, Project"}},
            "required": [],
        },
    },
    "run_indexer": {
        "description": "Run kos-indexer.py on the host side (bypasses sandbox SQLite restriction). Supports incremental (default) or full rebuild, optional domain filter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "incremental": {"type": "boolean", "description": "Incremental mode (default: true)", "default": True},
                "domain": {
                    "type": "string",
                    "description": "Single domain filter (e.g. gongwen, guozhuan)",
                    "default": "",
                },
                "background": {"type": "boolean", "description": "Run in background (default: true).", "default": True},
                "confirmed": {
                    "type": "boolean",
                    "description": "Confirm L2 full rebuild. Required when incremental=false.",
                    "default": False,
                },
            },
            "required": [],
        },
    },
    "full_sync": {
        "description": "Run indexer + ontology rebuild end-to-end on the host side. One-command full KOS refresh that bypasses sandbox SQLite restrictions. L2 operation — requires confirmed=true.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "background": {"type": "boolean", "description": "Run in background (default: true).", "default": True},
                "confirmed": {"type": "boolean", "description": "Explicit confirmation for L2.", "default": False},
            },
            "required": [],
        },
    },
    "db_vacuum": {
        "description": "VACUUM the retrieval database. Irreversible space reclamation — L3 operation requires confirmed=true AND cool_down_hours>=24.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "confirmed": {"type": "boolean", "description": "Explicit confirmation for L3.", "default": False},
                "cool_down_hours": {
                    "type": "integer",
                    "description": "Cool-down hours. Must be >= 24 for L3.",
                    "default": 0,
                },
            },
            "required": [],
        },
    },
    "research_now": {
        "description": "Execute deep research via Minerva (8 search engines + 4 LLMs). Returns structured report with citations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Research question"},
                "level": {
                    "type": "string",
                    "description": "Pipeline level: auto|L0|L1|L2|L3|L4 (default: auto)",
                    "default": "auto",
                },
                "max_cost": {"type": "number", "description": "Maximum cost in USD (default: 1.0)", "default": 1.0},
            },
            "required": ["query"],
        },
    },
    "semantic_search": {
        "description": "Search via Minerva LanceDB vector similarity for semantic understanding. Falls back to KOS FTS5 if Minerva unavailable.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"},
                "limit": {"type": "integer", "description": "Max results (default: 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    "semantic_scholar": {
        "name": "semantic_scholar",
        "description": "Search Semantic Scholar academic papers by keyword. Returns title, authors, year, citations, abstract.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results (1-20)", "default": 5},
            },
            "required": ["query"],
        },
    },
    "build_context": {
        "description": "Build LLM-ready context from knowledge base with budget control. Returns formatted prompt with relevant knowledge.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query to build context for"},
                "mode": {
                    "type": "string",
                    "description": "Context mode: concise|balanced|detailed (default: balanced)",
                    "default": "balanced",
                },
                "persona": {"type": "string", "description": "Persona/role for context"},
                "max_tokens": {"type": "integer", "description": "Max token budget (default: 0=auto)", "default": 0},
            },
            "required": ["query"],
        },
    },
    "verify_claim": {
        "description": "Verify a claim against the knowledge base. Returns supporting/contradicting evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {"claim": {"type": "string", "description": "Claim to verify"}},
            "required": ["claim"],
        },
    },
    "memory_stats": {
        "description": "Get memory tier statistics (session queries, search history, popular queries).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    "research_pipeline": {
        "description": "Full research pipeline: KOS hybrid search → context engineering → Minerva deep research → fact verification. Returns structured report.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Research question"},
                "level": {
                    "type": "string",
                    "description": "Minerva level: auto|L0|L1|L2|L3|L4 (default: auto)",
                    "default": "auto",
                },
                "max_cost": {"type": "number", "description": "Max cost in USD (default: 1.0)", "default": 1.0},
            },
            "required": ["question"],
        },
    },
    "fact_check": {
        "description": "Verify a factual claim against KOS knowledge base. Returns evidence and verdict.",
        "inputSchema": {
            "type": "object",
            "properties": {"claim": {"type": "string", "description": "Factual claim to verify"}},
            "required": ["claim"],
        },
    },
    "sync_gbrain": {
        "description": "Sync KOS documents with gbrain memory graph. Direction: export|import|both.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "description": "Sync direction: export|import|both (default: both)",
                    "default": "both",
                },
                "limit": {"type": "integer", "description": "Max items to sync (default: 100)", "default": 100},
            },
            "required": [],
        },
    },
    "graph_search": {
        "description": "Multi-hop knowledge graph search with reasoning. Finds entities connected by relationships.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_hops": {"type": "integer", "description": "Max hops (default: 3)", "default": 3},
                "limit": {"type": "integer", "description": "Max results (default: 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    "entity_explore": {
        "description": "Explore an entity: show its relations, related documents, and connected entities.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Entity ID (e.g. P:xia-mingxing)"},
                "depth": {"type": "integer", "description": "Exploration depth (default: 2)", "default": 2},
            },
            "required": ["entity_id"],
        },
    },
    "knowledge_ask": {
        "description": "Ask a question about your knowledge base. Uses GraphRAG to find reasoning paths and evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Question to answer"},
                "include_paths": {
                    "type": "boolean",
                    "description": "Include reasoning paths (default: true)",
                    "default": True,
                },
            },
            "required": ["question"],
        },
    },
    "mcp_market_discover": {
        "description": "G3: Discover external MCP tool market. Scans local MCP client configs (Claude/Cursor/Windsurf/VSCode) + agora registered MCP backends + known MCP server registries. Returns aggregated discovery report for tool ecosystem awareness.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Filter by source: local / agora. Omit for all sources.",
                },
            },
            "required": [],
        },
    },
    "viz_render": {
        "description": "G4: Render unified Mermaid visualization by type. Aggregates kos graph (ontology relationships) + eidos viz (class/state/pipeline/memory) into a single entry. Bridges the previously fragmented viz surfaces.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "viz_type": {
                    "type": "string",
                    "description": "ontology / class / state / pipeline / memory / all. Default: ontology",
                    "default": "ontology",
                },
                "entity_type": {
                    "type": "string",
                    "description": "Entity type filter (ontology viz only)",
                },
            },
            "required": [],
        },
    },
}


def get_all_tools(extra: dict[str, dict] | None = None) -> dict[str, dict]:
    """获取完整 TOOLS dict (核心 schema + 可选扩展: SELF/COLLAB/CONSENSUS)."""
    tools = dict(TOOLS_SCHEMA)
    if extra:
        for e in extra.values():
            if isinstance(e, dict):
                tools.update(e)
    return tools
