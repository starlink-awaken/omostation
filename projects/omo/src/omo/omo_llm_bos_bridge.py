"""LLM 工具调用 BOS URI 桥接 — P37-W2 跨域+LLM 实战.

LLM (Claude/GPT) 通过 tool_use 调 BOS URI 跨域串联.

P37-W2 目标: 把 BOS URI 抽象暴露成 LLM 可理解的 tool 工具集,
让 LLM 通过 tool_use 协议直接 invoke 知识工程/治理/分析域的 URI.

设计:
- 工具 1: ``invoke_bos_uri(uri, args)``  - 调单个 BOS URI
- 工具 2: ``list_bos_uris(domain?)``     - 列已注册 URI (供 LLM 上下文)
- 派发: ``TOOL_DISPATCHER``  - LLM 调用的同步派发表

POC 模式: 不依赖 anthropic/openai 包, 仅做工具 schema + 派发器,
真实场景由 demo 脚本 + LLM API 串联 (mock 模式可纯本地跑通).

P32 收官约束: 不改 agora 核心, 不重启 omo daemon, 0 破坏性操作.
本模块纯加法, 只读 BOS URI 注册表, 不写.
"""

from __future__ import annotations

import asyncio
import collections
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# ── BOS URI 验证/解析 ──────────────────────────────────────
# 复用 omo.omo_bos 北星验证, 避免重复实现 URI 解析逻辑
try:
    from omo.omo_bos import validate_bos_uri, parse_bos_uri, load_registry
except ImportError:  # pragma: no cover - 路径旁路场景
    # 允许脱离 PYTHONPATH 单测, 加 src 兜底
    _OMO_SRC = Path(__file__).resolve().parents[0]
    if str(_OMO_SRC) not in sys.path:
        sys.path.insert(0, str(_OMO_SRC))
    from omo.omo_bos import validate_bos_uri, parse_bos_uri, load_registry  # type: ignore[no-redef]


# ── 工具 schema (Anthropic tool_use 格式) ────────────────────


def bos_uri_tool_schema() -> list[dict[str, Any]]:
    """返回 LLM tool_use 工具的 schema (Anthropic 格式).

    LLM 看到这个 schema 后, 会决定在对话中调
    ``invoke_bos_uri`` 或 ``list_bos_uris`` 工具.

    OpenAI function-calling 格式: 把 ``input_schema`` 改成 ``parameters``
    并补 ``"strict": True``, 字段相同.
    """
    return [
        {
            "name": "invoke_bos_uri",
            "description": (
                "调用 BOS (Banyan Object Service) URI 执行知识工程/治理/分析/能力操作. "
                "BOS URI 格式: bos://<domain>/<package>/<action>. "
                "5 个 domain: memory (知识存储/摄取), governance (治理/门控), "
                "analysis (推演/分析), persona (数字人/桥接), capability (工具/能力). "
                "可先用 list_bos_uris 查可用 URI."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "uri": {
                        "type": "string",
                        "description": (
                            "BOS URI, 格式 bos://<domain>/<package>/<action>. "
                            "domain ∈ memory|governance|analysis|persona|capability. "
                            "package/action 是 kebab-case 小写."
                        ),
                        "pattern": (
                            r"^bos://(memory|governance|analysis|persona|capability)"
                            r"/[a-z][a-z0-9-]*[a-z0-9]?/[a-z][a-z0-9-]*[a-z0-9]?$"
                        ),
                    },
                    "args": {
                        "type": "object",
                        "description": (
                            "URI 调用参数 (如 query, topic, path, source 等). "
                            "schema 因 URI 而异, 优先读 list_bos_uris 的 description."
                        ),
                    },
                },
                "required": ["uri"],
            },
        },
        {
            "name": "list_bos_uris",
            "description": (
                "列出已注册的 BOS URI, 可按 domain 过滤. "
                "返回: 每条含 uri/domain/package/action/description. "
                "用来给 LLM 选可用 URI."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "enum": [
                            "memory",
                            "governance",
                            "analysis",
                            "persona",
                            "capability",
                        ],
                        "description": "可选, 按 domain 过滤",
                    },
                },
            },
        },
    ]


