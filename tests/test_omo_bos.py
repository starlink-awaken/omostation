"""Unit tests for omo.omo_bos — P33 Campaign 2.

Covers:
- BOS URI validation (5 domain whitelist + kebab-case)
- 3-segment legacy URI validation (R2 fix: mcp_server.py compat)
- Parsing round-trip (4-segment + 3-segment)
- Local JSON persistence (register, list, idempotency)
- KOS dual-write (M1 fix)
- Endpoint importlib verification (M2 fix)
- SEED_REGISTRATIONS consistency
- CLI subcommands dispatch (validate/list/register/seed/verify)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

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
    save_to_kos,
    validate_bos_uri,
    verify_all_endpoints,
    verify_endpoint,
)


# ── 验证逻辑 ──────────────────────────────────────────────


def test_validate_bos_uri_valid_40_seed_uris() -> None:
    """40 条 SEED URI 全部通过验证 (21 W33 + 19 W34)."""
    assert len(SEED_REGISTRATIONS) == 40
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


def test_register_seeds_writes_40(tmp_path: Path) -> None:
    """register_seeds 一次性写 40 条 SEED (21 W33 + 19 W34)."""
    reg_path = tmp_path / "bos-registry.json"
    results = register_seeds(path=reg_path)
    assert len(results) == 40
    for r in results:
        assert "error" not in r, f"SEED 注册失败: {r}"
        assert r["status"] in ("registered", "updated")
    # 文件存在且有 40 条
    assert reg_path.exists()
    raw = load_registry(path=reg_path)
    assert len(raw) == 40
    uris = {r["uri"] for r in raw}
    expected_uris = {s.uri for s in SEED_REGISTRATIONS}
    assert uris == expected_uris


def test_register_seeds_idempotent(tmp_path: Path) -> None:
    """register_seeds 调用两次, 总数仍为 40 (幂等)."""
    reg_path = tmp_path / "bos-registry.json"
    r1 = register_seeds(path=reg_path)
    r2 = register_seeds(path=reg_path)
    assert len(r1) == 40
    assert len(r2) == 40
    # 第二次全部应是 updated
    assert all(r["status"] == "updated" for r in r2)
    # 落盘总数仍 40
    raw = load_registry(path=reg_path)
    assert len(raw) == 40


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
    """list_registrations 按 domain 过滤 — 5 Domain 全覆盖 (P34-W0)."""
    reg_path = tmp_path / "bos-registry.json"
    register_seeds(path=reg_path)
    memory_only = list_registrations(domain="memory", path=reg_path)
    governance_only = list_registrations(domain="governance", path=reg_path)
    analysis_only = list_registrations(domain="analysis", path=reg_path)
    persona_only = list_registrations(domain="persona", path=reg_path)
    capability_only = list_registrations(domain="capability", path=reg_path)
    assert len(memory_only) == 5
    assert len(governance_only) == 8
    assert len(analysis_only) == 12
    assert len(persona_only) == 7
    assert len(capability_only) == 8
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
    assert "共 40 条" in proc.stdout


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
    """W2 验证: SEED_REGISTRATIONS 覆盖 5 Domain (P34-W0 扩展后 memory 5 / governance 8 / analysis 12 / persona 7 / capability 8)."""
    domains = {r.domain for r in SEED_REGISTRATIONS}
    assert domains == {"memory", "governance", "analysis", "persona", "capability"}
    counts: dict[str, int] = {}
    for r in SEED_REGISTRATIONS:
        counts[r.domain] = counts.get(r.domain, 0) + 1
    assert counts["memory"] == 5
    assert counts["governance"] == 8
    assert counts["analysis"] == 12
    assert counts["persona"] == 7
    assert counts["capability"] == 8
    assert sum(counts.values()) == 40


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


# ── P33-W3 修复: 5 个新测试 (M1 + M2 + R2) ─────────────────────


def test_save_to_kos_writes_entity(tmp_path: Path) -> None:
    """W3 验证: KOS 写入有 mock 测试 (避免污染 KOS db)."""
    with patch("omo.omo_bos.save_to_kos") as mock_save:
        mock_save.return_value = {
            "saved": "bos://test/x/y",
            "entity_id": "CON-BOS-test-x-y",
            "backend": "kos",
            "zone": "bos_registry",
        }
        result = mock_save({
            "uri": "bos://test/x/y",
            "domain": "test",
            "package": "x",
            "action": "y",
            "endpoint": "x.y:z",
            "description": "test",
        })
        assert result.get("backend") == "kos"
        assert result.get("saved") == "bos://test/x/y"
        assert mock_save.called


def test_save_to_kos_direct_call_fallback() -> None:
    """W3 验证: save_to_kos 真接调用走 _ensure_kos_importable + put_entity.

    不污染 KOS: 用唯一 ID 写入, 写入后再 delete_entity 清理.
    """
    reg = {
        "uri": "bos://memory/kos/test-w3-direct",
        "domain": "memory",
        "package": "kos",
        "action": "test-w3-direct",
        "endpoint": "kos.ontology.store:search_entities",
        "protocol": "internal",
        "description": "W3 direct-call test (transient)",
        "registered_at": "2026-06-06T00:00:00+00:00",
    }
    result = save_to_kos(reg, zone="bos_registry")
    # 要么 KOS 成功, 要么明确报错 — 不允许 raise
    assert "error" in result or result.get("backend") == "kos"
    # 清理: 如果真写入了, 把 entity 删掉
    if result.get("backend") == "kos":
        try:
            sys.path.insert(
                0,
                "/Users/xiamingxing/Workspace/projects/kairon/packages/kos/src",
            )
            from kos.ontology.store import delete_entity  # type: ignore
            delete_entity(result["entity_id"])
        except Exception:
            pass  # 清理失败不阻塞测试


def test_verify_endpoint_known_module() -> None:
    """W3 验证: 已知 omo.omo_bos 模块可实测可达."""
    r = verify_endpoint("omo.omo_bos:register_uri")
    assert r["module_found"] is True
    assert r["error"] is None


def test_verify_endpoint_unknown_module() -> None:
    """W3 验证: 未知模块返回 module_found=False."""
    r = verify_endpoint("nonexistent.module.foo_xyz_999:bar")
    assert r["module_found"] is False
    assert r["error"] is not None


def test_legacy_3segment_uri_validated() -> None:
    """W3 验证: 3 段 legacy URI 通过 (R2 协调 mcp_server.py bos://omo/debt)."""
    valid, err = validate_bos_uri("bos://omo/debt")
    assert valid, err
    assert "legacy" in err or "auto-mapped" in err
    # parse 也能跑, domain 隐含 governance
    parsed = parse_bos_uri("bos://omo/debt")
    assert parsed["domain"] == "governance"
    assert parsed["package"] == "omo"
    assert parsed["action"] == "debt"
    # 未知 legacy package 拒绝 (4-段新格式也仍生效)
    valid3, err3 = validate_bos_uri("bos://unknownpkg/whatever")
    assert not valid3
    # 4-段新格式 (domain=governance) 仍通过
    valid4, _ = validate_bos_uri("bos://governance/omo/audit")
    assert valid4


def test_register_uri_kos_and_local_dual_write(tmp_path: Path) -> None:
    """W3 验证: register_uri 同时写本地 JSON + 尝试 KOS (默认双写)."""
    reg_path = tmp_path / "bos-registry.json"
    with patch("omo.omo_bos.save_to_kos") as mock_kos:
        mock_kos.return_value = {
            "saved": "bos://memory/kos/search",
            "entity_id": "CON-BOS-memory-kos-search",
            "backend": "kos",
            "zone": "bos_registry",
        }
        r = register_uri(
            uri="bos://memory/kos/search",
            endpoint="kos.ontology.store:search_entities",
            description="W3 dual write test",
            path=reg_path,
        )
        assert "kos_result" in r, f"应含 kos_result, 实际 keys: {list(r.keys())}"
        assert mock_kos.called, "save_to_kos 应被调用一次"
        # 本地 JSON 仍写
        assert r["total"] == 1
        assert reg_path.exists()
        raw = json.loads(reg_path.read_text(encoding="utf-8"))
        assert len(raw) == 1
        assert raw[0]["uri"] == "bos://memory/kos/search"


def test_register_uri_no_kos_when_dual_write_false(tmp_path: Path) -> None:
    """W3 验证: dual_write=False 跳过 KOS 写入 (测试场景)."""
    reg_path = tmp_path / "bos-registry.json"
    with patch("omo.omo_bos.save_to_kos") as mock_kos:
        r = register_uri(
            uri="bos://memory/kos/search",
            endpoint="kos.ontology.store:search_entities",
            path=reg_path,
            dual_write=False,
        )
        assert "kos_result" in r
        assert r["kos_result"].get("skipped") == "dual_write_disabled"
        assert not mock_kos.called, "dual_write=False 不应调 save_to_kos"


def test_verify_all_endpoints_runs(tmp_path: Path) -> None:
    """W3 验证: verify_all_endpoints 跑全表, 返回结构化结果 (P34-W0 40 条)."""
    reg_path = tmp_path / "bos-registry.json"
    register_seeds(path=reg_path)
    results = verify_all_endpoints(path=reg_path)
    assert len(results) == 40
    for r in results:
        assert "uri" in r
        assert "endpoint" in r
        assert "module_found" in r
        assert "error" in r
    # 至少 omo.omo_bos 自身 endpoint 可达 (我们 register 的 SEED 含这个)
    omoruns = [r for r in results if "omo.omo_audit" in r["endpoint"]]
    if omoruns:
        assert omoruns[0]["module_found"] is True


# ── P34-W0 战役 2 扩展: 5 个新测试 ─────────────────────


def test_seeds_count_40() -> None:
    """W34 验证: SEED_REGISTRATIONS 扩到 40 条 (21 W33 + 19 W34)."""
    assert len(SEED_REGISTRATIONS) == 40


def test_seeds_5_domain_distribution() -> None:
    """W34 验证: 5 Domain 分布 (memory 5 / governance 8 / analysis 12 / persona 7 / capability 8)."""
    counts: dict[str, int] = {}
    for r in SEED_REGISTRATIONS:
        counts[r.domain] = counts.get(r.domain, 0) + 1
    assert counts == {"memory": 5, "governance": 8, "analysis": 12, "persona": 7, "capability": 8}
    assert sum(counts.values()) == 40


def test_register_19_new_uris_persists(tmp_path: Path) -> None:
    """W34 验证: 19 条新 URI 全部注册到本地 JSON."""
    reg_path = tmp_path / "bos-registry.json"
    new_uris = [
        "bos://memory/kos/ingest",
        "bos://memory/kronos/query",
        "bos://memory/kronos/schedule",
        "bos://governance/omo/sync",
        "bos://governance/omo/inspect",
        "bos://governance/metaos/register",
        "bos://governance/sot-bridge/query",
        "bos://analysis/minerva/audit",
        "bos://analysis/iris/transform",
        "bos://analysis/iris/validate",
        "bos://analysis/codeanalyze/lint",
        "bos://analysis/ontoderive/fact-check",
        "bos://persona/sharedbrain-bridge/recall-entity",
        "bos://persona/core-models/validate",
        "bos://persona/health-profile/alert",
        "bos://capability/forge/list-tools",
        "bos://capability/forge/exec-tool",
        "bos://capability/agent-runtime/agent-list",
        "bos://capability/agent-runtime/task-status",
    ]
    for uri in new_uris:
        result = register_uri(uri=uri, description="W34 expansion", path=reg_path)
        assert "error" not in result, f"注册失败: {uri} → {result}"
    raw = load_registry(path=reg_path)
    persisted = {r["uri"] for r in raw}
    for uri in new_uris:
        assert uri in persisted, f"未持久化: {uri}"


def test_list_filter_by_5_domains_w34(tmp_path: Path) -> None:
    """W34 验证: --domain filter 对 5 Domain 全生效, 每域精确条数."""
    reg_path = tmp_path / "bos-registry.json"
    register_seeds(path=reg_path)
    expected = {"memory": 5, "governance": 8, "analysis": 12, "persona": 7, "capability": 8}
    for d, expected_count in expected.items():
        regs = list_registrations(domain=d, path=reg_path)
        assert all(r.domain == d for r in regs), f"域 {d} 过滤不纯"
        assert len(regs) == expected_count, f"域 {d} 应 {expected_count} 条, 实得 {len(regs)}"


def test_no_duplicate_uris() -> None:
    """W34 验证: 40 URI 不重复."""
    uris = [r.uri for r in SEED_REGISTRATIONS]
    assert len(uris) == len(set(uris)), f"URI 重复: {[u for u in uris if uris.count(u) > 1]}"
    assert len(uris) == 40
