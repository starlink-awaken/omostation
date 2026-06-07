"""Mesh MCP Server — exposes compute mesh functionality via MCP protocol.

Integrates all mesh layers (topology + pool + scheduler) into MCP tools
that the eCOS agora hub can route to.
"""

from __future__ import annotations

from fastmcp import FastMCP

from ..pool import ComputePool, CostTracker

# Global pool instance (lazily initialized)
_pool: ComputePool | None = None


def _get_pool() -> ComputePool:
    global _pool
    if _pool is None:
        _pool = ComputePool()
        _pool.scan()
    return _pool


mcp = FastMCP("aetherforge-mesh")


@mcp.tool()
async def mesh_list_nodes() -> str:
    """List all compute nodes in the mesh."""
    pool = _get_pool()
    nodes = pool.registry.get_all()
    if not nodes:
        return "No compute nodes discovered."

    lines = [f"🔮 AetherForge Mesh — {len(nodes)} nodes:"]
    for n in sorted(nodes, key=lambda x: (x.network_zone, x.node_id)):
        icon = "🟢" if n.is_online else "🔴"
        load = f"{n.load_factor:.1f}"
        lines.append(f"  {icon} {n.node_id:28s} {n.engine_type.value:15s} zone={n.network_zone} load={load} status={n.status.value}")
    return "\n".join(lines)


@mcp.tool()
async def mesh_status() -> str:
    """Get overall mesh health and load status."""
    pool = _get_pool()
    summary = pool.get_summary()
    return (
        f"Total: {summary['total']} | Online: {summary['online']} | "
        f"Offline: {summary['offline']} | Zones: {summary['zones']}"
    )


@mcp.tool()
async def mesh_health_check() -> str:
    """Run health checks on all nodes."""
    pool = _get_pool()
    results = pool.health_check_all()
    online = sum(1 for v in results.values() if v)
    lines = [f"🏥 {online}/{len(results)} nodes online:"]
    for node_id, is_alive in results.items():
        icon = "🟢" if is_alive else "🔴"
        lines.append(f"  {icon} {node_id}")
    return "\n".join(lines)


@mcp.tool()
async def mesh_cost_report() -> str:
    """Show cost report for the current session."""
    pool = _get_pool()
    tracker = CostTracker(pool.registry)
    report = tracker.get_report()
    return (
        f"Total cost: ${report['total_cost']:.6f} | "
        f"Requests: {report['total_requests']} | "
        f"Nodes: {len(report['nodes'])}"
    )


@mcp.tool()
async def mesh_generate(prompt: str) -> str:
    """Generate text via the best available compute node.

    Args:
        prompt: The prompt text to send to the model.
    """
    pool = _get_pool()
    best = pool.get_best_node()
    if best is None:
        return "❌ No online compute nodes available."

    provider_name = best.protocols[0] if best.protocols else ""
    if not provider_name:
        return f"❌ Node {best.node_id} has no known protocol."

    from llm_gateway.detection import create_provider
    from llm_gateway.provider import LLMRequest

    provider = create_provider(provider_name)
    if not provider or not provider.is_available():
        return f"❌ Provider {provider_name} not available."

    req = LLMRequest(prompt=prompt)
    try:
        resp = provider.complete(req)
        result = resp.content
        if resp.input_tokens:
            result += f"\n\n[{resp.model}] {resp.input_tokens} in / {resp.output_tokens} out"
        return result
    except Exception as e:
        return f"❌ Generation failed: {e}"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
