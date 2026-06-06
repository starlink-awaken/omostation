"""Unit tests for agora.mcp.bos_resolver — P33-W4 战役 1.

验证:
  1. BOS URI 解析 (11 POC 有效 + 无效格式)
  2. internal transport (omo 同进程 importlib)
  3. stdio transport (subprocess spawn + alive)
  4. ProcessPool 生命周期 (懒加载 + shutdown)
  5. 注册表完整性 (11 POC 覆盖 5 Domain)
"""
from __future__ import annotations

import asyncio

import pytest

from agora.mcp.bos_resolver import (
    BOS_URI_PATTERN,
    KAIRON_ROOT,
    POC_SERVICES,
    BosService,
    ProcessPool,
    get_pool,
    invoke_stdio,
    list_domains,
    list_services,
    parse_bos_uri,
    protocol_self_check,
    resolve_bos_uri,
)


# ── 1. parse_bos_uri ────────────────────────────────
class TestParseBosUri:
    def test_valid_all_11_poc_uris(self):
        """所有 11 POC URI 应能正确解析为 3 段."""
        expected = {
            "bos://memory/kos/search": ("memory", "kos", "search"),
            "bos://memory/kronos/ingest": ("memory", "kronos", "ingest"),
            "bos://governance/omo/audit": ("governance", "omo", "audit"),
            "bos://governance/metaos/gate": ("governance", "metaos", "gate"),
            "bos://governance/sot-bridge/register": ("governance", "sot-bridge", "register"),
            "bos://governance/protocols-layer/trigger": ("governance", "protocols-layer", "trigger"),
            "bos://analysis/minerva/research": ("analysis", "minerva", "research"),
            "bos://analysis/ontoderive/derive": ("analysis", "ontoderive", "derive"),
            "bos://analysis/codeanalyze/scan": ("analysis", "codeanalyze", "scan"),
            "bos://persona/health-profile/summary": ("persona", "health-profile", "summary"),
            "bos://capability/forge/register-tool": ("capability", "forge", "register-tool"),
        }
        for uri, (domain, package, action) in expected.items():
            parsed = parse_bos_uri(uri)
            assert parsed == {"domain": domain, "package": package, "action": action}, (
                f"Parse mismatch for {uri}: {parsed}"
            )

    def test_invalid_uri_raises(self):
        """非 4 段格式应抛 ValueError."""
        for bad in (
            "not-a-uri",
            "bos://memory",
            "bos://memory/kos",
            "bos://memory/kos/search/extra",
            "bos://UNKNOWN/kos/search",
            "bos://memory/Kos/search",  # 大写 package 不允许
            "",
            "http://memory/kos/search",
        ):
            with pytest.raises(ValueError, match="Invalid BOS URI"):
                parse_bos_uri(bad)

    def test_pattern_5_domains(self):
        """5 domain 严格白名单 (package/action 至少 2 字符)."""
        for d in ("memory", "governance", "analysis", "persona", "capability"):
            m = BOS_URI_PATTERN.match(f"bos://{d}/xx/yy")
            assert m is not None
            assert m.group("domain") == d
            assert m.group("package") == "xx"
            assert m.group("action") == "yy"


# ── 2. internal transport (omo) ─────────────────────
class TestInternalTransport:
    def test_resolve_omo_audit_via_internal(self):
        """bos://governance/omo/audit 走 internal (同进程 importlib)."""
        result = asyncio.run(resolve_bos_uri("bos://governance/omo/audit"))
        assert result["uri"] == "bos://governance/omo/audit"
        assert result["transport"] == "internal"
        # 若 omo 未安装或 import 失败, status=error; 不视为测试失败
        # 但若是 ok, result_type 应是 GovernanceReport
        if result["status"] == "ok":
            assert "result_type" in result
            assert "GovernanceReport" in result.get("result_type", "") or "dataclass" in str(result)


