"""Unit tests for omo.omo_bos — P33-W1 战役 2 起步.

Covers:
- BOS URI validation (5 domain whitelist + kebab-case)
- Parsing round-trip
- Local JSON persistence (register, list, idempotency)
- SEED_REGISTRATIONS consistency
- CLI subcommands dispatch

P33-W1 约束: 纯本地 JSON 持久化, 不写 KOS.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from omo.omo_bos import (
    ALLOWED_DOMAINS,
    BOS_URI_PATTERN,
    DEFAULT_REGISTRY_PATH,
    SEED_REGISTRATIONS,
    list_registrations,
    load_registry,
    parse_bos_uri,
    register_seeds,
    register_uri,
    save_registry,
    validate_bos_uri,
)


# ── 验证逻辑 ──────────────────────────────────────────────


def test_validate_bos_uri_valid_21_seed_uris() -> None:
    """21 条 SEED 起步 URI 全部通过验证 (6 W1 + 15 W2)."""
    assert len(SEED_REGISTRATIONS) == 21
    for r in SEED_REGISTRATIONS:
        valid, err = validate_bos_uri(r.uri)
        assert valid, f"{r.uri} 验证失败: {err}"
        assert r.domain in ALLOWED_DOMAINS


def test_validate_bos_uri_invalid_domain() -> None:
    """非 5 个白名单 domain 一律 FAIL."""
    bad_uris = [
        "bos://unknown/foo/bar",
        "bos://memoryx/kos/search",
        "bos://MEMORY/kos/search",
        "bos://ai/foo/bar",
    ]
    for uri in bad_uris:
        valid, err = validate_bos_uri(uri)
        assert not valid, f"应被拒: {uri}"
        assert "Invalid BOS URI" in err
        assert uri in err or "bos://" in err


def test_validate_bos_uri_invalid_format() -> None:
    """格式错误 (缺 //, 段数错, 大写) 一律 FAIL."""
    bad_uris = [
        "memory/kos/search",         # 缺 bos:// 前缀
        "bos:/memory/kos/search",    # 单斜杠
        "bos://memory",              # 段数不足
        "bos://memory/kos",          # 段数不足
        "bos://memory/kos/search/extra",  # 段数过多
        "bos://memory/KOS/search",   # 大写不通过 kebab-case
        "bos://memory/-kos/search",  # 开头不能 -
        "bos://memory/kos-/search",  # 末尾 - 也不行
        "",                          # 空
    ]
    for uri in bad_uris:
        valid, err = validate_bos_uri(uri)
        assert not valid, f"应被拒: {uri!r}"


def test_parse_bos_uri_roundtrip() -> None:
    """parse 与正则 groupdict 一致."""
    uri = "bos://governance/sot-bridge/register"
    parsed = parse_bos_uri(uri)
    assert parsed == {
        "domain": "governance",
        "package": "sot-bridge",
        "action": "register",
    }
    # invalid 抛 ValueError
    with pytest.raises(ValueError):
        parse_bos_uri("bos://invalid/foo/bar")


# ── 本地 JSON 持久化 ──────────────────────────────────────


def test_register_and_list_roundtrip(tmp_path: Path) -> None:
    """register → save → load → list 链路通畅."""
    reg_path = tmp_path / "bos-registry.json"
    result = register_uri(
        uri="bos://memory/kos/search",
        endpoint="kairon.packages.kos.ontology.store:search_entities",
        protocol="internal",
        description="test roundtrip",
        path=reg_path,
    )
    assert result["uri"] == "bos://memory/kos/search"
    assert result["status"] == "registered"
    assert result["total"] == 1
    assert reg_path.exists()

    # 落盘内容可解析
    raw = json.loads(reg_path.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert len(raw) == 1
    assert raw[0]["uri"] == "bos://memory/kos/search"
    assert raw[0]["domain"] == "memory"

    # list 读回一致
    regs = list_registrations(path=reg_path)
    assert len(regs) == 1
    assert regs[0].uri == "bos://memory/kos/search"
    assert regs[0].endpoint == "kairon.packages.kos.ontology.store:search_entities"


def test_register_idempotent(tmp_path: Path) -> None:
    """重复注册同一 URI 不报错, 状态为 updated, 总数不变."""
    reg_path = tmp_path / "bos-registry.json"
    r1 = register_uri(
        uri="bos://memory/kos/search",
        endpoint="endpoint-v1",
        description="first call",
        path=reg_path,
    )
    assert r1["status"] == "registered"
    assert r1["total"] == 1
    first_at = json.loads(reg_path.read_text(encoding="utf-8"))[0]["registered_at"]

    r2 = register_uri(
        uri="bos://memory/kos/search",
        endpoint="endpoint-v2",
        description="second call",
        path=reg_path,
    )
    assert r2["status"] == "updated"
    assert r2["total"] == 1  # 总数不变
    raw = json.loads(reg_path.read_text(encoding="utf-8"))
    assert len(raw) == 1
    assert raw[0]["endpoint"] == "endpoint-v2"  # 字段已更新
    assert raw[0]["description"] == "second call"
    # registered_at 保留首次时间
    assert raw[0]["registered_at"] == first_at


def test_register_seeds_writes_21(tmp_path: Path) -> None:
    """register_seeds 一次性写 21 条 SEED (6 W1 + 15 W2)."""
    reg_path = tmp_path / "bos-registry.json"
    results = register_seeds(path=reg_path)
    assert len(results) == 21
    for r in results:
        assert "error" not in r, f"SEED 注册失败: {r}"
        assert r["status"] in ("registered", "updated")
    # 文件存在且有 21 条
    assert reg_path.exists()
    raw = load_registry(path=reg_path)
    assert len(raw) == 21
    uris = {r["uri"] for r in raw}
    expected_uris = {s.uri for s in SEED_REGISTRATIONS}
    assert uris == expected_uris


def test_register_seeds_idempotent(tmp_path: Path) -> None:
    """register_seeds 调用两次, 总数仍为 21 (幂等)."""
    reg_path = tmp_path / "bos-registry.json"
    r1 = register_seeds(path=reg_path)
    r2 = register_seeds(path=reg_path)
    assert len(r1) == 21
    assert len(r2) == 21
    # 第二次全部应是 updated
    assert all(r["status"] == "updated" for r in r2)
    # 落盘总数仍 21
    raw = load_registry(path=reg_path)
    assert len(raw) == 21


def test_save_registry_atomic_writes_valid_json(tmp_path: Path) -> None:
    """save_registry 写出可解析 JSON, 不留临时文件."""
    reg_path = tmp_path / "bos-registry.json"
    sample = [{"uri": "bos://memory/kos/search", "domain": "memory",
               "package": "kos", "action": "search"}]
    save_registry(sample, path=reg_path)
    assert reg_path.exists()
    parsed = json.loads(reg_path.read_text(encoding="utf-8"))
    assert parsed == sample
    # 临时文件应已被 rename 替换
    leftovers = list(tmp_path.glob(".bos-registry.*.json.tmp"))
    assert leftovers == []


def test_load_registry_missing_file(tmp_path: Path) -> None:
    """文件不存在 → 空列表 (不抛异常)."""
    reg_path = tmp_path / "does-not-exist.json"
    assert load_registry(path=reg_path) == []


def test_list_registrations_domain_filter(tmp_path: Path) -> None:
    """list_registrations 按 domain 过滤 — 5 Domain 全覆盖."""
    reg_path = tmp_path / "bos-registry.json"
    register_seeds(path=reg_path)
    memory_only = list_registrations(domain="memory", path=reg_path)
    governance_only = list_registrations(domain="governance", path=reg_path)
    analysis_only = list_registrations(domain="analysis", path=reg_path)
    persona_only = list_registrations(domain="persona", path=reg_path)
    capability_only = list_registrations(domain="capability", path=reg_path)
    assert len(memory_only) == 2
    assert len(governance_only) == 4
    assert len(analysis_only) == 7
    assert len(persona_only) == 4
    assert len(capability_only) == 4
    assert all(r.domain == "memory" for r in memory_only)
    assert all(r.domain == "governance" for r in governance_only)
    assert all(r.domain == "analysis" for r in analysis_only)
    assert all(r.domain == "persona" for r in persona_only)
    assert all(r.domain == "capability" for r in capability_only)


# ── CLI dispatch ──────────────────────────────────────────


def test_cli_list_subcommand_runs(tmp_path: Path) -> None:
    """`omo bos list --path <tmp>` 跑通, 输出表格."""
    reg_path = tmp_path / "bos-registry.json"
    register_seeds(path=reg_path)
    proc = subprocess.run(
        [
            sys.executable, "-m", "omo.cli", "bos", "list",
            "--path", str(reg_path),
        ],
        cwd="/Users/xiamingxing/Workspace/projects/omo",
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "bos://memory/kos/search" in proc.stdout
    assert "bos://governance/omo/audit" in proc.stdout
    assert "共 21 条" in proc.stdout


def test_cli_validate_subcommand() -> None:
    """`omo bos validate <uri>` 跑通, exit code 区分有效/无效."""
    # 有效
    p1 = subprocess.run(
        [sys.executable, "-m", "omo.cli", "bos", "validate",
         "bos://memory/kos/search"],
        cwd="/Users/xiamingxing/Workspace/projects/omo",
        capture_output=True, text=True, timeout=30,
    )
    assert p1.returncode == 0
    assert "OK" in p1.stdout
    # 无效
    p2 = subprocess.run(
        [sys.executable, "-m", "omo.cli", "bos", "validate",
         "bos://invalid/foo/bar"],
        cwd="/Users/xiamingxing/Workspace/projects/omo",
        capture_output=True, text=True, timeout=30,
    )
    assert p2.returncode == 1
    assert "FAIL" in p2.stdout


# ── 命名空间一致性 ──────────────────────────────────────


def test_default_registry_path_under_omo_knowledge() -> None:
    """默认注册表路径在 .omo/_knowledge/ 下 (P33-W1 战役 2 起步约定)."""
    assert ".omo" in str(DEFAULT_REGISTRY_PATH)
    assert "_knowledge" in str(DEFAULT_REGISTRY_PATH)
    assert str(DEFAULT_REGISTRY_PATH).endswith("bos-registry.json")


def test_bos_uri_pattern_matches_seeds() -> None:
    """BOS_URI_PATTERN 正则能匹配全部 SEED."""
    for s in SEED_REGISTRATIONS:
        m = BOS_URI_PATTERN.match(s.uri)
        assert m is not None, f"正则未匹配: {s.uri}"
        assert m.group("domain") == s.domain
        assert m.group("package") == s.package
        assert m.group("action") == s.action


# ── P33-W2 战役 2 余下 3 Domain 验证 ──────────────────────


def test_seeds_cover_5_domains() -> None:
    """W2 验证: SEED_REGISTRATIONS 覆盖 5 Domain (memory/governance/analysis/persona/capability)."""
    domains = {r.domain for r in SEED_REGISTRATIONS}
    assert domains == {"memory", "governance", "analysis", "persona", "capability"}
    # 每域至少 2 条 (除 capability 可少), 验证深度覆盖
    counts: dict[str, int] = {}
    for r in SEED_REGISTRATIONS:
        counts[r.domain] = counts.get(r.domain, 0) + 1
    assert counts["memory"] == 2
    assert counts["governance"] == 4
    assert counts["analysis"] == 7
    assert counts["persona"] == 4
    assert counts["capability"] == 4
    assert sum(counts.values()) == 21


def test_register_3_domains_persists(tmp_path: Path) -> None:
    """W2 验证: Analysis/Persona/Capability 3 Domain URI 注册到本地 JSON."""
    # 3 个新 Domain 各注册一条到 tmp 路径
    register_uri(
        uri="bos://analysis/minerva/research",
        endpoint="kairon.packages.minerva.research:run",
        description="W2 analysis test",
        path=tmp_path / "bos-registry.json",
    )
    register_uri(
        uri="bos://persona/sharedbrain-bridge/recall",
        endpoint="kairon.packages.sharedbrain_bridge.recall:recall",
        description="W2 persona test",
        path=tmp_path / "bos-registry.json",
    )
    register_uri(
        uri="bos://capability/forge/register-tool",
        endpoint="kairon.packages.forge.registry:register",
        description="W2 capability test",
        path=tmp_path / "bos-registry.json",
    )

    # 按 domain 过滤读回
    analysis = list_registrations(domain="analysis", path=tmp_path / "bos-registry.json")
    persona = list_registrations(domain="persona", path=tmp_path / "bos-registry.json")
    capability = list_registrations(domain="capability", path=tmp_path / "bos-registry.json")
    assert any(r.uri == "bos://analysis/minerva/research" for r in analysis)
    assert any(r.uri == "bos://persona/sharedbrain-bridge/recall" for r in persona)
    assert any(r.uri == "bos://capability/forge/register-tool" for r in capability)


def test_list_filter_by_each_domain(tmp_path: Path) -> None:
    """W2 验证: --domain filter 对 5 Domain 都生效, 全部 SEED 注册后验证."""
    reg_path = tmp_path / "bos-registry.json"
    register_seeds(path=reg_path)
    for d in ["memory", "governance", "analysis", "persona", "capability"]:
        regs = list_registrations(domain=d, path=reg_path)
        assert all(r.domain == d for r in regs), f"域 {d} 过滤不纯"
        assert len(regs) >= 1, f"域 {d} 应至少 1 条, 实得 {len(regs)}"
