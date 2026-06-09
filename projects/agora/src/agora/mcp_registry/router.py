"""Smart Router — LLM-powered tool selection and orchestration.

Three modes:
1. direct — User knows the exact tool name ("docker list containers")
2. recommend — User is unsure, system recommends tools ("I need database analysis")
3. auto — Full pipeline: discover → install → load → call
"""

import structlog

from agora.mcp_registry.embeddings import EmbeddingStore  # type: ignore[import-not-found]
from agora.mcp_registry.repository import ToolCatalog  # type: ignore[import-not-found]

logger = structlog.get_logger(__name__)


class SmartRouter:
    """Natural language → tool routing engine."""

    def __init__(
        self,
        catalog: ToolCatalog,
        embeddings: EmbeddingStore | None = None,
        lifecycle=None,
        orchestrator=None,
    ):
        self._catalog = catalog
        self._embeddings = embeddings
        self._lifecycle = lifecycle
        self._orchestrator = orchestrator
        self._llm = None  # Lazy init

    # ── LLM client (lazy) ────────────────────────────────────────────────

    def _init_llm(self):
        """Initialize LLM client from minerva package (optional dependency)."""
        if self._llm is not None:
            return self._llm if self._llm is not False else None
        try:
            from minerva.llm.client import OpenAICompatibleClient

            self._llm = OpenAICompatibleClient(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
                model="qwen3:30b-a3b",
                timeout=30,
            )
            logger.info("smart_router_llm_initialized", model="qwen3:30b-a3b")
        except ImportError:
            logger.info("smart_router_llm_unavailable", reason="minerva not available")
            self._llm = False
        except Exception as e:
            logger.warning("smart_router_llm_init_failed", error=str(e))
            self._llm = False
        return self._llm if self._llm is not False else None

    @property
    def llm_available(self) -> bool:
        """Check if LLM client is available."""
        return self._init_llm() is not None

    # ── Main routing ────────────────────────────────────────────────────

    async def route(self, query: str, mode: str = "auto") -> dict:
        """Route a natural language query to the appropriate tool.

        Modes:
        - 'direct': Expects "tool_name action params" format
        - 'recommend': Return tool recommendations ranked by relevance
        - 'auto': Try direct → recommend → auto-discover

        Returns dict with keys: mode, status, tool(s), action, message
        """
        query = query.strip()
        if not query:
            return {"status": "error", "error": "Empty query", "mode": mode}

        if mode == "direct":
            return await self._route_direct(query)
        elif mode == "recommend":
            return await self._route_recommend(query)
        else:  # auto
            # Phase 1: Try direct match
            result = await self._route_direct(query)
            if result.get("tool") is not None:
                result["mode"] = "auto(direct)"
                return result

            # Phase 2: Semantic search + recommend
            result = await self._route_recommend(query)
            tools = result.get("tools", [])
            has_tool = result.get("tool") is not None
            if (tools or has_tool) and result.get("action") != "no_match":
                result["mode"] = "auto(recommend)"
                return result

            # Phase 3: Auto-discover from external sources
            if self._orchestrator:
                return await self._route_auto_discover(query)
            return result

    async def _route_direct(self, query: str) -> dict:
        """Route using explicit tool name as first word of query."""
        parts = query.split(None, 2)
        tool_hint = parts[0].lower()

        # Search loaded tools first
        loaded = self._catalog.search_tools(tool_hint, status="loaded", limit=5)
        if loaded:
            tool = loaded[0]
            return {
                "status": "ok",
                "mode": "direct",
                "tool": tool,
                "action": "call",
                "message": f"Tool '{tool['name']}' is loaded and ready",
            }

        # Search all tools
        all_tools = self._catalog.search_tools(tool_hint, limit=5)
        if all_tools:
            tool = all_tools[0]
            load_needed = tool.get("status") not in ("loaded",)
            return {
                "status": "ok",
                "mode": "direct",
                "tool": tool,
                "action": "load_and_call" if load_needed else "call",
                "message": f"Tool '{tool['name']}' found (status: {tool.get('status', '?')})",
            }

        return {
            "status": "ok",
            "mode": "direct",
            "tool": None,
            "action": "no_match",
            "message": f"No tool matching '{tool_hint}'",
        }

    async def _route_recommend(self, query: str) -> dict:
        """Search by semantic similarity → rank by quality → return top matches."""
        candidates = self._semantic_search(query)
        if not candidates:
            # Fall back to keyword search
            candidates = self._catalog.search_tools(query, limit=20)

        if not candidates:
            return {
                "status": "ok",
                "mode": "recommend",
                "tools": [],
                "action": "no_match",
                "message": "No matching tools found",
            }

        # Use LLM to refine if available
        llm = self._init_llm()
        if llm and candidates:
            return await self._llm_select_tool(query, candidates)

        # Fallback: return top 5 by quality score
        top = candidates[:5]
        return {
            "status": "ok",
            "mode": "recommend",
            "tools": top,
            "action": "select",
            "message": f"Found {len(top)} matching tool(s). Use 'agora.execute --tool <name> <args>' to call.",
        }

    async def _route_auto_discover(self, query: str) -> dict:
        """Full auto-discover → install → load pipeline."""
        try:
            result = await self._orchestrator.discover_install_load(query)
            loaded_count = result.get("loaded", 0)
            if loaded_count > 0:
                return {
                    "status": "ok",
                    "mode": "auto_discover",
                    "discovered": result.get("discovered", 0),
                    "loaded": loaded_count,
                    "results": result.get("results", []),
                    "action": "load",
                    "message": f"Discovered {result.get('discovered', 0)} tool(s), loaded {loaded_count}",
                }
            return {
                "status": "ok",
                "mode": "auto_discover",
                "discovered": result.get("discovered", 0),
                "loaded": 0,
                "action": "no_match",
                "message": f"Discovered {result.get('discovered', 0)} tool(s) but none could be loaded",
            }
        except Exception as e:
            logger.exception("auto_discover_failed")
            return {
                "status": "error",
                "mode": "auto_discover",
                "error": f"Auto-discover failed: {e}",
            }

    # ── Semantic search ─────────────────────────────────────────────────

    def _semantic_search(self, query: str) -> list[dict]:
        """Search using embedding similarity if available, else keyword."""
        if self._embeddings and self._embeddings.available:
            similar = self._embeddings.search_similar(query, top_k=20)
            if similar:
                tools = []
                seen = set()
                for tool_id, score in similar:
                    if tool_id not in seen:
                        seen.add(tool_id)
                        t = self._catalog.get_tool(tool_id)
                        if t:
                            t["_similarity"] = round(score, 4)
                            tools.append(t)
                tools.sort(
                    key=lambda x: x.get("_similarity", 0) * x.get("quality_score", 0.5),
                    reverse=True,
                )
                return tools
        return []

    # ── LLM tool selection ──────────────────────────────────────────────

    async def _llm_select_tool(self, query: str, candidates: list[dict]) -> dict:
        """Use LLM to select the best tool from candidates."""
        prompt = self._build_selection_prompt(query, candidates)
        try:
            response = await self._llm.generate("", prompt, max_tokens=100)
            selected_name = response.strip().lower()
        except Exception as e:
            logger.warning("llm_select_failed", error=str(e))
            top = candidates[:5]
            return {
                "status": "ok",
                "mode": "llm_fallback",
                "tools": top,
                "action": "select",
                "message": "LLM error, fallback to quality sort",
            }

        # Match selected name to catalog
        for t in candidates:
            if t["name"].lower() == selected_name or selected_name in t["name"].lower():
                return {
                    "status": "ok",
                    "mode": "llm_selected",
                    "tool": t,
                    "action": "load_and_call"
                    if t.get("status") != "loaded"
                    else "call",
                    "message": f"LLM selected '{t['name']}' (quality: {t.get('quality_score', 0):.2f})",
                }

        # No exact match — return top candidates
        top = candidates[:5]
        return {
            "status": "ok",
            "mode": "llm_no_match",
            "tools": top,
            "action": "select",
            "message": f"LLM response '{selected_name}' didn't match any tool",
        }

    def _build_selection_prompt(self, query: str, candidates: list[dict]) -> str:
        """Build LLM prompt for tool selection."""
        prompt = f"""You are a tool selection assistant. Given a user request and a list of available MCP tools, select the BEST matching tool.

User request: "{query}"

Available tools:
"""
        for i, t in enumerate(candidates[:10], 1):
            tags = ", ".join(t.get("tags", [])[:5])
            desc = (t.get("description") or "No description")[:100]
            prompt += f"{i}. {t['name']} — {desc} [tags: {tags}] [quality: {t.get('quality_score', 0):.2f}]\n"

        prompt += "\nRespond with ONLY the tool name (exactly as listed above) that best matches the user's request. If none match, respond with 'none'."
        return prompt

    # ── Status ──────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return router status."""
        return {
            "mode": "smart_router",
            "llm_available": self.llm_available,
            "embeddings_available": self._embeddings.available
            if self._embeddings
            else False,
            "lifecycle_available": self._lifecycle is not None,
            "orchestrator_available": self._orchestrator is not None,
        }
