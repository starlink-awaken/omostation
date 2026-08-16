"""claude_code — Claude Code CLI 适配器。

提取自 D_Extension adapters/claude_code_adapter.py。
- 本地定义 ICliAdapter 协议（不再从 D_Execution 导入）
- 已移除 SharedBrain 依赖
- 独立子进程管理 + EU 余额监控
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time
from typing import Any, Protocol, runtime_checkable

_log = logging.getLogger(__name__)

# =============================================================================
# 本地 ICliAdapter 协议 (替代 D_Execution 导入)
# =============================================================================


@runtime_checkable
class ICliAdapter(Protocol):
    """CLI 适配器协议 —— 本地定义，不依赖 D_Execution。

    实现此协议的类需提供以下方法:
        spawn_process(persona, task_msg, mcp_server_url) -> subprocess.Popen
        inject_context(process, context) -> bool
        parse_output(process) -> str
        send_halt(process) -> bool
    """

    def spawn_process(self, persona: str, task_msg: str, mcp_server_url: str) -> subprocess.Popen[str]:
        """启动子进程。"""
        ...

    def inject_context(self, process: subprocess.Popen[str], context: dict[str, Any]) -> bool:
        """向运行中的进程注入上下文。"""
        ...

    def parse_output(self, process: subprocess.Popen[str]) -> str:
        """解析进程输出。"""
        ...

    def send_halt(self, process: subprocess.Popen[str]) -> bool:
        """发送停止信号。"""
        ...


# =============================================================================
# Claude Code 适配器
# =============================================================================


class ClaudeCodeAdapter(ICliAdapter):
    """Claude Code CLI 适配器。

    管理 Claude Code 子进程，包括 EU 余额监控、上下文注入和输出解析。
    不再继承 SharedBrain 基类。
    """

    def __init__(self, eu_check_interval: int = 30) -> None:
        self._eu_check_interval = eu_check_interval
        self._running_monitors: dict[int, threading.Thread] = {}

    # ── EU 余额监控 ──

    def _eu_monitor_thread(self, process: subprocess.Popen[str], agent_id: str) -> None:
        """后台线程：定期检查 EU 余额，耗尽时终止进程。"""
        while process.poll() is None:
            time.sleep(self._eu_check_interval)
            balance = self._query_eu_balance()
            if balance is not None and balance <= 0:
                _log.warning("EU balance depleted for agent %s (pid=%d), halting...", agent_id, process.pid)
                self.send_halt(process)
                break

    def _query_eu_balance(self) -> float | None:
        """查询 EU 余额。默认返回 None (余额检查不可用)。"""
        return None

    # ── 进程管理 ──

    def spawn_process(self, persona: str, task_msg: str, mcp_server_url: str) -> subprocess.Popen[str]:
        """启动 Claude Code 子进程。

        Args:
            persona: BOS persona 标识
            task_msg: 任务消息
            mcp_server_url: MCP 服务端 URL

        Returns:
            已启动的 subprocess.Popen 实例。
        """
        env = os.environ.copy()
        env["MCP_SERVER_URL"] = mcp_server_url
        env["BOS_PERSONA"] = persona
        env["BOS_TASK"] = task_msg

        cmd = ["claude", "--mcp-server", mcp_server_url, "-p", task_msg]

        process = subprocess.Popen(
            cmd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        monitor = threading.Thread(
            target=self._eu_monitor_thread,
            args=(process, persona),
            daemon=True,
            name=f"claude-eu-monitor-{process.pid}",
        )
        monitor.start()
        self._running_monitors[process.pid] = monitor
        _log.info("Spawned Claude Code process (pid=%d) for persona=%s", process.pid, persona)
        return process

    def inject_context(self, process: subprocess.Popen[str], context: dict[str, Any]) -> bool:
        """向运行中的进程注入附加上下文。

        Args:
            process: 目标子进程
            context: 要注入的上下文键值对

        Returns:
            注入成功返回 True。
        """
        if not context:
            return False

        context_str = "\n".join(f"{k}: {v}" for k, v in context.items())
        inject_msg = f"\n\n[BOS CONTEXT INJECTION]\n{context_str}\n[END CONTEXT]\n"

        try:
            process.stdin.write(inject_msg)  # type: ignore[union-attr]
            process.stdin.flush()  # type: ignore[union-attr]
            return True
        except (OSError, BrokenPipeError):
            return False

    def parse_output(self, process: subprocess.Popen[str]) -> str:
        """读取进程标准输出（最多等待 60 秒）。

        Args:
            process: 目标子进程

        Returns:
            标准输出字符串。
        """
        try:
            stdout, _ = process.communicate(timeout=60)
            return stdout if stdout else ""
        except subprocess.TimeoutExpired:
            return ""

    def send_halt(self, process: subprocess.Popen[str]) -> bool:
        """发送 SIGTERM 停止进程组。

        Args:
            process: 目标子进程

        Returns:
            成功返回 True。
        """
        try:
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGTERM)
            return True
        except (ProcessLookupError, PermissionError):
            try:
                process.terminate()
                return True
            except OSError:
                return False

    def cleanup_monitors(self) -> None:
        """清理所有已终止进程的监控线程。"""
        dead_pids = [pid for pid, t in self._running_monitors.items() if not t.is_alive()]
        for pid in dead_pids:
            self._running_monitors.pop(pid, None)
            _log.debug("Cleaned up monitor for pid=%d", pid)

    @property
    def active_process_count(self) -> int:
        """当前活跃的监控进程数。"""
        self.cleanup_monitors()
        return len(self._running_monitors)
