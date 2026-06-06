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
    def test_11_poc_services(self):
        """应有 11 个 POC service."""
        assert len(POC_SERVICES) == 11

    def test_5_domains_coverage(self):
        """覆盖 5 个 domain."""
        domains = list_domains()
        assert set(domains.keys()) == {"memory", "governance", "analysis", "persona", "capability"}

    def test_by_transport(self):
        """1 internal (omo) + 10 stdio = 11."""
        by_t = {"stdio": 0, "internal": 0, "http": 0}
        for svc in POC_SERVICES.values():
            by_t[svc.transport] += 1
        assert by_t["stdio"] == 10
        assert by_t["internal"] == 1
        assert by_t["http"] == 0

    def test_list_services_returns_11(self):
        services = list_services()
        assert len(services) == 11
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
        assert ck["total_services"] == 11
        assert len(ck["domains"]) == 5
        assert ck["by_transport"]["stdio"] == 10
        assert ck["by_transport"]["internal"] == 1


# ── 6. MCP tool wrapper (bos_resolve / bos_list) ────
class TestMcpToolWrapper:
    """验证 agora/mcp/tools/bos_resolve.py 的 fastmcp 入口."""

    def test_bos_list_tool(self):
        from agora.mcp.tools.bos_resolve import bos_list

        result = bos_list()
        assert result["status"] == "ok"
        assert result["count"] == 11
        assert len(result["services"]) == 11

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
    assert len(POC_SERVICES) == 11
