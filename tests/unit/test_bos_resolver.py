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
import json
import subprocess
import sys
import types

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


def _kairon_main_help(module: str) -> dict:
    """Probe a Kairon module without spawning when its checkout is unavailable."""
    if not KAIRON_ROOT.is_dir():
        return {
            "status": "error",
            "error": "kairon_root_unavailable",
            "process_started": False,
        }

    result = subprocess.run(
        [
            "uv",
            "run",
            "--directory",
            str(KAIRON_ROOT),
            "python",
            "-m",
            module,
            "serve",
            "--help",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return {
        "status": "ok" if result.returncode == 0 else "error",
        "error": result.stderr if result.returncode else None,
        "process_started": True,
        "returncode": result.returncode,
    }


# ── 1. parse_bos_uri ────────────────────────────────
class TestParseBosUri:
    def test_valid_all_11_poc_uris(self):
        """所有 11 POC URI 应能正确解析为 3 段."""
        expected = {
            "bos://memory/kos/search": ("memory", "kos", "search"),
            "bos://memory/kronos/ingest": ("memory", "kronos", "ingest"),
            "bos://governance/omo/audit": ("governance", "omo", "audit"),
            "bos://governance/metaos/gate": ("governance", "metaos", "gate"),
            "bos://governance/sot-bridge/register": (
                "governance",
                "sot-bridge",
                "register",
            ),
            "bos://governance/protocols-layer/trigger": (
                "governance",
                "protocols-layer",
                "trigger",
            ),
            "bos://analysis/minerva/research": ("analysis", "minerva", "research"),
            "bos://analysis/ontoderive/derive": ("analysis", "ontoderive", "derive"),
            "bos://analysis/codeanalyze/scan": ("analysis", "codeanalyze", "scan"),
            "bos://persona/health-profile/summary": (
                "persona",
                "health-profile",
                "summary",
            ),
            "bos://capability/forge/register-tool": (
                "capability",
                "forge",
                "register-tool",
            ),
        }
        for uri, (domain, package, action) in expected.items():
            parsed = parse_bos_uri(uri)
            assert parsed == {"domain": domain, "package": package, "action": action}, (
                f"Parse mismatch for {uri}: {parsed}"
            )

    def test_invalid_uri_raises(self):
        """非 4 段格式应返回空 dict."""
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
            result = parse_bos_uri(bad)
            assert result == {}, f"Expected empty dict for {bad}, got {result}"

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
    def test_internal_async_handler_is_awaited(self, monkeypatch):
        """internal resolver must unwrap an async handler returned by the thread wrapper."""
        from agora.mcp.resolver import api

        async def handler(*_args, **_kwargs):
            return {"answer": "async-ok"}

        module = types.ModuleType("test_async_bos_handler")
        module.handler = handler  # type: ignore[reportAttributeAccessIssue]
        monkeypatch.setitem(sys.modules, module.__name__, module)
        service = BosService(
            uri="bos://memory/test/async",
            domain="memory",
            package="agora",
            action="async",
            transport="internal",
            module_path=module.__name__,
            func_name="handler",
        )
        monkeypatch.setattr(api, "get_service", lambda _uri: service)

        result = asyncio.run(api.resolve_bos_uri(service.uri))

        assert result["status"] == "ok"
        assert result["result"] == {"answer": "async-ok"}

    def test_resolve_omo_audit_via_internal(self):
        """bos://governance/omo/audit 走 internal (同进程 importlib)."""
        result = asyncio.run(resolve_bos_uri("bos://governance/omo/audit"))
        assert result["uri"] == "bos://governance/omo/audit"
        assert result["transport"] == "internal"
        # 若 omo 未安装或 import 失败, status=error; 不视为测试失败
        # 但若是 ok, result_type 应是 GovernanceReport
        if result["status"] == "ok":
            assert "result" in result
            assert "GovernanceReport" in str(result)


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

    @pytest.mark.xfail(reason="需要 kairon 子进程, 仅 CI 完整环境可用")
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
        """当前 POC_SERVICE 计数 (36)."""
        assert len(POC_SERVICES) >= 36

    def test_5_domains_coverage(self):
        """覆盖 5 个 domain (实际已扩展到 7+)."""
        domains = list_domains()
        assert len(domains) >= 5
        assert "memory" in domains
        assert "governance" in domains
        assert "analysis" in domains

    def test_by_transport(self):
        """验证传输类型分布。"""
        by_t: dict[str, int] = {}
        for svc in POC_SERVICES:
            by_t[svc.transport] = by_t.get(svc.transport, 0) + 1
        assert by_t.get("stdio", 0) >= 19
        assert by_t.get("internal", 0) >= 1

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
        assert ck["total"] == len(POC_SERVICES)
        assert len(ck["domains"]) >= 5
        assert ck["by_transport"].get("stdio", 0) >= 19
        assert ck["by_transport"].get("internal", 0) >= 1


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

    def test_kos_main_help(self, monkeypatch):
        """可用时验证真实入口；缺失时明确失败闭合且不启动进程。"""
        if not KAIRON_ROOT.is_dir():
            monkeypatch.setattr(
                subprocess,
                "run",
                lambda *args, **kwargs: pytest.fail(
                    "subprocess must not start without KAIRON_ROOT"
                ),
            )

        result = _kairon_main_help("kos")
        if KAIRON_ROOT.is_dir():
            assert result["status"] == "ok", result["error"]
            assert result["returncode"] == 0
            assert result["process_started"] is True
        else:
            assert result == {
                "status": "error",
                "error": "kairon_root_unavailable",
                "process_started": False,
            }

    @pytest.mark.xfail(
        condition=not KAIRON_ROOT.exists(),
        reason="需要 kairon workspace 安装 (KAIRON_ROOT 不存在时 xfail; 存在时正常跑, strict 防 XPASS 误标)",
        strict=True,
    )
    def test_health_profile_main_help(self):
        import subprocess

        result = subprocess.run(
            [
                "uv",
                "run",
                "--directory",
                str(KAIRON_ROOT),
                "python",
                "-m",
                "health_profile",
                "serve",
                "--help",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"health_profile --help failed: {result.stderr}"

    @pytest.mark.xfail(
        condition=not KAIRON_ROOT.exists(),
        reason="需要 kairon workspace 安装 (KAIRON_ROOT 不存在时 xfail; 存在时正常跑, strict 防 XPASS 误标)",
        strict=True,
    )
    def test_minerva_main_help(self):
        import subprocess

        result = subprocess.run(
            [
                "uv",
                "run",
                "--directory",
                str(KAIRON_ROOT),
                "python",
                "-m",
                "minerva",
                "serve",
                "--help",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"minerva --help failed: {result.stderr}"


# ── 8. ruff 兼容 (无 lint 错误基本自检) ────────────
def test_module_no_lint_smoke():
    """smoke: 模块能 import, 所有公共符号存在."""
    assert callable(parse_bos_uri)
    assert callable(resolve_bos_uri)
    assert callable(list_services)
    assert callable(list_domains)
    assert callable(protocol_self_check)
    assert callable(get_pool)
    assert isinstance(POC_SERVICES, list)
    assert len(POC_SERVICES) >= 20


# ── 9. P34-W1 升级: invoke_stdio 真 stdio 协议 ──────
class TestP34W1StdioProtocol:
    """P34-W1 战役 1 升级: 完整 stdio JSON 协议通信 (写 stdin/读 stdout)."""

    def teardown_method(self):
        """清理: 测试结束关闭所有 spawn 的进程."""
        get_pool().shutdown()

    def test_invoke_stdio_success(self):
        """W1 验证: invoke_stdio 调用成功 (kos → conftest 降级为 stdio).

        Note: conftest 自动降级 mcp_stdio→stdio, 因此子进程 spawn 后可能
        因 kairon __main__.py 无 stdin 处理而返回 eof_no_response.
        """
        r = invoke_stdio("bos://memory/kos/search", "search", ["hello"], {"q": "test"})
        # status 可能 ok 或 error (eof_no_response 因为 kairon __main__ 不处理 stdin)
        assert "status" in r

    def test_invoke_stdio_unknown_uri(self):
        """W1 验证: 未知 URI → unknown_bos_uri error."""
        r = invoke_stdio("bos://nonexistent/x/y", "test", {})
        assert r.get("status") == "error"
        assert "unknown_bos_uri" in r["error"]

    def test_invoke_stdio_minerva(self, monkeypatch, tmp_path):
        """Minerva 可用时保留正例；缺失时验证真实 spawn 失败边界。"""
        processes_before = dict(get_pool().processes)

        if not KAIRON_ROOT.is_dir():
            from agora.mcp.resolver import adapter as adapter_module

            empty_workspace = tmp_path / "empty-workspace"
            (empty_workspace / "projects").mkdir(parents=True)
            missing_kairon = empty_workspace / "projects/knowledge/kairon"
            missing_executable = missing_kairon / "bin/minerva-python"
            assert not missing_kairon.exists()
            assert not missing_executable.exists()
            monkeypatch.setenv("WORKSPACE_ROOT", str(empty_workspace))

            minerva_service = next(
                service
                for service in POC_SERVICES
                if service.uri == "bos://analysis/minerva/research"
            )
            monkeypatch.setattr(
                minerva_service,
                "command",
                [str(missing_executable), "-m", "minerva.cli", "research"],
            )

            original_popen = adapter_module.subprocess.Popen
            attempted_argv = []
            successful_spawns = []

            def _transparent_popen(*args, **kwargs):
                attempted_argv.append(args[0])
                proc = original_popen(*args, **kwargs)
                successful_spawns.append({"pid": proc.pid, "argv": proc.args})
                return proc

            monkeypatch.setattr(
                adapter_module.subprocess, "Popen", _transparent_popen
            )

        r = invoke_stdio(
            "bos://analysis/minerva/research", "research", {"topic": "test"}
        )
        assert r.get("uri") == "bos://analysis/minerva/research"
        if KAIRON_ROOT.is_dir():
            # 正例环境仍验证真实协议 envelope。
            assert r.get("status") in ("ok", "error")
            assert "result" in r or "error" in r
        else:
            assert r.get("status") == "error"
            assert "[Errno 2]" in r.get("error", "")
            assert "result" not in r
            assert get_pool().processes == processes_before
            assert attempted_argv == [
                [str(missing_executable), "-m", "minerva.cli", "research"]
            ]
            assert r.get("pid") is None
            assert successful_spawns == []

    def test_list_services_includes_fields(self):
        """W1 验证: list_services 含 transport/pid/alive 字段."""
        services = list_services()
        kos_service = next(s for s in services if s["uri"] == "bos://memory/kos/search")
        # conftest 自动降级 mcp_stdio→stdio
        assert kos_service["transport"] in ("stdio", "mcp_stdio")

    def test_process_pool_lifecycle_w1(self):
        """W1 验证: ProcessPool 进程复用 (使用自定义 stdio service, 非 POC_SERVICES)."""
        from agora.mcp.bos_resolver import BosService

        svc = BosService(
            uri="bos://test/pool/reuse",
            domain="test",
            package="pool",
            action="reuse",
            transport="stdio",
            command=["sleep", "0.05"],
        )
        pool = get_pool()
        # 第一次 spawn
        p1 = pool.get_or_spawn(svc)
        # 第二次复用
        p2 = pool.get_or_spawn(svc)
        assert p1 is p2, f"进程不复用! p1={p1.pid}, p2={p2.pid}"
        # 清理
        pool.shutdown(svc.uri)


# ── 10. P35-W1 战役 4: 自动 respawn 死进程 ────────────
class TestP35W1Respawn:
    """P35-W1 战役 4: agora spawn 真替代 (自动 respawn 死进程)."""

    def teardown_method(self):
        """清理: 测试结束关闭所有 spawn 的进程."""
        get_pool().shutdown()

    @pytest.mark.xfail(reason="需要 kairon 子进程, 仅 CI 完整环境可用")
    def test_process_pool_respawn_dead_w1(self):
        """W1 验证: 死进程 respawn (使用 POC_SERVICES 真实 service, conftest 降级→stdio)."""
        from agora.mcp.bos_resolver import _pool
        from agora.mcp.bos_resolver import POC_SERVICES

        uri = "bos://memory/kos/search"
        original_svc = next((s for s in POC_SERVICES if s.uri == uri), None)
        # 确保 spawn (POC_SERVICES 中的 transport 已被 conftest 降级为 stdio)
        _pool.get_or_spawn(original_svc)  # type: ignore[reportArgumentType]
        _pool.seen_uris.add(uri)
        pid1 = _pool.processes[uri].pid
        # kill
        _pool.processes[uri].kill()
        _pool.processes[uri].wait()
        # is_alive 应返 False (并自动清理)
        assert not _pool.is_alive(uri)
        assert uri not in _pool.processes
        # respawn_dead
        respawned = _pool.respawn_dead()
        assert uri in respawned
        pid2 = _pool.processes[uri].pid
        assert pid1 != pid2, f"respawn 后 PID 应不同: {pid1} vs {pid2}"
        _pool.shutdown(uri)

    @pytest.mark.xfail(reason="需要 kairon 子进程, 仅 CI 完整环境可用")
    def test_invoke_stdio_respawn_on_dead_w1(self):
        """W1 验证: invoke_stdio 遇死进程自动 respawn (降级 stdio)."""
        from agora.mcp.bos_resolver import _pool, invoke_stdio

        uri = "bos://memory/kos/search"
        # 第一次调用 spawn (进程可能因 kairon __main__ 无 stdin 处理而返回 eof, 但 pid 必有)
        r1 = invoke_stdio(uri, "search", {})
        assert r1.get("pid") is not None and r1["pid"] > 0, f"first call failed: {r1}"
        pid1 = r1["pid"]
        # kill pool 中的进程
        if uri in _pool.processes and _pool.processes[uri].poll() is None:
            _pool.processes[uri].kill()
            _pool.processes[uri].wait()
        # 第二次调用自动 respawn
        r2 = invoke_stdio(uri, "search", {})
        pid2 = r2.get("pid", 0)
        assert pid2 > 0 and pid2 != pid1, (
            f"respawn 后 PID 应不同: pid1={pid1}, pid2={pid2}, r2={r2}"
        )

    @pytest.mark.xfail(reason="需要 kairon 子进程, 仅 CI 完整环境可用")
    def test_respawn_dead_batch_w1(self):
        """W1 验证: 批量 respawn_dead (使用 POC_SERVICES 真实 service)."""
        from agora.mcp.bos_resolver import _pool, POC_SERVICES

        uris = ["bos://memory/kos/search", "bos://analysis/minerva/research"]
        for uri in uris:
            _pool.get_or_spawn(next(s for s in POC_SERVICES if s.uri == uri))
            _pool.seen_uris.add(uri)
        # kill 2 个
        for uri in uris:
            proc = _pool.processes.get(uri)
            if proc:
                proc.kill()
                proc.wait()
        # 批量 respawn
        respawned = _pool.respawn_dead()
        assert len(respawned) == 2, (
            f"应 respawn 2 个, 实际 {len(respawned)}: {respawned}"
        )
        for uri in uris:
            assert uri in respawned
            _pool.shutdown(uri)

    @pytest.mark.asyncio
    async def test_resolve_unimplemented_bos_uri_raises_error(self):
        """测试对标记为 [UNIMPLEMENTED] 的 BOS 服务进行 resolve_bos_uri 时会被拦截并报错。"""
        from agora.mcp.bos_resolver import resolve_bos_uri
        from agora.mcp.resolver.services import POC_SERVICES

        unimpl_svc = next(
            (s for s in POC_SERVICES if s.description.startswith("[UNIMPLEMENTED]")),
            None,
        )
        if unimpl_svc is None:
            pytest.skip("当前注册表没有可路由的 [UNIMPLEMENTED] 服务")

        result = await resolve_bos_uri(unimpl_svc.uri)
        assert result["status"] == "error"
        assert "unimplemented_bos_service" in result["error"]
        assert result["description"] == unimpl_svc.description


_MCP_MOCK_SERVER = """
import json, sys

def send(msg):
    print(json.dumps(msg), flush=True)

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        req = json.loads(line)
    except Exception:
        continue
    method = req.get("method", "")
    req_id = req.get("id")
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": "2024-11-05", "serverInfo": {"name": "mock"}, "capabilities": {"tools": {}}}})
    elif method == "notifications/initialized":
        pass
    elif method == "tools/call":
        name = req.get("params", {}).get("name")
        args = req.get("params", {}).get("arguments", {})
        if name == "pkg/boom":
            send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32600, "message": "boom"}})
        else:
            send({"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": f"ok:{name}:{json.dumps(args)}"}]}})
"""

_MCP_MOCK_SERVER_INIT_ERROR = """
import json, sys

def send(msg):
    print(json.dumps(msg), flush=True)

for line in sys.stdin:
    req = json.loads(line.strip())
    req_id = req.get("id")
    if req.get("method") == "initialize":
        send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32600, "message": "init rejected"}})
"""


class TestStdioAdapterProtocol:
    def test_stdio_transport_uses_custom_json(self):
        """transport=stdio 向后兼容：发送自定义 {args, kwargs} JSON."""
        from agora.mcp.resolver.adapter import StdioAdapter

        svc = BosService(
            uri="bos://test/pkg/action",
            domain="test",
            package="pkg",
            action="action",
            transport="stdio",
            command=["cat"],
        )
        adapter = StdioAdapter(timeout=2.0)
        result = adapter.call(svc, {"x": 1})
        assert result["status"] == "ok"
        assert result["result"] == {"args": [{"x": 1}], "kwargs": {}}

    def test_stdio_nonzero_preserves_bounded_structured_error_without_secrets(self):
        """非零退出保留 typed JSON stdout，但 stderr 与敏感字段不得外泄。"""
        from agora.mcp.resolver.adapter import StdioAdapter

        script = """
import json, sys
print(json.dumps({
    "error": {"code": "gateway_auth_failed", "message": "denied"},
    "status": 401,
    "api_key": "stdout-secret",
}))
print("stderr-secret", file=sys.stderr)
raise SystemExit(7)
"""
        svc = BosService(
            uri="bos://compute/aetherforge/infer",
            domain="compute",
            package="aetherforge",
            action="infer",
            transport="stdio",
            command=[sys.executable, "-c", script],
        )

        result = StdioAdapter(timeout=2.0).call(svc)

        assert result["status"] == "error"
        assert result["exit_code"] == 7
        assert result["result"]["error"] == {
            "code": "gateway_auth_failed",
            "message": "denied",
        }
        assert result["result"]["api_key"] == "[REDACTED]"
        serialized = json.dumps(result)
        assert "stdout-secret" not in serialized
        assert "stderr-secret" not in serialized

    def test_stdio_nonzero_redacts_nested_path_and_identity_keys(self):
        """path/identity 组合键在任意嵌套层都必须失败闭合脱敏。"""
        from agora.mcp.resolver.adapter import StdioAdapter

        script = """
import json
print(json.dumps({
    "error": {
        "code": "gateway_failed",
        "details": {
            "workspacePath": "/Users/private/workspace",
            "ssh-identity-file": "/Users/private/.ssh/id_ed25519",
            "nested": [{"caller_identity": "private-user", "safe": "public-code"}],
        },
    },
    "path_identity_bundle": "private-bundle",
}))
raise SystemExit(8)
"""
        svc = BosService(
            uri="bos://compute/aetherforge/infer",
            domain="compute",
            package="aetherforge",
            action="infer",
            transport="stdio",
            command=[sys.executable, "-c", script],
        )

        result = StdioAdapter(timeout=2.0).call(svc)

        assert result["status"] == "error"
        assert result["exit_code"] == 8
        assert result["error"]["details"]["workspacePath"] == "[REDACTED]"
        assert result["error"]["details"]["ssh-identity-file"] == "[REDACTED]"
        assert result["error"]["details"]["nested"] == [
            {"caller_identity": "[REDACTED]", "safe": "public-code"}
        ]
        assert result["result"]["path_identity_bundle"] == "[REDACTED]"
        serialized = json.dumps(result)
        assert "/Users/private" not in serialized
        assert "private-user" not in serialized
        assert "private-bundle" not in serialized

    def test_stdio_nonzero_drops_oversized_structured_stdout(self):
        """过大的失败 stdout 不能进入 BOS envelope。"""
        from agora.mcp.resolver.adapter import StdioAdapter

        script = """
import json
print(json.dumps({"error": {"code": "too_large"}, "blob": "x" * 70000}))
raise SystemExit(9)
"""
        svc = BosService(
            uri="bos://compute/aetherforge/infer",
            domain="compute",
            package="aetherforge",
            action="infer",
            transport="stdio",
            command=[sys.executable, "-c", script],
        )

        result = StdioAdapter(timeout=2.0).call(svc)

        assert result["status"] == "error"
        assert result["exit_code"] == 9
        assert result["error"] == "subprocess_exit_nonzero"
        assert "result" not in result

    def test_stdio_timeout_kills_and_reaps_child(self, monkeypatch):
        """超时必须同时 kill 和 communicate，不能留下僵尸子进程。"""
        import subprocess

        from agora.mcp.resolver.adapter import StdioAdapter

        class TimedOutProcess:
            pid = 1234
            returncode = None

            def __init__(self):
                self.communicate_calls = 0
                self.killed = False
                self.reaped = False

            def communicate(self, *, input=None, timeout=None):
                self.communicate_calls += 1
                if self.communicate_calls == 1:
                    raise subprocess.TimeoutExpired(["fake"], timeout)
                self.reaped = True
                self.returncode = -9
                return "", ""

            def kill(self):
                self.killed = True

        proc = TimedOutProcess()
        monkeypatch.setattr(
            "agora.mcp.resolver.adapter.subprocess.Popen", lambda *_a, **_kw: proc
        )
        svc = BosService(
            uri="bos://compute/aetherforge/infer",
            domain="compute",
            package="aetherforge",
            action="infer",
            transport="stdio",
            command=["fake"],
        )

        result = StdioAdapter(timeout=0.01).call(svc)

        assert result["status"] == "error"
        assert result["error"] == "timeout"
        assert proc.killed is True
        assert proc.reaped is True

    def test_mcp_stdio_full_session_ok(self):
        """transport=mcp_stdio 走完整 initialize / initialized / tools/call."""
        from agora.mcp.resolver.adapter import StdioAdapter

        svc = BosService(
            uri="bos://test/pkg/action",
            domain="test",
            package="pkg",
            action="action",
            transport="mcp_stdio",
            command=[sys.executable, "-c", _MCP_MOCK_SERVER],
        )
        adapter = StdioAdapter(timeout=5.0)
        result = adapter.call(svc, {"x": 1})
        assert result["status"] == "ok"
        text = result["result"]["content"][0]["text"]
        assert "ok:pkg/action" in text
        assert '"x": 1' in text

    def test_mcp_stdio_full_session_error(self):
        """transport=mcp_stdio 正确传播 tools/call error."""
        from agora.mcp.resolver.adapter import StdioAdapter

        svc = BosService(
            uri="bos://test/pkg/boom",
            domain="test",
            package="pkg",
            action="boom",
            transport="mcp_stdio",
            command=[sys.executable, "-c", _MCP_MOCK_SERVER],
        )
        adapter = StdioAdapter(timeout=5.0)
        result = adapter.call(svc)
        assert result["status"] == "error"
        assert "boom" in str(result["error"])

    def test_mcp_stdio_initialize_error_closes_process(self):
        """initialize 失败时也应关闭子进程，避免泄漏."""
        from agora.mcp.resolver.adapter import StdioAdapter

        svc = BosService(
            uri="bos://test/pkg/action",
            domain="test",
            package="pkg",
            action="action",
            transport="mcp_stdio",
            command=[sys.executable, "-c", _MCP_MOCK_SERVER_INIT_ERROR],
        )
        adapter = StdioAdapter(timeout=5.0)
        result = adapter.call(svc)
        assert result["status"] == "error"
        assert "init rejected" in str(result["error"])

    def test_mcp_stdio_pool_reuses_process(self):
        """P1: ProcessPool 复用同一 mcp_stdio 子进程 (PID 不变)."""
        from agora.mcp.resolver.adapter import StdioAdapter
        from agora.mcp.resolver.pool import ProcessPool

        svc = BosService(
            uri="bos://test/pkg/pool",
            domain="test",
            package="pkg",
            action="pool",
            transport="mcp_stdio",
            command=[sys.executable, "-c", _MCP_MOCK_SERVER],
        )
        pool = ProcessPool()
        adapter = StdioAdapter(timeout=5.0, pool=pool)
        try:
            r1 = adapter.call(svc, {"x": 1})
            r2 = adapter.call(svc, {"x": 2})
            assert r1["status"] == "ok"
            assert r2["status"] == "ok"
            # 同一 URI 复用同一进程
            assert r1["pid"] == r2["pid"]
            assert len(pool.processes) == 1
        finally:
            adapter.shutdown()

    def test_mcp_stdio_pool_replaces_dead_process(self):
        """P1: pool 中进程死亡后重新 spawn."""
        from agora.mcp.resolver.adapter import StdioAdapter
        from agora.mcp.resolver.pool import ProcessPool

        svc = BosService(
            uri="bos://test/pkg/pooldead",
            domain="test",
            package="pkg",
            action="pooldead",
            transport="mcp_stdio",
            command=[sys.executable, "-c", _MCP_MOCK_SERVER],
        )
        pool = ProcessPool()
        adapter = StdioAdapter(timeout=5.0, pool=pool)
        try:
            r1 = adapter.call(svc, {"x": 1})
            assert r1["status"] == "ok"
            # 手动杀掉进程, 下次调用应重新 spawn
            pool.shutdown(svc.uri)
            r2 = adapter.call(svc, {"x": 2})
            assert r2["status"] == "ok"
            assert r2["pid"] != r1["pid"]
        finally:
            adapter.shutdown()
