"""BOS URI 解析器 — agora 侧 (P33-W4 + P34-W1 战役 1 升级).

输入: bos://<domain>/<package>/<action> + args
输出: 实际 MCP 工具调用结果 (stdio 子进程 / internal / http)

P33-W3 揭出 M3 高严重度: omo 进程 verify_endpoint 时, 20/21 kairon URI 不可达.
本质: URI 解析在错误进程 (omo). 正确位置: agora 进程 — subprocess spawn
kairon 子进程, MCP 协议通信. 此模块即战役 1 的 agora 侧落地.

P34-W1 升级: 从"进程 alive 验证"到"真 stdio JSON 协议通信".
  - 完整 JSON-RPC (写请求到 stdin, 读响应从 stdout)
  - 5s 超时控制 (select + timeout)
  - 错误处理 (BrokenPipe / JSONDecode / EOF)
  - 进程池复用 (同 URI 多次调用复用同一进程)

11 POC service 覆盖 5 Domain (memory / governance / analysis / persona / capability).
"""
from __future__ import annotations

import importlib
import json
import logging
import re
import select
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

_log = logging.getLogger(__name__)

# ── stdio 协议默认超时 (秒) ──────────────────────────
_STDIO_TIMEOUT_DEFAULT = 5.0

# ── 4 段标准 (W1 北星) ──────────────────────────────
BOS_URI_PATTERN = re.compile(
    r"^bos://(?P<domain>memory|governance|analysis|persona|capability)"
    r"/(?P<package>[a-z][a-z0-9-]+)/(?P<action>[a-z][a-z0-9-]+)$"
)

# ── 路径常量 ────────────────────────────────────────
KAIRON_ROOT = Path("/Users/xiamingxing/Workspace/projects/kairon")
METAOS_ROOT = Path("/Users/xiamingxing/Workspace/projects/metaos")
OMOSTATION_ROOT = Path("/Users/xiamingxing/Workspace")

# ── 类型 ────────────────────────────────────────────
Transport = Literal["stdio", "internal", "http"]


@dataclass
class BosService:
    """BOS 服务描述 — 怎么调用一个 URI."""

    uri: str
    domain: str
    package: str
    action: str
    transport: Transport = "stdio"
    # stdio: command 列表 (subprocess.Popen 用)
    command: list[str] = field(default_factory=list)
    # internal: import path + func
    module_path: str = ""
    func_name: str = ""
    # http: URL
    http_url: str = ""
    # 描述
    description: str = ""


