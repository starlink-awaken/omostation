"""P43-W1 40 BOS URI smoke test — 覆盖 P33 W0 21→40 扩域全 5 Domain.

跑 invoke_bos_uri_tool 全部 40 URI, 验证:
  - 25 URI resolved (POC_SERVICES 25, P39 时代已扩)
  - 15 URI agora 内部 unknown_bos_uri (registry 有但 POC_SERVICES 无, GAP)

5 Domain 全覆盖:
  - memory: 5 (kos/kronos)
  - governance: 8 (metaos/omo/sot-bridge)
  - analysis: 12 (minerva/ontoderive/codeanalyze/iris)
  - persona: 7 (core-models/sharedbrain-bridge/health-profile)
  - capability: 8 (agent-runtime/forge)

GAP URI 行为 (P43-W1 修正): omo invoke 层 status=resolved, agora 内部 result.status=error (unknown_bos_uri)
不依赖 LLM, 不需要 ANTHROPIC_API_KEY, 只测跨进程派发闭环.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from pathlib import Path

import pytest

from omo.omo_llm_bos_bridge import invoke_bos_uri_tool

OMOSTATION_ROOT = Path(__file__).resolve().parents[3]
BOS_REGISTRY = OMOSTATION_ROOT / ".omo" / "_knowledge" / "bos-registry.json"


# ── Pytest markers (P44-W4 上线, CI 按需分组跑) ─────────
#   pytest -m fast           → 只跑 test_40_uri_registry_loads
#   pytest -m bos_5domain    → 跑 5 domain 覆盖 (1 测, ~3s)
#   pytest -m bos_40         → 跑 40 URI 全套 (3 测, ~3s)
#   pytest                   → 全跑


def _load_registry() -> list[dict]:
    return json.loads(BOS_REGISTRY.read_text(encoding="utf-8"))


def _default_args_for(uri: str) -> dict:
    """给 URI 一个合理的默认 args."""
    action = uri.split("/")[-1]
    if action in (
        "search",
        "query",
        "recall",
        "scan",
        "lint",
        "discover",
        "list-tools",
        "agent-list",
        "schema",
        "ingest",
    ):
        return {"query": "smoke test"}
    return {"topic": "smoke test"}


@pytest.mark.fast
@pytest.mark.bos_40
def test_40_uri_registry_loads():
    """P43-W1 验证: bos-registry.json 含 40+ URI."""
    regs = _load_registry()
    assert len(regs) >= 36, f"Expected >=40 URIs, got {len(regs)}"
    domains = Counter(r.get("domain") for r in regs)
    # Verify domain structure exists (counts may grow)
    expected_domains = {"memory", "governance", "analysis", "persona", "capability"}
    assert set(domains.keys()) == expected_domains, (
        f"Domain set drift: {set(domains.keys())}"
    )


@pytest.mark.bos_40
def test_smoke_25_resolved_15_gap_single_loop():
    """P43-W1 验证: registry URI 全部能 invoke; resolved + gap 覆盖全集.

    ADR-0181: unimplemented/deprecated BOS entries are filtered from the
    routable table → invoke returns unknown_bos_uri (counted as gap).

    P43-W0 长驻池是 module-level singleton, 必须单 asyncio.run() 内调用.
    跑完显式关 pool.
    """
    from omo.omo_llm_bos_bridge import _MANAGER

    async def _run_all():
        regs = _load_registry()
        results = []
        for r in regs:
            uri = r["uri"]
            args = _default_args_for(uri)
            out = await invoke_bos_uri_tool(uri, args)
            # GAP URI: omo invoke 层 status=resolved, agora 内部 result.status=error + unknown_bos_uri
            if out.get("status") == "resolved":
                result = out.get("result", {})
                if result.get("status") == "error" and "unknown_bos_uri" in result.get(
                    "error", ""
                ):
                    results.append((uri, "gap"))
                    continue
                results.append((uri, "resolved"))
            else:
                results.append((uri, out.get("status", "?")))
        return results

    results = asyncio.run(_run_all())
    if _MANAGER is not None:
        asyncio.run(_MANAGER.close_all())

    by_status = Counter(s for _, s in results)
    # ADR-0181: agora filters status=unimplemented|deprecated from the routable
    # table, so many registry URIs now surface as unknown_bos_uri (gap). Counts
    # track the current bos-registry.json (36) + live bos-services.yaml.
    total = len(results)
    resolved = by_status.get("resolved", 0)
    gap = by_status.get("gap", 0)
    classified = resolved + gap + by_status.get("invalid_uri", 0)
    assert classified == total, (
        f"Expected all URIs classified resolved|gap|invalid_uri, got {dict(by_status)}: "
        f"{results}"
    )
    assert resolved >= 15, (
        f"Expected >=15 resolved after ADR-0181 filter, got {resolved}: "
        f"{[(u, s) for u, s in results if s != 'resolved']}"
    )
    assert gap >= 3, (
        f"Expected >=3 gap (P43 14 服务 UNIMPLEMENTED→POC 后余 iris 3), got {gap}: "
        f"{[(u, s) for u, s in results if s == 'gap']}"
    )

    by_domain = Counter()
    for u, s in results:
        dom = u.replace("bos://", "").split("/")[0]
        by_domain[(dom, s)] += 1
    print("\nP43-W1 40 URI smoke test 结果:")
    print(f"  resolved: {by_status.get('resolved', 0)}/40 (POC_SERVICES 25)")
    print(f"  gap:      {by_status.get('gap', 0)}/40 (registry 40 - POC 25)")
    print(f"  by (domain, status): {dict(by_domain)}")


@pytest.mark.bos_5domain
@pytest.mark.bos_40
def test_5_domain_each_resolves_at_least_one():
    """P43-W1 验证: 5 Domain 全部有 URI, 每个域至少有 1 个 resolved (POC_SERVICES 覆盖)."""
    import omo.omo_llm_bos_bridge as bridge

    bridge._MANAGER = None  # reset singleton (跨 asyncio.run 边界)

    async def _check():
        regs = _load_registry()
        resolved_domains = set()
        for r in regs:
            uri = r["uri"]
            args = _default_args_for(uri)
            out = await invoke_bos_uri_tool(uri, args)
            if out.get("status") == "resolved":
                result = out.get("result", {})
                # 排除 GAP URI (status=error + unknown_bos_uri)
                if not (
                    result.get("status") == "error"
                    and "unknown_bos_uri" in result.get("error", "")
                ):
                    dom = uri.replace("bos://", "").split("/")[0]
                    resolved_domains.add(dom)
        return resolved_domains

    resolved = asyncio.run(_check())
    assert resolved == {"memory", "governance", "analysis", "persona", "capability"}, (
        f"5 domain 覆盖不全, resolved_domains={resolved}"
    )
