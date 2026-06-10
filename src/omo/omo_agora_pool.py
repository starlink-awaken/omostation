"""P58-W1 omo agora pool — 长驻 subprocess 池 + 派发 + 一次性 fallback.

P43-W0: _AgoraPool 单连接长驻池
P44-W0: _AgoraPoolManager LRU 多连接池 (max=4)
P44-W1: 死连接 LRU 淘汰
P45-W5: 后台 heartbeat 清理 idle 死连接
P58-W1: 从 omo_llm_bos_bridge.py 716 行抽出
"""
from __future__ import annotations

import asyncio
import collections
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from omo.omo_audit_dedup import record_agora_failure  # P58-W1 dedup 抽 module


# ── Agora 长驻池 manager singleton ─────────────────────────────
_MANAGER: "_AgoraPoolManager | None" = None
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
    P58-W1: 移到独立 module.
    """

    HEARTBEAT_INTERVAL_SEC = float(
        os.environ.get("OMO_AGORA_HEARTBEAT_SEC", "30.0")
    )

    def __init__(
        self,
        cmd: list[str],
        max_size: int = 4,
        heartbeat_interval_sec: float | None = None,
    ) -> None:
        self._cmd = cmd
        self._max_size = max_size
        self._heartbeat_interval = (
            heartbeat_interval_sec
            if heartbeat_interval_sec is not None
            else self.HEARTBEAT_INTERVAL_SEC
        )
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
        """P45-W5: 后台心跳循环, 每 30s (可配) 扫一次 idle 池死连接."""
        while not self._heartbeat_stop.is_set():
            try:
                await asyncio.wait_for(
                    self._heartbeat_stop.wait(),
                    timeout=self._heartbeat_interval,
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
                    record_agora_failure(uri, err["type"], err["details"])
                    return {"_subprocess_error": err["details"], "transport": "agora_pool"}
                if isinstance(result, dict):
                    result.setdefault("_transport", "agora_pool")
                return result
            except Exception as exc:
                await manager.release(pool, alive=False)
                record_agora_failure(uri, "invoke_exception", f"{type(exc).__name__}: {exc}")
                return {"_subprocess_error": f"{type(exc).__name__}: {exc}", "transport": "agora_pool"}

    # Fallback: 一次性 subprocess (P42-W2 行为, 长驻池启动失败时)
    result = await _resolve_via_oneoff_subprocess(uri, args)
    if isinstance(result, dict):
        result.setdefault("_transport", "agora_subprocess")
    return result


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
        record_agora_failure(uri, "spawn_failed", f"{type(exc).__name__}: {exc}")
        return {"_subprocess_error": f"{type(exc).__name__}: {exc}"}
    finally:
        try:
            Path(args_file).unlink(missing_ok=True)
        except OSError:
            pass

    if proc.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace")
        record_agora_failure(uri, "non_zero_exit", f"rc={proc.returncode} stderr={stderr_text[:200]}")
        return {"_subprocess_error": stderr_text}

    try:
        return json.loads(stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        record_agora_failure(uri, "json_decode_failed", f"{type(exc).__name__}: {exc}")
        return None


__all__ = [
    "_AgoraPool",
    "_AgoraPoolManager",
    "_get_agora_pool",
    "_resolve_via_agora_subprocess",
    "_resolve_via_oneoff_subprocess",
    "_write_agora_daemon_script",
]