# ── 5 Domain 5 包 POC service registry (11 总) ──────
# 命名规范: python -m <package> serve --action <action>
# 实际 stdio 协议: stdin JSON 行 → stdout JSON 行 (POC 简化版)
POC_SERVICES: dict[str, BosService] = {
    # Memory (2)
    "bos://memory/kos/search": BosService(
        uri="bos://memory/kos/search",
        domain="memory",
        package="kos",
        action="search",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "kos", "serve", "--action", "search",
        ],
        description="KOS 跨域语义搜索 (POC stdio)",
    ),
    "bos://memory/kronos/ingest": BosService(
        uri="bos://memory/kronos/ingest",
        domain="memory",
        package="kronos",
        action="ingest",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "kronos", "serve", "--action", "ingest",
        ],
        description="Kronos 知识摄入 (POC stdio)",
    ),
    # Governance (4)
    "bos://governance/omo/audit": BosService(
        uri="bos://governance/omo/audit",
        domain="governance",
        package="omo",
        action="audit",
        transport="internal",
        module_path="omo.omo_audit",
        func_name="run_governance_audit",
        description="OMO 治理审计 (internal — 同进程 importlib)",
    ),
    "bos://governance/metaos/gate": BosService(
        uri="bos://governance/metaos/gate",
        domain="governance",
        package="metaos",
        action="gate",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(METAOS_ROOT),
            "python", "-m", "metaos", "serve", "--action", "gate",
        ],
        description="MetaOS 门控检查 (POC stdio)",
    ),
    "bos://governance/sot-bridge/register": BosService(
        uri="bos://governance/sot-bridge/register",
        domain="governance",
        package="sot-bridge",
        action="register",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "sot_bridge", "serve", "--action", "register",
        ],
        description="SOT-Bridge 注册 (POC stdio)",
    ),
    "bos://governance/protocols-layer/trigger": BosService(
        uri="bos://governance/protocols-layer/trigger",
        domain="governance",
        package="protocols-layer",
        action="trigger",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "protocols_layer", "serve", "--action", "trigger",
        ],
        description="Protocols-Layer 触发 (POC stdio)",
    ),
    # Analysis (3 POC, 余 4 W4.5+)
    "bos://analysis/minerva/research": BosService(
        uri="bos://analysis/minerva/research",
        domain="analysis",
        package="minerva",
        action="research",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "minerva", "serve", "--action", "research",
        ],
        description="Minerva 深度研究 (POC stdio)",
    ),
    "bos://analysis/ontoderive/derive": BosService(
        uri="bos://analysis/ontoderive/derive",
        domain="analysis",
        package="ontoderive",
        action="derive",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "ontoderive", "serve", "--action", "derive",
        ],
        description="Ontoderive 事实推导 (POC stdio)",
    ),
    "bos://analysis/codeanalyze/scan": BosService(
        uri="bos://analysis/codeanalyze/scan",
        domain="analysis",
        package="codeanalyze",
        action="scan",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "codeanalyze", "serve", "--action", "scan",
        ],
        description="CodeAnalyze 代码扫描 (POC stdio)",
    ),
    # Persona (1 POC)
    "bos://persona/health-profile/summary": BosService(
        uri="bos://persona/health-profile/summary",
        domain="persona",
        package="health-profile",
        action="summary",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "health_profile", "serve", "--action", "summary",
        ],
        description="Health-Profile 健康摘要 (POC stdio)",
    ),
    # Capability (1 POC)
    "bos://capability/forge/register-tool": BosService(
        uri="bos://capability/forge/register-tool",
        domain="capability",
        package="forge",
        action="register-tool",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "forge", "serve", "--action", "register-tool",
        ],
        description="Forge 工具注册 (POC stdio)",
    ),
}


@dataclass
class ProcessPool:
    """BOS stdio 进程池 — 持久后台, 按需调用.

    设计:
      - 懒加载: 第一次调用时 spawn, 后续复用
      - 轻量清理: 提供 shutdown() 优雅终止
      - 持久 stdio: spawn 后保持 stdin/stdout 打开, 持续 serve (P34-W1)
      - request_id 自增: 每次调用分配唯一 request_id 跟踪响应
    """

    processes: dict[str, subprocess.Popen] = field(default_factory=dict)
    request_id: int = 0

    def _next_id(self) -> str:
        """生成唯一 request_id (req-<seq>-<rand>)."""
        self.request_id += 1
        return f"req-{self.request_id}-{uuid.uuid4().hex[:8]}"

    def get_or_spawn(self, service: BosService) -> subprocess.Popen:
        """懒加载 spawn. PID 在 spawn 后即可获取."""
        if service.uri not in self.processes:
            self.processes[service.uri] = subprocess.Popen(
                service.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(KAIRON_ROOT),
                bufsize=0,  # unbuffered for stdio JSON 协议
            )
            _log.info("Spawned BOS service: %s (pid=%d)", service.uri, self.processes[service.uri].pid)
        return self.processes[service.uri]

    def is_alive(self, uri: str) -> bool:
        """检查 URI 对应进程是否还活着."""
        proc = self.processes.get(uri)
        if proc is None:
            return False
        return proc.poll() is None

    def shutdown(self, uri: str | None = None) -> int:
        """关闭一个或全部进程. 返回关闭数量."""
        if uri is None:
            count = 0
            for u in list(self.processes.keys()):
                count += self.shutdown(u)
            return count
        proc = self.processes.pop(uri, None)
        if proc is None:
            return 0
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        return 1

    def status(self) -> dict[str, bool]:
        """全部 URI → alive 状态."""
        return {uri: self.is_alive(uri) for uri in self.processes}


# 全局进程池 (单例)
_pool = ProcessPool()


def get_pool() -> ProcessPool:
    """获取全局进程池."""
    return _pool


# ── 解析 + 调用 ─────────────────────────────────────
def parse_bos_uri(uri: str) -> dict[str, str]:
    """解析 BOS URI. 抛 ValueError 当格式错."""
    m = BOS_URI_PATTERN.match(uri)
    if not m:
        raise ValueError(f"Invalid BOS URI: {uri!r} (expected bos://<domain>/<package>/<action>)")
    return m.groupdict()


