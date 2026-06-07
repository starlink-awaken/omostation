"""P36-W1 跨 Domain 串联测试 — 5 场景真实 stdio 调用 (含 GAP 补 5 URI).

P35-W0 验证: 跨 Domain URI 真能串联 — LLM 调一次 bos://memory/kos/search 拿结果,
再调 bos://analysis/minerva/draft 生成草稿. 端到端 stdio 协议 (P34-W1 同款), 不 mock.

P36-W1 升级: 补 5 条 GAP URI (P35-W0 spec 注册但未在 POC_SERVICES):
  - bos://persona/sharedbrain-bridge/recall-entity
  - bos://persona/health-profile/alert
  - bos://capability/forge/exec-tool
  - bos://capability/forge/list-tools
  - bos://governance/omo/inspect

5 场景 (每场景末 2-3 个 URI 跨域串联):
  1. memory → analysis      (kos.search → minerva.research → minerva.draft)
  2. analysis → persona     (minerva.research → health-profile.summary → health-profile.alert)
  3. governance → analysis  (omo.audit → minerva.audit)
  4. persona → capability   (sharedbrain-bridge.recall-entity → forge.list-tools → forge.exec-tool)
  5. capability → governance(forge.list-tools → omo.inspect)

P36-W1 应 11/11 全 ok (P35-W0 是 9/11).
"""
from __future__ import annotations

import asyncio
import time

from agora.mcp.bos_resolver import POC_SERVICES, resolve_bos_uri


# ── 5 场景链 (每链 2-3 URI) ──────────────────────────
CHAIN_SCENARIOS = [
    {
        "name": "memory_to_analysis",
        "chain": [
            ("bos://memory/kos/search", {"query": "kairon 2026-06 commits"}),
            ("bos://analysis/minerva/research", {"topic": "kairon 2026-06 commits"}),
            ("bos://analysis/minerva/draft", {"topic": "kairon 2026-06 commits"}),
        ],
    },
    {
        "name": "analysis_to_persona",
        "chain": [
            ("bos://analysis/minerva/research", {"topic": "kairon persona"}),
            ("bos://persona/health-profile/summary", {"member_id": "夏明星"}),
            ("bos://persona/health-profile/alert", {"member_id": "夏明星", "level": "info"}),
        ],
    },
    {
        "name": "governance_to_analysis",
        "chain": [
            ("bos://governance/omo/audit", {}),
            ("bos://analysis/minerva/audit", {}),
        ],
    },
    {
        "name": "persona_to_capability",
        "chain": [
            ("bos://persona/sharedbrain-bridge/recall-entity", {"entity_id": "user-001"}),
            ("bos://capability/forge/list-tools", {}),
            ("bos://capability/forge/exec-tool", {"name": "echo-tool"}),
        ],
    },
    {
        "name": "capability_to_governance",
        "chain": [
            ("bos://capability/forge/list-tools", {}),
            ("bos://governance/omo/inspect", {}),
        ],
    },
]


def _run_chain(scenario: dict, timeout_per_call: float = 6.0) -> list[dict]:
    """执行一个链, 返回每步结果 (uri, status, elapsed, error?)."""
    out: list[dict] = []
    for uri, kwargs in scenario["chain"]:
        start = time.monotonic()
        try:
            r = asyncio.run(resolve_bos_uri(uri, **kwargs))
        except Exception as exc:  # noqa: BLE001
            r = {"uri": uri, "status": "error", "error": f"exception: {exc}"}
        elapsed = time.monotonic() - start
        out.append({
            "uri": uri,
            "status": r.get("status", "error"),
            "elapsed": round(elapsed, 2),
            "transport": r.get("transport"),
            "in_resolver": uri in POC_SERVICES,
            "error": r.get("error") if r.get("status") != "ok" else None,
        })
    return out


# ── 单场景测试 (P36-W1 全 100%) ───────────────────────

def test_scenario_1_memory_to_analysis():
    """场景 1: memory.kos.search → analysis.minerva.research → analysis.minerva.draft."""
    scenario = CHAIN_SCENARIOS[0]
    results = _run_chain(scenario)
    ok = sum(1 for r in results if r["status"] == "ok")
    # P36-W1 应 3/3 全 ok
    assert ok == 3, (
        f"场景 1 (memory→analysis) 只 {ok}/3 ok: {results}"
    )
    print(f"\n[场景1 memory→analysis] {ok}/3 ok: {results}")


def test_scenario_2_analysis_to_persona():
    """场景 2: analysis → persona (P36-W1 加 alert 升级 3/3)."""
    scenario = CHAIN_SCENARIOS[1]
    results = _run_chain(scenario)
    ok = sum(1 for r in results if r["status"] == "ok")
    # P36-W1 应 3/3 全 ok (P35-W0 是 1/2)
    assert ok == 3, (
        f"场景 2 (analysis→persona) 只 {ok}/3 ok: {results}"
    )
    print(f"\n[场景2 analysis→persona] {ok}/3 ok: {results}")


def test_scenario_3_governance_to_analysis():
    """场景 3: governance → analysis."""
    scenario = CHAIN_SCENARIOS[2]
    results = _run_chain(scenario)
    ok = sum(1 for r in results if r["status"] == "ok")
    # P36-W1 应 2/2 全 ok
    assert ok == 2, (
        f"场景 3 (governance→analysis) 只 {ok}/2 ok: {results}"
    )
    print(f"\n[场景3 governance→analysis] {ok}/2 ok: {results}")


