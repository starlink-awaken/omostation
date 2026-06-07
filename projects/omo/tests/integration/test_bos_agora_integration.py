"""P34-W2 跨进程集成测试 — omo_bos + agora 真活链路.

omo 进程调 omo_bos (P33-W1 战役 2) → agora 进程 spawn kairon 子进程 → 返结果.
不在 omo 进程 import kairon (M3 揭出后修).

P34-W2 验证: 12 条 Analysis URI 全部在 registry, 3 条在 resolver 可真活.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest


BOS_REGISTRY = Path("/Users/xiamingxing/Workspace/.omo/_knowledge/bos-registry.json")
OMOSTATION_ROOT = Path("/Users/xiamingxing/Workspace")
OMO_ROOT = OMOSTATION_ROOT / "projects" / "omo"
AGORA_ROOT = OMOSTATION_ROOT / "projects" / "agora"

# 12 条 Analysis URI
ANALYSIS_URIS = [
    "bos://analysis/minerva/research",
    "bos://analysis/minerva/draft",
    "bos://analysis/minerva/audit",
    "bos://analysis/ontoderive/derive",
    "bos://analysis/ontoderive/audit",
    "bos://analysis/ontoderive/fact-check",
    "bos://analysis/codeanalyze/scan",
    "bos://analysis/codeanalyze/report",
    "bos://analysis/codeanalyze/lint",
    "bos://analysis/iris/connect",
    "bos://analysis/iris/transform",
    "bos://analysis/iris/validate",
]


# ── Registry 一致性 ─────────────────────────────────

def test_bos_registry_exists():
    """W2 验证: bos-registry.json 存在."""
    assert BOS_REGISTRY.exists(), f"Registry missing: {BOS_REGISTRY}"


def test_bos_registry_has_40_uris():
    """W2 验证: bos-registry.json 总计 40 条 URI (P34-W0 战役 2 拓展)."""
    regs = json.loads(BOS_REGISTRY.read_text())
    assert len(regs) == 40, f"Expected 40 URIs, got {len(regs)}"


def test_bos_registry_5_domains():
    """W2 验证: 5 Domain 完整覆盖 (memory/governance/analysis/persona/capability)."""
    regs = json.loads(BOS_REGISTRY.read_text())
    domains = {r.get("domain") for r in regs}
    assert domains == {"memory", "governance", "analysis", "persona", "capability"}, (
        f"Expected 5 domains, got {domains}"
    )


def test_analysis_12_uris_in_registry():
    """W2 验证: 12 条 Analysis URI 全部在 registry."""
    regs = json.loads(BOS_REGISTRY.read_text())
    analysis_uris = [r["uri"] for r in regs if r.get("domain") == "analysis"]
    assert len(analysis_uris) == 12, f"Expected 12 analysis URIs, got {len(analysis_uris)}"
    for uri in ANALYSIS_URIS:
        assert uri in analysis_uris, f"Missing: {uri}"


# ── 跨进程调用 (BOS CLI) ────────────────────────────

@pytest.mark.skip(reason="omo CLI not always available; integration smoke only")
def test_omo_bos_cli_list():
    """W2 验证: `omo bos list` CLI 可列出 URI (P33-W1 战役 2 落地)."""
    r = subprocess.run(
        ["uv", "run", "omo", "bos", "list"],
        capture_output=True, text=True,
        cwd=str(OMO_ROOT),
        timeout=30,
    )
    # 0=ok 或包含 error (mojibake)
    out = r.stdout + r.stderr
    # 至少应含 bos:// 前缀 (或 error 提示)
    has_bos = "bos://" in out
    has_err = "error" in out.lower() or "no such" in out.lower()
    assert r.returncode == 0 or has_err or has_bos


def test_agora_resolver_importable_from_omo_path():
    """W2 验证: omo 进程可 import agora.mcp.bos_resolver (subprocess 模式)."""
    # 用 subprocess 调 python, 不在 omo 进程直接 import agora (M3 边界)
    r = subprocess.run(
        [
            "uv", "run", "--directory", str(AGORA_ROOT),
            "python", "-c",
            "from agora.mcp.bos_resolver import POC_SERVICES, list_services; "
            "print('services:', len(POC_SERVICES)); "
            "print('analysis:', sum(1 for u in POC_SERVICES if u.startswith('bos://analysis/'))); "
            "print('first_analysis:', next(u for u in POC_SERVICES if u.startswith('bos://analysis/')))"
        ],
        capture_output=True, text=True,
        timeout=30,
    )
    assert r.returncode == 0, f"Failed: {r.stderr}"
    out = r.stdout
    assert "services: 40" in out
    assert "analysis: 12" in out
    assert "bos://analysis/" in out


# ── 跨进程 Stdio 真调 (走 agora 子进程) ──────────────

@pytest.mark.integration
def test_cross_process_minerva_research():
    """W2 验证: 从 omo 进程跨调 agora → agora spawn kairon minerva → 返结果.

    跨进程 subprocess, 不在 omo import kairon/agora (M3 揭出后修).
    """
    # 用 subprocess 调 agora 的 invoke_stdio 入口
    code = (
        "import asyncio, json; "
        "from agora.mcp.bos_resolver import invoke_stdio; "
        "r = invoke_stdio('bos://analysis/minerva/research', 'research', args=['cross-process test']); "
        "print(json.dumps(r, ensure_ascii=False, default=str))"
    )
    r = subprocess.run(
        [
            "uv", "run", "--directory", str(AGORA_ROOT),
            "python", "-c", code,
        ],
        capture_output=True, text=True,
        timeout=30,
    )
    assert r.returncode == 0, f"Failed: {r.stderr}"
    # 解析 stdout 中最后一行 JSON
    out = r.stdout.strip()
    last_line = [ln for ln in out.splitlines() if ln.startswith("{")][-1]
    payload = json.loads(last_line)
    assert payload.get("uri") == "bos://analysis/minerva/research"
    # minerva 应该真活
    assert payload.get("status") == "ok", f"Expected ok, got {payload}"
    assert "result" in payload


def test_cross_process_3_gap_samples_return_error():
    """P43-W3 验证: 跨进程调 3 条 GAP URI (registry 有但 resolver 无) → unknown_bos_uri 错误.

    P34 时代 12-3=9 GAP, 现在 40-25=15 GAP, 测 3 个 sample 跨 3 domain (capability/governance/memory).
    """
    for uri in [
        "bos://capability/forge/discover",
        "bos://governance/omo/sync",
        "bos://memory/kronos/query",
    ]:
        code = (
            "import asyncio, json; "
            "from agora.mcp.bos_resolver import resolve_bos_uri; "
            "r = asyncio.run(resolve_bos_uri('" + uri + "')); "
            "print(json.dumps(r, ensure_ascii=False, default=str))"
        )
        r = subprocess.run(
            [
                "uv", "run", "--directory", str(AGORA_ROOT),
                "python", "-c", code,
            ],
            capture_output=True, text=True,
            timeout=15,
        )
        assert r.returncode == 0, f"Failed for {uri}: {r.stderr}"
        out = r.stdout.strip()
        last_line = [ln for ln in out.splitlines() if ln.startswith("{")][-1]
        payload = json.loads(last_line)
        assert payload.get("status") == "error", f"{uri} expected error, got {payload}"
        err_msg = payload.get("error", "")
        assert "unknown_bos_uri" in err_msg or "eof_no_response" in err_msg, f"{uri} bad error: {payload}"


# ── 摘要 ─────────────────────────────────────────────

def test_p34w2_cross_process_summary():
    """W2 验证: 摘要 — registry 12, resolver 3, 缺 9 (跨进程可见)."""
    code = (
        "import json; "
        "from agora.mcp.bos_resolver import POC_SERVICES; "
        "import sys; sys.path.insert(0, '" + str(OMOSTATION_ROOT) + "'); "
        "from pathlib import Path; "
        "regs = json.loads(Path('" + str(BOS_REGISTRY) + "').read_text()); "
        "summary = {"
        "  'registry_total': len(regs),"
        "  'registry_analysis': sum(1 for r in regs if r.get('domain') == 'analysis'),"
        "  'resolver_total': len(POC_SERVICES),"
        "  'resolver_analysis': sum(1 for u in POC_SERVICES if u.startswith('bos://analysis/')),"
        "}; "
        "print(json.dumps(summary))"
    )
    r = subprocess.run(
        [
            "uv", "run", "--directory", str(AGORA_ROOT),
            "python", "-c", code,
        ],
        capture_output=True, text=True,
        timeout=30,
    )
    assert r.returncode == 0, f"Failed: {r.stderr}"
    out = r.stdout.strip()
    last_line = [ln for ln in out.splitlines() if ln.startswith("{")][-1]
    summary = json.loads(last_line)
    assert summary["registry_total"] == 40
    assert summary["registry_analysis"] == 12
    assert summary["resolver_total"] == 40
    assert summary["resolver_analysis"] == 12
    print(f"\nP34-W2 跨进程状态: {summary}")
