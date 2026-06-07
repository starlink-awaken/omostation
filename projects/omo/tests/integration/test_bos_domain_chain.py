"""P35-W0 omo 端跨 Domain 串联测试 — Registry / Domain 覆盖度.

agora 端 (test_domain_chain.py) 跑真实 stdio 串联.
omo 端 (本测试) 验证:
  - BOS Registry 总数 ≥ 40 (P34-W0 战役 2 拓展)
  - 5 Domain 完整覆盖 (memory/governance/analysis/persona/capability)
  - 跨域跳转所需 URI 全部在 registry (P35 任务规划的真实可链 URI 集合)
  - 至少 5 条跨域跳转 (memory↔analysis, analysis↔persona, persona↔capability,
    capability↔governance, governance↔analysis)
"""
from __future__ import annotations

import json
from pathlib import Path


BOS_REGISTRY = Path("/Users/xiamingxing/Workspace/.omo/_knowledge/bos-registry.json")
OMOSTATION_ROOT = Path("/Users/xiamingxing/Workspace")


# ── Registry 元数据 ─────────────────────────────────

def test_bos_registry_exists():
    """W0 验证: bos-registry.json 存在 (P33-W1 战役 2 落地)."""
    assert BOS_REGISTRY.exists(), f"Registry missing: {BOS_REGISTRY}"


def test_bos_registry_has_at_least_40_uris():
    """W0 验证: bos-registry.json 总数 ≥ 40 (P34-W0 战役 2 拓展)."""
    regs = json.loads(BOS_REGISTRY.read_text())
    assert len(regs) >= 40, f"Expected ≥ 40 URIs, got {len(regs)}"


def test_bos_registry_5_domains_complete():
    """W0 验证: 5 Domain 完整覆盖 (memory/governance/analysis/persona/capability)."""
    regs = json.loads(BOS_REGISTRY.read_text())
    domains = {r.get("domain") for r in regs}
    assert domains == {"memory", "governance", "analysis", "persona", "capability"}, (
        f"Expected 5 domains, got {domains}"
    )


def test_each_domain_has_at_least_5_uris():
    """W0 验证: 每个 Domain 至少 5 条 URI (P34-W0 战役 2 拓展后底线)."""
    regs = json.loads(BOS_REGISTRY.read_text())
    from collections import Counter
    counts = Counter(r.get("domain") for r in regs)
    for domain in ("memory", "governance", "analysis", "persona", "capability"):
        assert counts[domain] >= 5, (
            f"Domain {domain} 只有 {counts[domain]} 条 URI (≥ 5 要求)"
        )


# ── 跨域跳转 URI 集合 (P35 任务规划) ──────────────────

# 5 场景至少 1 个 URI 在 registry
CROSS_DOMAIN_URIS = {
    "memory_to_analysis": [
        "bos://memory/kos/search",
        "bos://analysis/minerva/research",
    ],
    "analysis_to_persona": [
        "bos://analysis/minerva/research",
        "bos://persona/health-profile/summary",
    ],
    "governance_to_analysis": [
        "bos://governance/omo/audit",
        "bos://analysis/minerva/audit",
    ],
    "persona_to_capability": [
        "bos://persona/health-profile/summary",
        "bos://capability/forge/register-tool",
    ],
    "capability_to_governance": [
        "bos://capability/forge/register-tool",
        "bos://governance/omo/audit",
    ],
}


def test_cross_domain_uris_in_registry():
    """W0 验证: 5 跨域跳转的所有 URI 全部在 registry."""
    regs = json.loads(BOS_REGISTRY.read_text())
    all_uris = {r["uri"] for r in regs}
    missing: list[tuple[str, str]] = []
    for scenario_name, uris in CROSS_DOMAIN_URIS.items():
        for uri in uris:
            if uri not in all_uris:
                missing.append((scenario_name, uri))
    assert not missing, f"跨域 URI 缺失: {missing}"


def test_cross_domain_chain_count():
    """W0 验证: 跨域跳转至少 5 条 (P35 任务规划 5 场景)."""
    regs = json.loads(BOS_REGISTRY.read_text())
    all_uris = {r["uri"] for r in regs}
    ok_chains = 0
    for scenario_name, uris in CROSS_DOMAIN_URIS.items():
        if all(u in all_uris for u in uris):
            ok_chains += 1
    assert ok_chains >= 5, f"只 {ok_chains}/5 跨域链 URI 完整在 registry"


# ── 5 域 cross-link 验证 (W0 元数据) ──────────────────

def test_5_domain_cross_link_coverage():
    """W0 验证: 5 域 (memory / governance / analysis / persona / capability) 都在跨域链中."""
    domains_hit: set[str] = set()
    for uris in CROSS_DOMAIN_URIS.values():
        for uri in uris:
            domain = uri.split("/")[2]  # bos://<domain>/...
            domains_hit.add(domain)
    assert domains_hit == {
        "memory", "governance", "analysis", "persona", "capability",
    }, f"跨域链未覆盖 5 域: {domains_hit}"


# ── W0 总结 (P35 报告用) ─────────────────────────────

def test_p35w0_summary():
    """W0 总结: 5 域 + ≥ 40 URI + 5 跨域链 — 跨 Domain 串联基础设施就绪."""
    regs = json.loads(BOS_REGISTRY.read_text())
    from collections import Counter
    counts = Counter(r.get("domain") for r in regs)
    summary = {
        "total_uris": len(regs),
        "domains": dict(counts),
        "cross_domain_chains": len(CROSS_DOMAIN_URIS),
    }
    print(f"\nP35-W0 omo 端跨域串联基础设施: {summary}")
    assert summary["total_uris"] >= 40
    assert summary["cross_domain_chains"] >= 5
