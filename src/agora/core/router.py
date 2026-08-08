"""Request Router — routes incoming calls to the correct service.

Phase 3: Load balancing — supports multiple instances per service
with round-robin routing strategy.
"""

from __future__ import annotations

import atexit
import html
import json
import json as _json
import os
import re
import time as _time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from pathlib import Path as _Path

import structlog

from agora import persistence_db as _persist  # type: ignore[import-not-found]
from agora._protocols import close_client  # type: ignore[import-not-found]
from agora._protocols import dispatch as _dispatch
from agora.auth.identity import (  # type: ignore[import-not-found]
    Identity,
    normalize_identity,
)
from agora.core.event_bus import EventBus  # type: ignore[import-not-found]
from agora.core.registry import ServiceRegistry  # type: ignore[import-not-found]
from agora.core.service_cache import (  # type: ignore[import-not-found]
    load_service_cache as _load_service_cache,
)
from agora.core.service_cache import (
    save_service_cache as _save_service_cache,
)
from agora.mcp.mcp_bootstrap import get_data_dir  # type: ignore[import-not-found]

logger = structlog.get_logger(__name__)

# atexit 去重：跟踪所有 Router 实例，确保只注册一次
_routers: list[Router] = []
_atexit_registered = False


@dataclass
class _CompressedResult:
    content: str
    original_len: int
    compressed_len: int
    ratio: float
    stats: dict = field(default_factory=dict)

    @property
    def saved(self) -> int:
        return self.original_len - self.compressed_len


_DEFAULT_JSON_KEY_MAP = {
    "description": "desc",
    "identifier": "id",
    "metadata": "meta",
    "configuration": "config",
    "properties": "props",
    "attributes": "attrs",
    "parameters": "params",
    "arguments": "args",
    "message": "msg",
    "content": "val",
    "value": "val",
    "status": "st",
    "context": "ctx",
    "response": "resp",
    "request": "req",
    "handler": "hnd",
    "service": "svc",
    "definition": "defn",
    "reference": "ref",
    "category": "cat",
    "priority": "pri",
    "severity": "sev",
    "timestamp": "ts",
    "duration": "dur",
    "endpoint": "ep",
    "protocol": "proto",
    "version": "ver",
    "pattern": "ptn",
    "template": "tpl",
    "resource": "rsrc",
    "component": "comp",
    "extension": "ext",
}