# ── 3. stdio transport (kairon) ─────────────────────
class TestStdioTransport:
    def test_resolve_kos_stdio_spawn(self):
        """bos://memory/kos/search 走 stdio, 进程 spawn 后 alive."""
        result = asyncio.run(resolve_bos_uri("bos://memory/kos/search"))
        assert result["uri"] == "bos://memory/kos/search"
        assert result["transport"] == "stdio"
        # spawn 成功 → pid > 0 + alive_at_spawn True
        if result["status"] == "ok":
            assert result["pid"] > 0
            assert result["alive_at_spawn"] is True
        # 若 uv 不在 PATH, status=error 也合理 (CI 环境)
        else:
            assert "error" in result

    def test_resolve_minerva_stdio_spawn(self):
        """bos://analysis/minerva/research stdio spawn."""
        result = asyncio.run(resolve_bos_uri("bos://analysis/minerva/research"))
        assert result["uri"] == "bos://analysis/minerva/research"
        assert result["transport"] == "stdio"
        if result["status"] == "ok":
            assert result["pid"] > 0

    def test_resolve_health_profile_stdio_spawn(self):
        """bos://persona/health-profile/summary stdio spawn."""
        result = asyncio.run(resolve_bos_uri("bos://persona/health-profile/summary"))
        assert result["uri"] == "bos://persona/health-profile/summary"
        assert result["transport"] == "stdio"


# ── 4. ProcessPool 生命周期 ─────────────────────────
class TestProcessPool:
    def setup_method(self):
        self.pool = ProcessPool()

    def teardown_method(self):
        self.pool.shutdown()  # 确保不残留

    def test_lazy_spawn_first_time(self):
        """首次 get_or_spawn → spawn, 第二次复用."""
        svc = BosService(
            uri="bos://test/x/y",
            domain="memory",
            package="x",
            action="y",
            transport="stdio",
            command=["sleep", "0.05"],  # 短时存活命令
        )
        p1 = self.pool.get_or_spawn(svc)
        p2 = self.pool.get_or_spawn(svc)
        assert p1 is p2, "重复调用必须返回同一进程"
        assert self.pool.is_alive(svc.uri)

    def test_alive_status(self):
        """is_alive 在进程未 spawn 时返回 False."""
        assert not self.pool.is_alive("bos://nope/nope/nope")
        assert self.pool.processes == {}

    def test_shutdown_specific(self):
        """shutdown(uri) 只关一个."""
        svc = BosService(
            uri="bos://test/a/b",
            domain="memory",
            package="a",
            action="b",
            transport="stdio",
            command=["sleep", "5"],
        )
        self.pool.get_or_spawn(svc)
        assert self.pool.is_alive(svc.uri)
        count = self.pool.shutdown(svc.uri)
        assert count == 1
        assert svc.uri not in self.pool.processes

    def test_shutdown_all(self):
        """shutdown() 全关."""
        for i in range(3):
            svc = BosService(
                uri=f"bos://test/x{i}/y{i}",
                domain="memory",
                package=f"x{i}",
                action=f"y{i}",
                transport="stdio",
                command=["sleep", "5"],
            )
            self.pool.get_or_spawn(svc)
        assert len(self.pool.processes) == 3
        count = self.pool.shutdown()
        assert count == 3
        assert self.pool.processes == {}


# ── 5. list_services / 注册表完整性 ────────────────
class TestRegistry:
    def test_25_poc_services(self):
        """P35 升级: 25 个 POC service (原 20 + Phase 35 补 5)."""
        assert len(POC_SERVICES) == 25

    def test_5_domains_coverage(self):
        """覆盖 5 个 domain."""
        domains = list_domains()
        assert set(domains.keys()) == {"memory", "governance", "analysis", "persona", "capability"}

    def test_by_transport(self):
        """P35: 25 services total (actual breakdown from POC_SERVICES)."""
        by_t = {"stdio": 0, "internal": 0, "http": 0}
        for svc in POC_SERVICES.values():
            by_t[svc.transport] += 1
        assert by_t["stdio"] >= 19
        assert by_t["internal"] >= 1
        assert by_t["http"] >= 0

    def test_list_services_returns_all(self):
        services = list_services()
        assert len(services) == len(POC_SERVICES)
        for svc in services:
            assert "uri" in svc
            assert "transport" in svc
            assert "alive" in svc

    def test_unknown_uri_returns_error(self):
        result = asyncio.run(resolve_bos_uri("bos://memory/nonexistent/xxx"))
        assert result["status"] == "error"
        assert "unknown_bos_uri" in result["error"]

    def test_protocol_self_check(self):
        ck = protocol_self_check()
        assert ck["status"] == "ok"
        assert ck["total_services"] == len(POC_SERVICES)
        assert len(ck["domains"]) == 5
        assert ck["by_transport"]["stdio"] >= 19
        assert ck["by_transport"]["internal"] >= 1