def _call_internal(service: BosService, *args: Any, **kwargs: Any) -> dict:
    """internal transport: 同进程 importlib 调用."""
    try:
        mod = importlib.import_module(service.module_path)
        func = getattr(mod, service.func_name)
        result = func(*args, **kwargs)
    except ImportError as exc:
        return {
            "uri": service.uri,
            "transport": "internal",
            "status": "error",
            "error": f"import_failed: {exc}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "uri": service.uri,
            "transport": "internal",
            "status": "error",
            "error": f"call_failed: {exc}",
        }
    # dataclass 兼容
    if hasattr(result, "__dataclass_fields__"):
        result_repr = {k: str(v) for k, v in result.__dict__.items()}
    elif isinstance(result, (dict, list, str, int, float, bool, type(None))):
        result_repr = result
    else:
        result_repr = repr(result)
    return {
        "uri": service.uri,
        "transport": "internal",
        "status": "ok",
        "result_type": type(result).__name__,
        "result": result_repr,
    }


def _call_stdio(service: BosService, *args: Any, **kwargs: Any) -> dict:
    """stdio transport: 真 stdio JSON 协议 (P34-W1 升级).

    流程:
      1. spawn kairon 子进程 (Popen, bufsize=0 unbuffered)
      2. 写 JSON 请求到 stdin: {"request_id", "action", "args"}
      3. 读一行 JSON 响应从 stdout: {"status", "result"|"error", ...}
      4. 5s 超时控制 (select)
      5. 进程持久: 后续调用复用 (不关闭)

    协议格式 (与 kairon __main__.py 一致):
      请求: {"request_id": "req-N-xxx", "action": "<name>", "args": <list>}
      响应: {"status": "ok|error", "service": "<name>", "action": "<name>",
             "request_id": "<id>", "result": {...} | "error": "..."}
    """
    return invoke_stdio(service.uri, service.action, args, kwargs, timeout=_STDIO_TIMEOUT_DEFAULT)


def invoke_stdio(
    uri: str,
    action: str,
    args: list | None = None,
    kwargs: dict | None = None,
    timeout: float = _STDIO_TIMEOUT_DEFAULT,
) -> dict:
    """通过 stdio JSON 协议调用 BOS 服务 (P34-W1 主入口).

    协议:
      写一行 JSON 到 stdin: {"request_id": "req-N-xxx", "action": "...", "args": [...]}
      从 stdout 读一行 JSON: {"status": "ok|error", "result": {...} | "error": "..."}

    Args:
        uri: bos://<domain>/<package>/<action>
        action: 子进程的 action 名 (从 URI 解析)
        args: 位置参数列表
        kwargs: 关键字参数字典
        timeout: 超时秒数 (默认 5.0)

    Returns:
        dict: 含 status + result/error + request_id + pid 等字段
    """
    service = POC_SERVICES.get(uri)
    if service is None:
        return {
            "uri": uri,
            "status": "error",
            "error": f"unknown_bos_uri: {uri} (registered: {len(POC_SERVICES)})",
        }
    if service.transport != "stdio":
        return {
            "uri": uri,
            "status": "error",
            "error": f"not_stdio_transport: {service.transport}",
        }

    pool = get_pool()
    try:
        proc = pool.get_or_spawn(service)
    except FileNotFoundError as exc:
        return {
            "uri": uri,
            "status": "error",
            "error": f"command_not_found: {exc}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "uri": uri,
            "status": "error",
            "error": f"spawn_failed: {exc}",
        }

    if not pool.is_alive(uri):
        return {
            "uri": uri,
            "status": "error",
            "error": f"process_dead: pid={proc.pid}",
        }

    # 构造请求
    request_id = pool._next_id()
    request = {
        "request_id": request_id,
        "action": action,
        "args": list(args) if args else [],
    }
    if kwargs:
        request["kwargs"] = kwargs
    request_line = json.dumps(request, ensure_ascii=False) + "\n"

    try:
        # 写请求
        proc.stdin.write(request_line.encode("utf-8"))
        proc.stdin.flush()

        # 读响应 (select 避免阻塞)
        ready, _, _ = select.select([proc.stdout], [], [], timeout)
        if not ready:
            return {
                "uri": uri,
                "status": "error",
                "error": f"timeout_after_{timeout}s",
                "request_id": request_id,
                "pid": proc.pid,
            }

        response_line = proc.stdout.readline()
        if not response_line:
            return {
                "uri": uri,
                "status": "error",
                "error": "eof_no_response",
                "request_id": request_id,
                "pid": proc.pid,
            }

        response = json.loads(response_line.decode("utf-8"))
        response["uri"] = uri
        response["request_id"] = response.get("request_id", request_id)
        response["pid"] = proc.pid
        return response

    except BrokenPipeError as exc:
        return {
            "uri": uri,
            "status": "error",
            "error": f"broken_pipe: {exc}",
            "request_id": request_id,
        }
    except OSError as exc:
        return {
            "uri": uri,
            "status": "error",
            "error": f"stdio_io_error: {exc}",
            "request_id": request_id,
        }
    except json.JSONDecodeError as exc:
        return {
            "uri": uri,
            "status": "error",
            "error": f"json_decode_error: {exc}",
            "request_id": request_id,
        }