def test_scenario_4_persona_to_capability():
    """W1 验证: persona → capability 3/3 ok (P35-W0 是 1/2, P36-W1 加 sharedbrain-bridge + exec-tool)."""
    scenario = CHAIN_SCENARIOS[3]
    results = _run_chain(scenario)
    ok = sum(1 for r in results if r["status"] == "ok")
    # P36-W1 应 3/3 全 ok
    assert ok == 3, (
        f"场景 4 (persona→capability) 只 {ok}/3 ok: {results}"
    )
    print(f"\n[场景4 persona→capability] {ok}/3 ok: {results}")


def test_scenario_5_capability_to_governance():
    """W1 验证: capability → governance 2/2 ok (P35-W0 GAP 补, list-tools + omo.inspect)."""
    scenario = CHAIN_SCENARIOS[4]
    results = _run_chain(scenario)
    ok = sum(1 for r in results if r["status"] == "ok")
    # P36-W1 应 2/2 全 ok
    assert ok == 2, (
        f"场景 5 (capability→governance) 只 {ok}/2 ok: {results}"
    )
    print(f"\n[场景5 capability→governance] {ok}/2 ok: {results}")


# ── W0 总结 (P36-W1 升级 100%) ───────────────────────

def test_all_5_scenarios_summary():
    """W1 总结: 5 场景整体通过率 100% (P35-W0 是 81.8%, 9/11)."""
    total_steps = 0
    total_ok = 0
    total_in_resolver = 0
    total_resolver_ok = 0
    scenario_results = []
    for scenario in CHAIN_SCENARIOS:
        results = _run_chain(scenario)
        ok = sum(1 for r in results if r["status"] == "ok")
        in_resolver = sum(1 for r in results if r["in_resolver"])
        resolver_ok = sum(1 for r in results if r["in_resolver"] and r["status"] == "ok")
        total_steps += len(results)
        total_ok += ok
        total_in_resolver += in_resolver
        total_resolver_ok += resolver_ok
        scenario_results.append({
            "name": scenario["name"],
            "ok": ok,
            "total": len(results),
            "in_resolver": in_resolver,
            "resolver_ok": resolver_ok,
        })

    rate = total_ok / total_steps if total_steps else 0.0
    resolver_rate = total_resolver_ok / total_in_resolver if total_in_resolver else 0.0
    summary = {
        "scenarios": scenario_results,
        "total_ok": total_ok,
        "total_steps": total_steps,
        "overall_rate": round(rate * 100, 1),
        "in_resolver_steps": total_in_resolver,
        "in_resolver_ok": total_resolver_ok,
        "resolver_rate": round(resolver_rate * 100, 1),
    }
    print(f"\nP36-W1 跨 Domain 串联总结: {summary}")

    # P36-W1: 整体 100% ok (P35-W0 是 ≥ 50%)
    assert rate == 1.0, f"P36-W1 应 100% ok, 实际 {rate*100:.1f}%: {summary}"


# ── 跨域覆盖度 (W0 元数据, P36-W1 守) ────────────────

def test_5_domains_covered_by_chains():
    """W1 验证: 5 个 chain 至少覆盖 4 个 domain (跨域必备)."""
    domains_hit: set[str] = set()
    for scenario in CHAIN_SCENARIOS:
        for uri, _ in scenario["chain"]:
            domain = uri.split("/")[2]  # bos://<domain>/...
            domains_hit.add(domain)
    assert len(domains_hit) >= 4, (
        f"只覆盖 {len(domains_hit)} domains: {domains_hit}"
    )


def test_chain_steps_respect_transport_modes():
    """W1 验证: 链中至少 1 步是 stdio, 至少 1 步是 internal (覆盖两种 transport)."""
    transport_modes: set[str] = set()
    for scenario in CHAIN_SCENARIOS:
        for uri, _ in scenario["chain"]:
            svc = POC_SERVICES.get(uri)
            if svc is not None:
                transport_modes.add(svc.transport)
    # 至少 stdio + internal 二者
    assert "stdio" in transport_modes and "internal" in transport_modes, (
        f"链未覆盖 stdio + internal 两种 transport: {transport_modes}"
    )


# ── W1 GAP 全补验证 (P36-W1 新增) ───────────────────

def test_w1_gap_5_uris_all_registered():
    """W1 验证: P35-W0 GAP 5 条 URI 全部在 POC_SERVICES 注册."""
    spec_uris = [
        "bos://persona/sharedbrain-bridge/recall-entity",
        "bos://persona/health-profile/alert",
        "bos://capability/forge/exec-tool",
        "bos://capability/forge/list-tools",
        "bos://governance/omo/inspect",
    ]
    missing = [u for u in spec_uris if u not in POC_SERVICES]
    assert not missing, f"P36-W1 GAP 补失败, 仍缺: {missing}"
    print("\nP36-W1 GAP 全补: 5/5 URI 已注册")


# ── P36-W1 11/11 总结 ────────────────────────────────

def test_all_5_scenarios_100pct_w1():
    """W1 验证: 5 场景整体 11/11 全 ok (P35-W0 是 9/11)."""
    total_chains = 0
    total_ok = 0
    for scenario in CHAIN_SCENARIOS:
        for uri, kwargs in scenario["chain"]:
            r = asyncio.run(resolve_bos_uri(uri, **kwargs))
            total_chains += 1
            if r.get("status") == "ok":
                total_ok += 1
    rate = total_ok / total_chains if total_chains else 0
    print(f"跨域 11 条: {total_ok}/{total_chains} ({rate*100:.1f}%)")
    assert rate == 1.0, f"应 100%, 实际 {rate*100:.1f}%"