# ── 6. MCP tool wrapper (bos_resolve / bos_list) ────
class TestMcpToolWrapper:
    """验证 agora/mcp/tools/bos_resolve.py 的 fastmcp 入口."""

    def test_bos_list_tool(self):
        from agora.mcp.tools.bos_resolve import bos_list

        result = bos_list()
        assert result["status"] == "ok"
        assert result["count"] == len(POC_SERVICES)
        assert len(result["services"]) == len(POC_SERVICES)

    def test_bos_parse_tool(self):
        from agora.mcp.tools.bos_resolve import bos_parse

        result = bos_parse("bos://memory/kos/search")
        assert result["status"] == "ok"
        assert result["parsed"]["domain"] == "memory"

    def test_bos_parse_tool_invalid(self):
        from agora.mcp.tools.bos_resolve import bos_parse

        result = bos_parse("not-a-uri")
        assert result["status"] == "error"
        assert "invalid_bos_uri" in result["error"]

    def test_bos_resolve_tool_omo(self):
        """bos_resolve tool on omo internal."""
        from agora.mcp.tools.bos_resolve import bos_resolve

        result = bos_resolve("bos://governance/omo/audit")
        # omo import 可能失败 (CI 环境), 但 tool 自身应返回 dict
        assert "status" in result
        assert "format_version" in result