async def resolve_bos_uri(uri: str, *args: Any, **kwargs: Any) -> dict:
    """解析 BOS URI 到实际调用 (主入口, async 兼容)."""
    parsed = parse_bos_uri(uri)
    service = POC_SERVICES.get(uri)
    if service is None:
        return {
            "uri": uri,
            "parsed": parsed,
            "status": "error",
            "error": f"unknown_bos_uri: {uri} (registered: {len(POC_SERVICES)})",
        }
    if service.transport == "internal":
        # internal 在事件循环内同步执行 (omo 同进程)
        return _call_internal(service, *args, **kwargs)
    if service.transport == "stdio":
        return _call_stdio(service, *args, **kwargs)
    return {
        "uri": uri,
        "status": "error",
        "error": f"unsupported_transport: {service.transport}",
    }


def list_services() -> list[dict]:
    """列出所有 POC services + 实时状态 + PID (P34-W1 升级含 pid)."""
    pool = get_pool()
    out = []
    for uri, svc in POC_SERVICES.items():
        proc = pool.processes.get(uri) if svc.transport == "stdio" else None
        out.append({
            "uri": uri,
            "domain": svc.domain,
            "package": svc.package,
            "action": svc.action,
            "transport": svc.transport,
            "alive": pool.is_alive(uri) if svc.transport == "stdio" else None,
            "pid": proc.pid if proc and proc.pid else None,
            "description": svc.description,
        })
    return out


def get_service(uri: str) -> BosService | None:
    """查询单个 service (无副作用)."""
    return POC_SERVICES.get(uri)


def list_domains() -> dict[str, list[str]]:
    """按 domain 聚合 URI."""
    grouped: dict[str, list[str]] = {}
    for uri, svc in POC_SERVICES.items():
        grouped.setdefault(svc.domain, []).append(uri)
    return grouped


# ── 协议健康自检 (P33-W4 战役 1 自带) ─────────────
def protocol_self_check() -> dict:
    """自检: 报告注册表 + 解析器 + 池状态."""
    return {
        "status": "ok",
        "total_services": len(POC_SERVICES),
        "domains": list(list_domains().keys()),
        "by_transport": {
            t: sum(1 for s in POC_SERVICES.values() if s.transport == t)
            for t in ("stdio", "internal", "http")
        },
        "active_processes": len(get_pool().processes),
        "kairon_root": str(KAIRON_ROOT),
        "metaos_root": str(METAOS_ROOT),
    }


# Re-export 关键 API
__all__ = (
    "BOS_URI_PATTERN",
    "BosService",
    "ProcessPool",
    "KAIRON_ROOT",
    "METAOS_ROOT",
    "POC_SERVICES",
    "get_pool",
    "parse_bos_uri",
    "resolve_bos_uri",
    "invoke_stdio",
    "list_services",
    "list_domains",
    "get_service",
    "protocol_self_check",
)


if __name__ == "__main__":
    # CLI 自检模式: python -m agora.mcp.bos_resolver self-check
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "self-check":
        print(json.dumps(protocol_self_check(), indent=2, ensure_ascii=False))
    else:
        # 默认: 打印所有 services
        for svc in list_services():
            print(json.dumps(svc, ensure_ascii=False))