# ── 工具实现 (派发器 target) ────────────────────────────────


async def invoke_bos_uri_tool(uri: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """LLM 调 BOS URI 工具入口.

    返回: 标准 dict (JSON 序列化友好), 供 LLM 二次 round 解析.

    失败语义: 永不抛异常, 总是 dict (LLM 不会崩溃).
    """
    args = args or {}

    # 1) 北星验证
    valid, err = validate_bos_uri(uri)
    if not valid:
        return {"error": err, "uri": uri, "status": "invalid_uri"}

    # 2) 解析
    try:
        parsed = parse_bos_uri(uri)
    except ValueError as exc:  # pragma: no cover - validate 已守
        return {"error": str(exc), "uri": uri, "status": "parse_failed"}

    # 3) agora 接管 (走 MCP 跨进程, P32 上线的统一入口)
    # P32 架构: agora 独立 venv 跨进程通信, 不 in-process import
    # (因 agora 依赖链含 websockets/aiohttp, 拉进 omo 进程会污染 omo 依赖面)
    sub_result = await _resolve_via_agora_subprocess(uri, args)
    if sub_result is not None:
        transport = sub_result.pop("_transport", "agora_subprocess")
        return {
            "uri": uri,
            "domain": parsed["domain"],
            "package": parsed["package"],
            "action": parsed["action"],
            "status": "resolved",
            "transport": transport,
            "result": sub_result,
        }

    # subprocess 全失败 (agora venv 不可用 / URI 不在 11 POC registry)
    return {
        "uri": uri,
        "domain": parsed["domain"],
        "package": parsed["package"],
        "action": parsed["action"],
        "status": "agora_unavailable",
        "note": "agora subprocess 派发失败 (URI 不在 11 POC registry 或 venv 不可用)",
    }


async def _resolve_via_agora_subprocess(uri: str, args: dict[str, Any]) -> dict[str, Any] | None:
    """跨进程调 agora venv 跑 resolve_bos_uri (P32 跨进程架构, P42-W2 落地, P43-W0 长驻池).

    设计理由:
      - agora 是独立 venv, 含 websockets/aiohttp 等重依赖
      - omo 进程不 import agora (避免污染 omo 依赖面, 也避免 agora→omo 循环依赖)
      - P43-W0: 长驻 subprocess 池, 一次 spawn 多次调用, 消除每次 10-15s 启动开销
      - 长驻池启动失败 → fallback 到一次性 subprocess (P42-W2 行为)

    返回:
      - dict: agora resolve_bos_uri 的 result 字段
      - None: subprocess 失败 (uv/venv 不可用, URI 不在 registry, JSON parse 失败)
    """
    # P44-W0: 优先用多连接长驻池 manager (P43-W0 单连接池升级)
    manager = await _get_agora_pool()
    if manager is not None:
        pool = await manager.acquire()
        if pool is not None:
            try:
                result, err = await pool.invoke(uri, args)
                # P44-W1: 僵死检测 — err 含 eof/timeout/broken_pipe 时 alive=False
                alive = err is None
                await manager.release(pool, alive=alive)
                if err is not None:
                    _record_agora_failure(uri, err["type"], err["details"])
                    return {"_subprocess_error": err["details"], "transport": "agora_pool"}
                if isinstance(result, dict):
                    result.setdefault("_transport", "agora_pool")
                return result
            except Exception as exc:
                await manager.release(pool, alive=False)
                _record_agora_failure(uri, "invoke_exception", f"{type(exc).__name__}: {exc}")
                return {"_subprocess_error": f"{type(exc).__name__}: {exc}", "transport": "agora_pool"}

    # Fallback: 一次性 subprocess (P42-W2 行为, 长驻池启动失败时)
    result = await _resolve_via_oneoff_subprocess(uri, args)
    if isinstance(result, dict):
        result.setdefault("_transport", "agora_subprocess")
    return result


class _AgoraPool:
    """P43-W0: 长驻 agora subprocess, stdin/stdout 持久通信.

    协议 (行式 JSON-RPC 简化):
      - 客户端写: "URI <json_payload>\\n"
      - 服务端响应: "JSON <result_json>\\n" 或 "ERR <error_msg>\\n"
      - 客户端关闭: "QUIT\\n"
      - 服务端退出: EOF on stdin

    单连接串行, asyncio.Lock 同步.
    """

    def __init__(self, cmd: list[str]) -> None:
        self._cmd = cmd
        self._proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()

    def is_alive(self) -> bool:
        """P44-W1: 僵死检测 — returncode 是 None 表示还活着."""
        return self._proc is not None and self._proc.returncode is None

    async def start(self) -> bool:
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *self._cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    async def invoke(
        self, uri: str, args: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
        """invoke URI, 返 (result, err). err 非空表示失败."""
        assert self._proc is not None and self._proc.stdin and self._proc.stdout
        async with self._lock:
            try:
                payload = (
                    "URI "
                    + json.dumps({"uri": uri, "args": args}, ensure_ascii=False)
                    + "\n"
                )
                self._proc.stdin.write(payload.encode("utf-8"))
                await self._proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError) as exc:
                return None, {"type": "pool_broken_pipe", "details": str(exc)}

            try:
                line = await asyncio.wait_for(
                    self._proc.stdout.readline(), timeout=30
                )
            except asyncio.TimeoutError:
                return None, {"type": "pool_read_timeout", "details": "30s timeout"}

            text = line.decode("utf-8", errors="replace").rstrip()
            if text.startswith("JSON "):
                try:
                    return json.loads(text[5:]), None
                except json.JSONDecodeError as exc:
                    return None, {
                        "type": "json_decode_failed",
                        "details": f"{type(exc).__name__}: {exc}",
                    }
            if text.startswith("ERR "):
                return None, {"type": "daemon_error", "details": text[4:]}
            if not text:  # EOF
                return None, {"type": "pool_eof", "details": "agora daemon closed"}
            return None, {"type": "pool_unexpected", "details": text[:200]}

    async def close(self) -> None:
        if self._proc and self._proc.returncode is None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.write(b"QUIT\n")
                    await self._proc.stdin.drain()
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except (BrokenPipeError, asyncio.TimeoutError, OSError):
                try:
                    self._proc.kill()
                except ProcessLookupError:
                    pass


class _AgoraPoolManager:
    """P44-W0: LRU 多连接池, max_size=4, 支持并发 invoke.

    acquire() 拿空闲连接 (无空闲且 active < max 时新建, 否则返 None)
    release(pool, alive) 还连接 (alive=False 时关掉, LRU 淘汰最旧)

    P44-W1: 死连接由 is_alive() 探测, 死亡池 LRU 淘汰时关闭.
    P45-W5: 后台 heartbeat 主动检测长空闲连接的死活.
    """

    HEARTBEAT_INTERVAL_SEC = 30.0

    def __init__(self, cmd: list[str], max_size: int = 4) -> None:
        self._cmd = cmd
        self._max_size = max_size
        self._idle: collections.deque[_AgoraPool] = collections.deque()
        self._active = 0
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task | None = None
        self._heartbeat_stop = asyncio.Event()

    async def acquire(self) -> _AgoraPool | None:
        async with self._lock:
            # 先取 idle, 跳过死的
            while self._idle:
                p = self._idle.popleft()
                if p.is_alive():
                    self._active += 1
                    return p
                # 死的, 关掉 (不等)
                asyncio.create_task(p.close())  # noqa: RUF006
            # 无 idle, 尝试新建
            if self._active < self._max_size:
                p = _AgoraPool(self._cmd)
                if await p.start():
                    self._active += 1
                    return p
            return None  # 已满

    async def release(self, pool: _AgoraPool, alive: bool) -> None:
        async with self._lock:
            self._active = max(0, self._active - 1)
            if not alive or not pool.is_alive():
                # 死的, 关掉
                asyncio.create_task(pool.close())  # noqa: RUF006
                return
            self._idle.append(pool)
            # LRU: idle 超过 max 时淘汰最旧
            while len(self._idle) > self._max_size:
                old = self._idle.popleft()
                asyncio.create_task(old.close())  # noqa: RUF006

    async def start_heartbeat(self) -> None:
        """P45-W5: 启动后台 heartbeat task, 定期清理 idle 池死连接.

        每 30s 扫一次 idle 池, is_alive() 探测, 死的关掉 + 从 idle 移除.
        第一次 acquire 时自动启动, close_all() 时 cancel.
        """
        if self._heartbeat_task is not None and not self._heartbeat_task.done():
            return
        self._heartbeat_stop.clear()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        """P45-W5: 后台心跳循环, 每 30s 扫一次 idle 池死连接."""
        while not self._heartbeat_stop.is_set():
            try:
                await asyncio.wait_for(
                    self._heartbeat_stop.wait(),
                    timeout=self.HEARTBEAT_INTERVAL_SEC,
                )
                break  # stop event set
            except asyncio.TimeoutError:
                pass  # 30s 到, 跑一次清理
            # 清理死连接
            async with self._lock:
                dead = []
                live = collections.deque()
                while self._idle:
                    p = self._idle.popleft()
                    if p.is_alive():
                        live.append(p)
                    else:
                        dead.append(p)
                self._idle = live
                for p in dead:
                    asyncio.create_task(p.close())  # noqa: RUF006

    async def close_all(self) -> None:
        # P45-W5: 先停 heartbeat, 再清池
        if self._heartbeat_task is not None:
            self._heartbeat_stop.set()
            try:
                await asyncio.wait_for(self._heartbeat_task, timeout=2)
            except asyncio.TimeoutError:
                self._heartbeat_task.cancel()
            self._heartbeat_task = None
        async with self._lock:
            while self._idle:
                p = self._idle.popleft()
                try:
                    await p.close()
                except Exception:
                    pass
            self._active = 0


# ── Agora 长驻池 manager singleton ─────────────────────────────
_MANAGER: _AgoraPoolManager | None = None
_MANAGER_INIT_LOCK: asyncio.Lock | None = None
_DAEMON_SCRIPT_PATH: Path | None = None


def _write_agora_daemon_script() -> str | None:
    """P43-W0: 写临时 agora daemon 脚本 (subprocess 启动它, 持久 stdin/stdout)."""
    global _DAEMON_SCRIPT_PATH
    if _DAEMON_SCRIPT_PATH and _DAEMON_SCRIPT_PATH.exists():
        return str(_DAEMON_SCRIPT_PATH)
    try:
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".py", prefix="agora_daemon_")
        daemon_code = (
            "import asyncio, json, sys\n"
            "from agora.mcp.bos_resolver import resolve_bos_uri\n"
            "\n"
            "while True:\n"
            "    line = sys.stdin.readline()\n"
            "    if not line:\n"
            "        break\n"
            "    line = line.rstrip()\n"
            "    if line == 'QUIT':\n"
            "        break\n"
            "    if line.startswith('URI '):\n"
            "        try:\n"
            "            payload = json.loads(line[4:])\n"
            "            r = asyncio.run(resolve_bos_uri(payload['uri'], **payload.get('args') or {}))\n"
            "            sys.stdout.write('JSON ' + json.dumps(r, ensure_ascii=False) + '\\n')\n"
            "        except Exception as exc:\n"
            "            sys.stdout.write('ERR ' + f'{type(exc).__name__}: {exc}' + '\\n')\n"
            "        sys.stdout.flush()\n"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(daemon_code)
        _DAEMON_SCRIPT_PATH = Path(path)
        return path
    except OSError:
        return None


async def _get_agora_pool() -> _AgoraPoolManager | None:
    """P44-W0: singleton LRU 多连接池 manager, 启动失败返 None.

    P43-W0 是单 _AgoraPool, P44-W0 升级为 _AgoraPoolManager (max=4).
    P44-W1: 死连接由 manager.release(alive=False) 关闭.
    """
    global _MANAGER
    if _MANAGER is not None:
        return _MANAGER
    global _MANAGER_INIT_LOCK
    if _MANAGER_INIT_LOCK is None:
        _MANAGER_INIT_LOCK = asyncio.Lock()
    async with _MANAGER_INIT_LOCK:
        if _MANAGER is not None:
            return _MANAGER
        try:
            from omo.omo_paths import PROJECTS_DIR

            agora_project = PROJECTS_DIR / "agora"
            if not (agora_project / "pyproject.toml").exists():
                return None
            daemon_script = _write_agora_daemon_script()
            if daemon_script is None:
                return None
            cmd = [
                "uv",
                "run",
                "--project",
                str(agora_project),
                "python",
                daemon_script,
            ]
            manager = _AgoraPoolManager(cmd, max_size=4)
            # 预热: 启动 1 个连接, 避免首调用冷启动延迟
            warm = await manager.acquire()
            if warm is None:
                return None
            await manager.release(warm, alive=True)
            # P45-W5: 启动后台 heartbeat, 主动清理 idle 池死连接
            await manager.start_heartbeat()
            _MANAGER = manager
            return _MANAGER
        except Exception:
            return None


async def _resolve_via_oneoff_subprocess(
    uri: str, args: dict[str, Any]
) -> dict[str, Any] | None:
    """P42-W2 行为保留: 长驻池不可用时, fallback 到一次性 subprocess.

    启动开销 10-15s, 但保证可派发.
    """
    try:
        from omo.omo_paths import PROJECTS_DIR

        _AGORA_PROJECT = PROJECTS_DIR / "agora"
    except Exception:
        return None

    if not (_AGORA_PROJECT / "pyproject.toml").exists():
        return None

    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump({"uri": uri, "args": args}, f, ensure_ascii=False)
        args_file = f.name

    inline_py = (
        "import asyncio, json, sys; "
        f"from agora.mcp.bos_resolver import resolve_bos_uri; "
        f"p = {args_file!r}; "
        "data = json.load(open(p)); "
        "r = asyncio.run(resolve_bos_uri(data['uri'], **data.get('args') or {})); "
        "sys.stdout.write(json.dumps(r, ensure_ascii=False))"
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            "uv",
            "run",
            "--project",
            str(_AGORA_PROJECT),
            "python",
            "-c",
            inline_py,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except (subprocess.SubprocessError, asyncio.TimeoutError, OSError) as exc:
        _record_agora_failure(uri, "spawn_failed", f"{type(exc).__name__}: {exc}")
        return {"_subprocess_error": f"{type(exc).__name__}: {exc}"}
    finally:
        try:
            Path(args_file).unlink(missing_ok=True)
        except OSError:
            pass

    if proc.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace")
        _record_agora_failure(uri, "non_zero_exit", f"rc={proc.returncode} stderr={stderr_text[:200]}")
        return {"_subprocess_error": stderr_text}

    try:
        return json.loads(stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        _record_agora_failure(uri, "json_decode_failed", f"{type(exc).__name__}: {exc}")
        return None


# ── P44-W3: audit dedup (同 (uri, failure_type) 1 分钟内只 1 条) ─
_AUDIT_DEDUP_TTL_SEC = 60
_AUDIT_DEDUP_CACHE: dict[tuple[str, str], float] = {}


def _audit_should_record(uri: str, failure_type: str) -> bool:
    """P44-W3: 返回 True 表示可以 record (新 key 或 1 分钟前已过).

    用 in-memory dict + 60s TTL, 不持久化. 进程重启后清空.
    """
    import time as _time

    key = (uri, failure_type)
    now = _time.time()
    last = _AUDIT_DEDUP_CACHE.get(key)
    if last is not None and (now - last) < _AUDIT_DEDUP_TTL_SEC:
        return False
    _AUDIT_DEDUP_CACHE[key] = now
    # 简单 LRU 截断: 超过 1000 条清空 (避免无限增长)
    if len(_AUDIT_DEDUP_CACHE) > 1000:
        _AUDIT_DEDUP_CACHE.clear()
    return True


def _record_agora_failure(uri: str, failure_type: str, details: str) -> None:
    """P43-W2: 跨进程 agora 派发失败时 record omo-audit, 让治理 daemon 看到.
    P44-W3: 加 dedup, 同 (uri, failure_type) 1 分钟内只 1 条.

    失败类型: spawn_failed (uv/venv 不可用) / non_zero_exit (agora venv 内异常) /
              json_decode_failed (stdout 不是 JSON) / unknown_bos_uri (POC_SERVICES 没注册)
    """
    if not _audit_should_record(uri, failure_type):
        return
    try:
        from omo.omo_audit import record as audit_record  # type: ignore[import-not-found]

        audit_record(
            action="bos_resolve_failure",
            debt_id=f"BOS-RESOLVE-{failure_type.upper()}",
            actor="omo-bridge",
            details=f"uri={uri} failure={failure_type} {details}",
        )
    except Exception:
        # audit 自身失败不阻塞业务流
        pass


def list_bos_uris_tool(domain: str | None = None) -> dict[str, Any]:
    """列出已注册 URI (走本地 bos-registry.json via load_registry)."""
    try:
        regs = load_registry()
    except Exception as exc:
        return {"error": f"registry_load_failed: {exc}", "count": 0, "uris": []}

    if domain:
        regs = [r for r in regs if r.get("domain") == domain]

    # 压缩字段供 LLM 读
    compact = [
        {
            "uri": r.get("uri"),
            "domain": r.get("domain"),
            "package": r.get("package"),
            "action": r.get("action"),
            "description": r.get("description", ""),
        }
        for r in regs
    ]
    return {"count": len(compact), "uris": compact}


# ── 派发器 (供 demo + 真 API 模式共用) ──────────────────────


def _dispatch_sync(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """同步派发 (供不支持 async 的 LLM client 用)."""
    if name == "invoke_bos_uri":
        return asyncio.run(invoke_bos_uri_tool(args["uri"], args.get("args")))
    if name == "list_bos_uris":
        return list_bos_uris_tool(args.get("domain"))
    return {"error": f"unknown_tool: {name}"}


TOOL_DISPATCHER: dict[str, Any] = {
    "invoke_bos_uri": _dispatch_sync,  # 闭包内调 asyncio.run
    "list_bos_uris": _dispatch_sync,
}


# ── 自测 (直接 python omo_llm_bos_bridge.py) ───────────────


def _self_test() -> int:
    """快速自测: 验证 schema + 派发器本地闭环."""
    print("=" * 60)
    print("omo.llm_bos_bridge 自测")
    print("=" * 60)

    # 1) schema
    schema = bos_uri_tool_schema()
    assert len(schema) == 2, "schema 必须是 2 个工具"
    names = {s["name"] for s in schema}
    assert names == {"invoke_bos_uri", "list_bos_uris"}, f"工具名错: {names}"
    print(f"[OK] schema: 2 tools, names={names}")

    # 2) list
    r = TOOL_DISPATCHER["list_bos_uris"]({"domain": "memory"})
    print(f"[OK] list_bos_uris(memory): count={r.get('count', '?')}")
    assert "count" in r, "list 必须返回 count"

    # 3) invoke (memory/kos/search)
    r = TOOL_DISPATCHER["invoke_bos_uri"](
        {"uri": "bos://memory/kos/search", "args": {"query": "kairon commits"}}
    )
    print(f"[OK] invoke bos://memory/kos/search: status={r.get('status', '?')}")
    assert r.get("status") in ("resolved", "agora_unavailable"), (
        f"invoke 状态错: {r}"
    )

    # 4) invoke (invalid)
    r = TOOL_DISPATCHER["invoke_bos_uri"]({"uri": "bos://bad/foo/bar"})
    print(f"[OK] invoke invalid: status={r.get('status', '?')}")
    assert r.get("status") == "invalid_uri", f"invalid 状态错: {r}"

    # 5) invoke (5 跨域)
    uris = [
        ("bos://memory/kos/search", {"query": "kairon commits"}),
        ("bos://analysis/minerva/research", {"topic": "kairon 提交趋势"}),
        ("bos://analysis/minerva/draft", {"topic": "kairon 提交趋势"}),
        ("bos://analysis/iris/transform", {}),
        ("bos://capability/forge/list-tools", {}),
    ]
    for uri, args in uris:
        r = TOOL_DISPATCHER["invoke_bos_uri"]({"uri": uri, "args": args})
        print(f"  - {uri}: status={r.get('status', '?')}")
    print()
    print("[OK] omo.llm_bos_bridge 自测全过")
    return 0


if __name__ == "__main__":
    sys.exit(_self_test())