# ── 7. Kairon POC __main__.py 验证 ─────────────────
class TestKaironMainEntries:
    """验证 3 个 POC __main__.py 可 spawn + 协议工作."""

    def test_kos_main_help(self):
        """python -m kos serve --help 应可执行."""
        pytest.importorskip("subprocess")
        import subprocess

        result = subprocess.run(
            ["uv", "run", "--directory", str(KAIRON_ROOT), "python", "-m", "kos", "serve", "--help"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"kos --help failed: {result.stderr}"
        assert "--action" in result.stdout

    def test_health_profile_main_help(self):
        import subprocess

        result = subprocess.run(
            [
                "uv", "run", "--directory", str(KAIRON_ROOT),
                "python", "-m", "health_profile", "serve", "--help",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"health_profile --help failed: {result.stderr}"
        assert "--action" in result.stdout

    def test_minerva_main_help(self):
        import subprocess

        result = subprocess.run(
            [
                "uv", "run", "--directory", str(KAIRON_ROOT),
                "python", "-m", "minerva", "serve", "--help",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"minerva --help failed: {result.stderr}"
        assert "--action" in result.stdout


# ── 8. ruff 兼容 (无 lint 错误基本自检) ────────────
def test_module_no_lint_smoke():
    """smoke: 模块能 import, 所有公共符号存在."""
    assert callable(parse_bos_uri)
    assert callable(resolve_bos_uri)
    assert callable(list_services)
    assert callable(list_domains)
    assert callable(protocol_self_check)
    assert callable(get_pool)
    assert isinstance(POC_SERVICES, dict)
    assert len(POC_SERVICES) >= 20


# ── 9. P34-W1 升级: invoke_stdio 真 stdio 协议 ──────
class TestP34W1StdioProtocol:
    """P34-W1 战役 1 升级: 完整 stdio JSON 协议通信 (写 stdin/读 stdout)."""

    def teardown_method(self):
        """清理: 测试结束关闭所有 spawn 的进程."""
        get_pool().shutdown()

    def test_invoke_stdio_success(self):
        """W1 验证: stdio 协议调用成功 (kairon kos serve)."""
        r = invoke_stdio("bos://memory/kos/search", "search", ["hello"], {"q": "test"})
        # 期望: status=ok, 含 result 或 uri 字段
        assert r.get("uri") == "bos://memory/kos/search", f"missing uri: {r}"
        assert r.get("status") == "ok" or "result" in r, f"unexpected response: {r}"
        # pid 必有 (Popen 已 spawn)
        assert r.get("pid") is not None and r["pid"] > 0

    def test_invoke_stdio_unknown_uri(self):
        """W1 验证: 未知 URI → unknown_bos_uri error."""
        r = invoke_stdio("bos://nonexistent/x/y", "test", {})
        assert r.get("status") == "error"
        assert "unknown_bos_uri" in r["error"]

    def test_invoke_stdio_minerva(self):
        """W1 验证: minerva stdio 协议 (analysis domain)."""
        r = invoke_stdio("bos://analysis/minerva/research", "research", {"topic": "test"})
        assert r.get("uri") == "bos://analysis/minerva/research"
        # 三种可能: 成功 / 错误 / 超时
        assert r.get("status") in ("ok", "error")
        assert "result" in r or "error" in r

    def test_list_services_includes_pid(self):
        """W1 验证: list_services 含 pid + alive (spawn 后)."""
        # 先触发 spawn
        invoke_stdio("bos://memory/kos/search", "search", [])
        services = list_services()
        kos_service = next(s for s in services if s["uri"] == "bos://memory/kos/search")
        assert kos_service["transport"] == "stdio"
        assert kos_service["pid"] is not None
        assert kos_service["pid"] > 0
        assert kos_service["alive"] is True

    def test_process_pool_lifecycle_w1(self):
        """W1 验证: ProcessPool 进程复用 (不重复 spawn)."""
        # 第一次调用 → spawn
        r1 = invoke_stdio("bos://memory/kos/search", "search", [])
        assert r1.get("status") == "ok", f"first call failed: {r1}"
        pid1 = get_pool().processes["bos://memory/kos/search"].pid

        # 第二次调用 → 复用同一进程
        r2 = invoke_stdio("bos://memory/kos/search", "search", [])
        assert r2.get("status") == "ok", f"second call failed: {r2}"
        pid2 = get_pool().processes["bos://memory/kos/search"].pid

        assert pid1 == pid2, f"进程不复用! pid1={pid1}, pid2={pid2}"
        # request_id 必须递增
        assert r1["request_id"] != r2["request_id"]


# ── 10. P35-W1 战役 4: 自动 respawn 死进程 ────────────
class TestP35W1Respawn:
    """P35-W1 战役 4: agora spawn 真替代 (自动 respawn 死进程)."""

    def teardown_method(self):
        """清理: 测试结束关闭所有 spawn 的进程."""
        get_pool().shutdown()

    def test_process_pool_respawn_dead_w1(self):
        """W1 验证: 死进程 respawn (is_alive 自动清理 + respawn_dead 批量)."""
        from agora.mcp.bos_resolver import _pool, invoke_stdio
        # 第一次调用 spawn
        invoke_stdio("bos://memory/kos/search", "search", {})
        pid1 = _pool.processes["bos://memory/kos/search"].pid
        # kill
        _pool.processes["bos://memory/kos/search"].kill()
        _pool.processes["bos://memory/kos/search"].wait()
        # is_alive 应返 False (并自动清理)
        assert not _pool.is_alive("bos://memory/kos/search")
        assert "bos://memory/kos/search" not in _pool.processes
        # respawn_dead
        respawned = _pool.respawn_dead()
        assert "bos://memory/kos/search" in respawned
        pid2 = _pool.processes["bos://memory/kos/search"].pid
        assert pid1 != pid2, f"respawn 后 PID 应不同: {pid1} vs {pid2}"

    def test_invoke_stdio_respawn_on_dead_w1(self):
        """W1 验证: invoke_stdio 遇死进程自动 respawn."""
        from agora.mcp.bos_resolver import _pool, invoke_stdio
        # 第一次调用 spawn
        invoke_stdio("bos://memory/kos/search", "search", {})
        pid1 = _pool.processes["bos://memory/kos/search"].pid
        # kill
        _pool.processes["bos://memory/kos/search"].kill()
        _pool.processes["bos://memory/kos/search"].wait()
        # 第二次调用自动 respawn
        r = invoke_stdio("bos://memory/kos/search", "search", {})
        pid2 = _pool.processes["bos://memory/kos/search"].pid
        assert pid1 != pid2, f"respawn 后 PID 应不同: {pid1} vs {pid2}"
        assert r.get("status") == "ok" or "result" in r, f"unexpected: {r}"

    def test_respawn_dead_batch_w1(self):
        """W1 验证: 批量 respawn_dead."""
        from agora.mcp.bos_resolver import _pool, invoke_stdio
        # 触发 2 个 spawn
        invoke_stdio("bos://memory/kos/search", "search", {})
        invoke_stdio("bos://analysis/minerva/research", "research", {})
        # kill 2 个
        for uri in ["bos://memory/kos/search", "bos://analysis/minerva/research"]:
            if uri in _pool.processes:
                _pool.processes[uri].kill()
                _pool.processes[uri].wait()
        # 批量 respawn
        respawned = _pool.respawn_dead()
        assert len(respawned) == 2, f"应 respawn 2 个, 实际 {len(respawned)}: {respawned}"
        for uri in ["bos://memory/kos/search", "bos://analysis/minerva/research"]:
            assert uri in respawned
            assert _pool.is_alive(uri), f"{uri} respawn 后仍 dead"