class _Compressor:
    """Compress content based on detected or explicit content type."""

    def __init__(self, json_key_map: dict[str, str] | None = None):
        self._key_map = json_key_map or dict(_DEFAULT_JSON_KEY_MAP)
        self._reverse_map: dict[str, str] = {}
        self._url_refs: dict[str, str] = {}
        self._url_counter = 0
        self._dedup_seen: set[int] = set()

    def compress(self, content: str, content_type: str = "auto") -> _CompressedResult:
        original_len = len(content)
        if not content.strip():
            return _CompressedResult(content, original_len, 0, 0.0)
        ctype = self.detect_type(content) if content_type == "auto" else content_type
        stats: dict = {"type": ctype}
        if ctype == "json":
            compressed = self._compress_json(content, stats)
        elif ctype == "html":
            compressed = self._compress_html(content, stats)
        elif ctype == "error":
            compressed = self._compress_stacktrace(content, stats)
        elif ctype in ("code", "plaintext"):
            compressed = self._compress_plaintext(content, ctype, stats)
        else:
            compressed = content
        compressed_len = len(compressed)
        ratio = 1.0 - (compressed_len / original_len) if original_len else 0.0
        self._record_stats(ctype, original_len, compressed_len)
        return _CompressedResult(
            content=compressed,
            original_len=original_len,
            compressed_len=compressed_len,
            ratio=ratio,
            stats=stats,
        )

    def detect_type(self, content: str) -> str:
        if not content or not content.strip():
            return "plaintext"
        stripped = content.strip()
        if stripped[0] in ("{", "["):
            try:
                json.loads(stripped)
                return "json"
            except (json.JSONDecodeError, ValueError):
                pass
        if re.search(
            r"<\s*(html|div|span|p|body|head|table|article|section)",
            stripped[:500],
            re.IGNORECASE,
        ):
            return "html"
        if re.search(
            r"Traceback\s*\(|Error|Exception|at\s+\S+\.\w+\(.*\)", stripped[:600]
        ):
            return "error"
        code_patterns = [
            r"(?:^|\n)\s*(?:def|class|function|import|from|var|let|const|fn|pub|impl)\s",
            r"(?:^|\n)\s*(?:#|//|--|%)\s",
            r"(?:^|\n)\s*{",
            r"(?:^|\n)\s*(?:if|for|while|switch|match)\s+",
        ]
        score = sum(
            1 for pat in code_patterns if re.search(pat, stripped, re.MULTILINE)
        )
        return "code" if score >= 2 else "plaintext"

    def _compress_json(self, content: str, stats: dict) -> str:
        parsed = json.loads(content)
        self._reverse_map.clear()
        compressed = self._walk_and_shorten(parsed)
        stats["key_shorten_count"] = len(self._reverse_map)
        stats["reverse_map"] = dict(self._reverse_map)
        return json.dumps(compressed, ensure_ascii=False, separators=(",", ":"))

    def _walk_and_shorten(self, node):
        if isinstance(node, dict):
            new = {}
            for k, v in node.items():
                short = self._key_map.get(k, k)
                if short != k:
                    self._reverse_map[short] = k  # type: ignore[reportArgumentType]
                new[short] = self._walk_and_shorten(v)
            return new
        if isinstance(node, list):
            return [self._walk_and_shorten(item) for item in node]
        return node

    def _compress_html(self, content: str, stats: dict) -> str:
        original = content
        content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
        content = re.sub(
            r"</?(?:br|p|div|li|tr|h[1-6]|section|article|blockquote)[^>]*>",
            "\n",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(r"<[^>]+>", "", content)
        content = html.unescape(content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = content.strip()
        stats["tags_removed"] = len(re.findall(r"<[^>]+>", original))
        stats["lines"] = content.count("\n") + 1
        return content

    def _compress_urls(self, content: str, stats: dict) -> str:
        self._url_refs.clear()
        self._url_counter = 0
        url_pattern = re.compile(r"https?://\S+")

        def _replace_url(m: re.Match) -> str:
            self._url_counter += 1
            ref = f"{{ref_{self._url_counter}}}"
            self._url_refs[ref] = m.group(0)
            return ref

        result = url_pattern.sub(_replace_url, content)
        stats["urls_replaced"] = self._url_counter
        stats["url_map"] = dict(self._url_refs)
        return result

    def _compress_stacktrace(self, content: str, stats: dict) -> str:
        lines = content.splitlines()
        if not lines:
            return content
        kept = [lines[0]] if lines else []
        exc_line = None
        for line in reversed(lines):
            if re.match(r"^\w+(?:Error|Exception|Warning|Fault|Exit|Interrupt)", line):
                exc_line = line
                break
        key_frames = []
        skip_dirs = ("/lib/", "/site-packages/", "/usr/lib/", "node_modules/")
        for line in lines[1:]:
            frame_match = re.match(r'^\s*File "([^"]+)"', line)
            if frame_match:
                path = frame_match.group(1)
                if any(sd in path for sd in skip_dirs):
                    continue
                key_frames.append(line)
        if exc_line:
            key_frames.append(exc_line)
        kept.extend(key_frames)
        stats["original_lines"] = len(lines)
        stats["kept_lines"] = len(kept)
        stats["frames_removed"] = len(lines) - len(kept)
        return "\n".join(kept)

    def _compress_plaintext(self, content: str, ctype: str, stats: dict) -> str:
        content = self._compress_urls(content, stats)
        content = self._dedup(content, stats)
        if ctype == "plaintext" and len(content) > 3000:
            content = self._summarize_truncation(content, stats)
        return content

    def _dedup(self, content: str, stats: dict) -> str:
        lines = content.splitlines()
        if len(lines) < 6:
            return content
        new_lines: list[str] = []
        i = 0
        dedup_count = 0
        while i < len(lines):
            best_repeat = 0
            best_length = 0
            for block_len in range(min(10, (len(lines) - i) // 2), 2, -1):
                block = tuple(lines[i : i + block_len])
                repeat = 1
                j = i + block_len
                while (
                    j + block_len <= len(lines)
                    and tuple(lines[j : j + block_len]) == block
                ):
                    repeat += 1
                    j += block_len
                if repeat > best_repeat:
                    best_repeat = repeat
                    best_length = block_len
            if best_repeat > 1:
                new_lines.extend(lines[i : i + best_length])
                new_lines.append(f"[重复 {best_repeat}x，共 {best_length} 行]")
                i += best_length * best_repeat
                dedup_count += 1
            else:
                new_lines.append(lines[i])
                i += 1
        stats["dedup_blocks"] = dedup_count
        return "\n".join(new_lines)

    def _summarize_truncation(self, content: str, stats: dict) -> str:
        paragraphs = re.split(r"\n\s*\n", content)
        if len(paragraphs) < 3:
            summary = content[:3000]
            stats["truncated"] = True
            stats["original_paragraphs"] = len(paragraphs)
            return summary
        head = paragraphs[0]
        tail_text = "\n\n".join(paragraphs[-2:])
        middle_count = len(paragraphs) - 3
        summary_line = (
            f"\n\n[... 省略 {middle_count} 段落，共约 {len(content)} 字符 ...]\n\n"
        )
        result = head + summary_line + tail_text
        stats["truncated"] = True
        stats["original_paragraphs"] = len(paragraphs)
        stats["kept_paragraphs"] = 3
        return result

    def _record_stats(
        self, content_type: str, original_len: int, compressed_len: int
    ) -> None:
        try:
            ratio = 1.0 - (compressed_len / max(original_len, 1))
            conn = _persist._get_db(str(Path.home() / ".kos" / "usage.db"))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS compression_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_type TEXT DEFAULT '',
                    original_len INTEGER DEFAULT 0,
                    compressed_len INTEGER DEFAULT 0,
                    ratio REAL DEFAULT 0.0,
                    timestamp TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute(
                "INSERT INTO compression_stats (content_type, original_len, compressed_len, ratio) VALUES (?, ?, ?, ?)",
                (content_type, original_len, compressed_len, round(ratio, 4)),
            )
            conn.commit()
            conn.close()
        except Exception as exc:  # noqa: BLE001 — 统计落库失败不影响响应压缩主流程
            logger.warning(
                "compression_stats_record_failed",
                content_type=content_type,
                error=str(exc),
            )


# Module-level compressor for response compression middleware
_router_compressor: _Compressor = _Compressor()


def _flush_all_routers():
    """Flush trace buffers for all Router instances at exit."""
    import contextlib

    for r in _routers:
        with contextlib.suppress(Exception):
            r._flush_traces()


class Router:
    """Routes tool calls to the appropriate registered service via protocol dispatch.

    Supports:
    - Exact and prefix-based route resolution
    - Circuit breaker awareness (skips OPEN services)
    - Load balancing with round-robin across service instances
    - Multi-protocol dispatch: mcp (implemented), rest/grpc/stdio (reserved)
    - Event bus integration: auto-publishes route:call.succeeded/failed events
    """

    def __init__(
        self,
        registry: ServiceRegistry,
        strategy: str = "round-robin",
        event_bus: EventBus | None = None,
        routes_path: str | None = None,
    ):
        self.registry = registry
        self._event_bus = event_bus
        self._routes: dict[str, str] = {}  # tool_name → service_name
        self._strategy = strategy
        self._rr_index: dict[str, int] = {}  # service_name → next instance index
        self._latencies: deque[float] = deque(maxlen=1000)  # auto-FIFO truncation
        self._degraded_services: set[str] = (
            set()
        )  # track services in degrade mode for exit events
        self._trace_buffer: list[str] = []  # batched disk writes
        self._trace_path = get_data_dir() / "trace_log.jsonl"
        if routes_path:
            self._routes_path = _Path(routes_path)
        else:
            package_root = _Path(__file__).resolve().parents[3]
            package_root_routes = package_root / "agora-routes.json"
            storage_sibling_routes = (
                _Path(registry._storage_path).parent / "agora-routes.json"
            )
            self._routes_path = (
                package_root_routes
                if package_root_routes.exists()
                else storage_sibling_routes
            )
        self._load_routes()
        global _routers, _atexit_registered
        _routers.append(self)
        if not _atexit_registered:
            atexit.register(_flush_all_routers)
            _atexit_registered = True

    def _load_routes(self):
        """Load route mappings from L0 registry + JSON fallback."""

        # Try L0 registry first
        try:
            from agora.l0_registry_loader import load_routes as _l0_routes

            l0 = _l0_routes()
            if l0:
                self._routes = l0
                # Also load JSON for agora-internal routes not in L0
                from agora.persistence import json_load

                data = json_load(self._routes_path, default={})
                json_routes = data.get("routes", {})  # type: ignore[reportAttributeAccessIssue]
                # JSON agora-internal routes supplement L0
                for k, v in json_routes.items():
                    if v == "agora-internal":
                        self._routes[k] = v
                return
        except ImportError:
            pass

        # Fallback: JSON file
        from agora.persistence import json_load

        data = json_load(self._routes_path, default={})
        self._routes = data.get("routes", {})  # type: ignore[reportAttributeAccessIssue]

    def _save_routes(self):
        """Persist route mappings to JSON file."""
        from agora.persistence import json_save

        json_save(self._routes_path, {"routes": self._routes})

    def add_route(self, tool_name: str, service_name: str):
        """Register a tool → service mapping and persist it."""
        self._routes[tool_name] = service_name
        self._save_routes()

    def resolve(self, tool_name: str) -> str | None:
        """Find which service handles a tool. Supports prefix matching."""
        if tool_name in self._routes:
            return self._routes[tool_name]
        # Prefix match: "minerva.research_now" → try "minerva" prefix
        parts = tool_name.split(".", 1)
        if parts[0] in self._routes:
            return self._routes[parts[0]]
        return None

    def _next_instance(self, service_name: str) -> dict | None:
        """Get the next available instance using current strategy (round-robin).

        Skips services in OPEN circuit state.
        """
        svc = self.registry.get(service_name)
        if not svc:
            return None
        if not svc.is_available:
            return None

        result = {  # single instance mode
            "mcp_endpoint": svc.mcp_endpoint,
            "health_endpoint": svc.health_endpoint,
            "port": svc.port,
            "protocol": svc.protocol,
            "protocol_config": svc.protocol_config,
        }

        # Check if this service has multiple instances
        instances = svc.instances
        if instances:
            idx = self._rr_index.get(service_name, 0)
            instance = instances[idx % len(instances)]
            self._rr_index[service_name] = idx + 1
            result = instance

        return result

    def _cached_instance(self, service_name: str, tool_name: str) -> dict | None:
        """Fall back to the local service cache when registry is unavailable.

        Searches the cached service list for the given service_name and
        returns an instance dict compatible with ``_next_instance()`` output.
        """
        cached = _load_service_cache()
        services = cached.get("services", [])
        if not services:
            logger.warning(
                "cache_fallback_empty",
                service=service_name,
                tool=tool_name,
            )
            return None

        for svc in services:
            if not isinstance(svc, dict):
                continue
            if svc.get("name") == service_name:
                logger.info(
                    "cache_fallback_hit",
                    service=service_name,
                    mcp_endpoint=svc.get("mcp_endpoint"),
                )
                return {
                    "mcp_endpoint": svc.get("mcp_endpoint", ""),
                    "health_endpoint": svc.get("health_endpoint", ""),
                    "port": svc.get("port", 0),
                    "protocol": svc.get("protocol", "mcp"),
                    "protocol_config": svc.get("protocol_config", {}),
                }

        logger.warning(
            "cache_fallback_miss",
            service=service_name,
            tool=tool_name,
        )
        return None

    def persist_cache(self) -> bool:
        """Save the current registry service list to the local cache.

        Call this after every successful discovery to keep the cache fresh.
        Converts ``Service.to_dict()`` format (uses ``endpoint`` key) to the
        canonical cache format (uses ``mcp_endpoint`` and ``health_endpoint``).
        """
        from agora.core.service_base import (
            Service as _Service,  # type: ignore[import-not-found]
        )

        def _convert(svc: _Service | dict) -> dict:
            if isinstance(svc, dict):
                d = dict(svc)
                # Normalize key names: endpoint -> mcp_endpoint
                if "mcp_endpoint" not in d and "endpoint" in d:
                    d["mcp_endpoint"] = d.pop("endpoint")
                if "health_endpoint" not in d and "health" in d:
                    d["health_endpoint"] = d.pop("health")
                return d
            # Service dataclass instance
            return {
                "name": svc.name,
                "description": svc.description,
                "protocol": svc.protocol,
                "protocol_config": svc.protocol_config,
                "mcp_endpoint": svc.mcp_endpoint,
                "health_endpoint": svc.health_endpoint or "",
                "port": svc.port,
                "tags": svc.tags,
                "instances": svc.instances,
            }

        services = [_convert(s) for s in self.registry.list_all()]
        return _save_service_cache(services)

    def _add_instance(
        self,
        service_name: str,
        mcp_endpoint: str,
        health_endpoint: str = "",
        port: int = 0,
    ):
        """Add a load-balanced instance to an existing service."""
        svc = self.registry.get(service_name)
        if not svc:
            return
        if not svc.instances:
            # First instance: promote existing to list
            svc.instances.append(
                {
                    "mcp_endpoint": svc.mcp_endpoint,
                    "health_endpoint": svc.health_endpoint,
                    "port": svc.port,
                    "protocol": svc.protocol,
                    "protocol_config": svc.protocol_config,
                }
            )
        svc.instances.append(
            {
                "mcp_endpoint": mcp_endpoint,
                "health_endpoint": health_endpoint or "",
                "port": port or 0,
                "protocol": svc.protocol,
                "protocol_config": svc.protocol_config,
            }
        )

    async def route(
        self,
        tool_name: str,
        arguments: dict,
        caller_id: Identity | dict | str = "unknown",
        use_cache: bool = True,
    ) -> dict:
        """Route a tool call to the target service via protocol dispatch.

        Args:
            tool_name: Name of the tool to invoke.
            arguments: Tool arguments dict.
            caller_id: Identity of the caller for auditing.
            use_cache: If True (default), fall back to the local service cache
                       when the registry is unavailable or returns empty.
        """
        _start = _time.monotonic()
        caller = normalize_identity(caller_id)

        service_name = self.resolve(tool_name)
        if not service_name:
            self._trace(
                tool_name, service_name or "unknown", _start, "error", "not_found"
            )
            logger.warning("route_not_found", tool=tool_name)
            return {"status": "error", "error": "Tool not available"}

        instance = self._next_instance(service_name)
        # ── Degrade exit: previously degraded service is now available ──
        if instance and service_name in self._degraded_services:
            self._degraded_services.discard(service_name)
        if not instance and use_cache:
            # ── Degrade: fall back to local service cache ──────────────
            logger.info(
                "route_cache_fallback",
                tool=tool_name,
                service=service_name,
            )
            self._degraded_services.add(service_name)
            instance = self._cached_instance(service_name, tool_name)

        if not instance:
            self._trace(tool_name, service_name, _start, "error", "no_instance")
            return {"status": "error", "error": "Service temporarily unavailable"}

        # Check for explicit compress flag in request arguments
        compress_requested = (
            arguments.pop("_compress", False) if isinstance(arguments, dict) else False
        )

        try:
            result = await _dispatch(instance, tool_name, arguments)

            # ── Accounting middleware ────────────────────────────────────
            if result.get("status") != "error":
                try:
                    from agora.accounting import (  # type: ignore[import-not-found]
                        CallRecord,
                        ResourceAccountDB,
                        estimate_cost,
                    )

                    # Extract token usage from response if available
                    # Common MCP response patterns for usage info
                    input_tokens = 0
                    output_tokens = 0
                    # Pattern 1: result.meta.usage or result.usage
                    meta = result.get("meta") or {}
                    usage = (
                        meta.get("usage") or result.get("usage") or {}
                        if isinstance(meta, dict)
                        else result.get("usage") or {}
                    )
                    if isinstance(usage, dict):
                        input_tokens = (
                            usage.get("inputTokens") or usage.get("input_tokens") or 0
                        )
                        output_tokens = (
                            usage.get("outputTokens") or usage.get("output_tokens") or 0
                        )
                    # Pattern 2: result.result.usage (nested MCP response)
                    inner = result.get("result") or {}
                    if isinstance(inner, dict):
                        inner_usage = inner.get("usage") or {}
                        if isinstance(inner_usage, dict):
                            input_tokens = (
                                input_tokens
                                or inner_usage.get("inputTokens")
                                or inner_usage.get("input_tokens")
                                or 0
                            )
                            output_tokens = (
                                output_tokens
                                or inner_usage.get("outputTokens")
                                or inner_usage.get("output_tokens")
                                or 0
                            )

                    cost = estimate_cost(input_tokens, output_tokens)

                    record = CallRecord(
                        caller_id=caller.actor,
                        service_name=service_name,
                        tool_name=tool_name,
                        input_tokens=int(input_tokens),
                        output_tokens=int(output_tokens),
                        cost_usd=round(cost, 6),
                        billed_to=caller.billing_subject,
                    )
                    ResourceAccountDB().record_call(record)
                except Exception as acct_err:
                    logger.warning("accounting_record_failed", error=str(acct_err))

            # ── EU cost tracking middleware ────────────────────────────────
            if result.get("status") != "error":
                try:
                    from kaironcloud_billing.pricing.eu_ledger import (  # type: ignore[reportMissingImports]
                        EULedger,  # type: ignore[import-not-found]
                    )

                    # Map tool name to EU operation — fall back to tool prefix
                    eu_operation = (
                        tool_name.split(".")[0] if "." in tool_name else tool_name
                    )
                    tx = EULedger().consume(caller.actor, eu_operation)
                    if not tx.success:
                        logger.info(
                            "eu_cost_tracking_failed",
                            caller=caller.actor,
                            operation=eu_operation,
                            error=tx.error,
                        )
                except Exception as eu_err:
                    logger.warning("eu_cost_tracking_failed", error=str(eu_err))
            # ── End EU cost tracking middleware ────────────────────────────

            if result.get("status") == "error":
                self._trace(
                    tool_name,
                    service_name,
                    _start,
                    "error",
                    result.get("error", "")[:100],
                )
                logger.warning(
                    "route_dispatch_failed",
                    tool=tool_name,
                    service=service_name,
                    error=result.get("error", ""),
                )
                self.registry.mark_failure(service_name)
                self._maybe_publish(
                    "route:call.failed",
                    {
                        "tool": tool_name,
                        "service": service_name,
                        "error": result.get("error", "")[:100],
                        "identity": caller.to_payload(),
                    },
                )
                # Audit
                try:
                    from agora.audit import (
                        AuditLogger,  # type: ignore[import-not-found]
                    )

                    AuditLogger().log(
                        "route.call",
                        caller.actor,
                        service_name,
                        "error",
                        result.get("error", "")[:100],
                    )
                except Exception:  # defensive fallback
                    pass
            else:
                self.registry.mark_success(service_name)
                self._trace(tool_name, service_name, _start, "ok")
                self._maybe_publish(
                    "route:call.succeeded",
                    {
                        "tool": tool_name,
                        "service": service_name,
                        "duration_s": round(_time.monotonic() - _start, 4),
                        "identity": caller.to_payload(),
                    },
                )
                # Audit
                try:
                    from agora.audit import AuditLogger

                    AuditLogger().log("route.call", caller.actor, service_name)
                except Exception:  # defensive fallback
                    pass

            # Compression middleware: compress large responses
            result_json = _json.dumps(result)
            if compress_requested or len(result_json) > 1024:
                compressed = _router_compressor.compress(result_json, "json")
                result = {
                    "compressed": True,
                    "original_len": compressed.original_len,
                    "compressed_len": compressed.compressed_len,
                    "ratio": compressed.ratio,
                    "content": _json.loads(compressed.content),
                    "stats": compressed.stats,
                }
            return result
        except Exception as e:  # defensive fallback
            self._trace(tool_name, service_name, _start, "error", str(e)[:100])
            logger.warning(
                "route_failed", tool=tool_name, service=service_name, error=str(e)
            )
            self.registry.mark_failure(service_name)
            self._maybe_publish(
                "route:call.failed",
                {
                    "tool": tool_name,
                    "service": service_name,
                    "error": str(e)[:100],
                    "identity": caller.to_payload(),
                },
            )
            return {"status": "error", "error": "Routing failed"}

    def _maybe_publish(self, event_type: str, payload: dict):
        """Publish route event if event_bus is configured."""
        if self._event_bus:
            self._event_bus.publish(event_type, payload, "agora-router")

    def _trace(
        self, tool: str, service: str, start: float, status: str, detail: str = ""
    ):
        """Buffer trace entry; flush to disk every 50 calls."""
        elapsed = round(_time.monotonic() - start, 4)

        if status == "ok":
            self._latencies.append(elapsed)

        entry = _json.dumps(
            {
                "time": _time.time(),
                "tool": tool,
                "service": service,
                "status": status,
                "elapsed_s": elapsed,
                "detail": detail,
            }
        )
        self._trace_buffer.append(entry)
        if len(self._trace_buffer) >= 50:
            self._flush_traces()

    def _flush_traces(self):
        """Write buffered traces to disk, auto-rotate at 1MB."""
        if not self._trace_buffer:
            return
        try:
            # Rotate if exceeds 1MB
            if (
                self._trace_path.exists()
                and self._trace_path.stat().st_size > 1_048_576
            ):
                rotated = self._trace_path.with_suffix(".jsonl.1")
                if rotated.exists():
                    rotated.unlink()
                os.rename(self._trace_path, rotated)
            with open(self._trace_path, "a") as f:
                f.write("\n".join(self._trace_buffer) + "\n")
            self._trace_buffer.clear()
        except Exception:  # defensive fallback
            pass

    def get_percentiles(self) -> dict:
        """Calculate P50/P90/P99 from rolling latency window."""
        if not self._latencies:
            return {"p50": 0, "p90": 0, "p99": 0, "samples": 0, "avg": 0}
        sorted_l = sorted(self._latencies)
        n = len(sorted_l)
        return {
            "p50": round(sorted_l[int(n * 0.50)], 4),
            "p90": round(sorted_l[int(n * 0.90)], 4),
            "p99": round(sorted_l[min(int(n * 0.99), n - 1)], 4),
            "samples": n,
            "avg": round(sum(sorted_l) / n, 4),
        }

    def list_routes(self) -> dict[str, str]:
        return dict(self._routes)

    async def close(self):
        """Clean up the shared HTTP client connection pool."""
        await close_client()
