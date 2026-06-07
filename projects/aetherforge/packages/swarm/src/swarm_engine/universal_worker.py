from __future__ import annotations

# ruff: noqa: RUF001, RUF002, RUF003

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md
Layer: L3
---
"""


from pathlib import Path

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Microkernel_Component ≡ System_Bus
# 内涵 ≝ {Routing, Scheduling, Communication}
# 外延 ≝ {m | m ∈ Z-Microkernel ∧ orchestrates(m, Communication)}
# 功能 ⊢ {RouteMessages, ScheduleTasks, ManageBus}
# =============================================================================

"""
---
Type: Framework
Status: ACTIVE
Version: 3.0.0
Owner: '@Kiro'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-05_microkernel_fractal_axiom.md
Layer: L3-Execution
Created: 2026-02-18
Updated: 2026-03-07
Constraint: "[!!] CONFIGURATION_DRIVEN | [!!] EXECUTION_HANDLERS"
Summary: 通用 Worker 引擎 — 配置驱动的动态 worker 管理，支持 direct_exec、subprocess、python、MCP 执行模式
Tags:
  - framework
  - universal-worker
  - execution-engine
  - configuration-driven
  - multi-handler
---

🌐 通用 Worker 引擎 (Universal Worker Engine)

职责: 基于配置文件动态创建和管理 worker 实例
集成: worker_profile.py + agent_daemon_base.py
执行模式: direct_exec (shell) | subprocess (args) | python (exec) | mcp_bridge
"""

import logging
import os
import subprocess
import threading
import time
from typing import Any

import yaml

from .organs.engine.agent_daemon_base import AgentDaemonBase  # type: ignore[import-not-found]
from .organs.worker_profile import WORKER_REGISTRY, get_worker_profile  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)
HAS_WORKER_PROFILE = True


class UniversalWorker(AgentDaemonBase):
    """配置驱动的通用 Worker 实现"""

    def __init__(self, config: dict[str, Any]) -> None:
        """
        从配置字典初始化 worker

        Args:
            config: worker 配置字典（从 workers.yaml 加载）
        """
        # 如果有 WorkerProfile，优先使用
        worker_id = config.get("id", config.get("worker_id", "unknown"))

        if HAS_WORKER_PROFILE and worker_id in WORKER_REGISTRY:
            profile = get_worker_profile(worker_id, overrides=config)
            profile_dict = profile.to_dict()
            # 合并配置
            config = {**profile_dict, **config}

        # 提取能力列表
        capabilities = self._extract_capabilities(config)

        super().__init__(
            agent_id=worker_id,
            persona=config.get("persona", config.get("archetype", "Generic Worker")),
            capabilities=capabilities,
            heartbeat_interval=config.get("heartbeat_interval", 10.0),
            poll_interval=config.get("poll_interval", 2.0),
        )

        self.config = config
        self.max_concurrency = config.get("max_concurrency", config.get("max_parallel_tasks", 1))
        self.trust_score = config.get("trust_score", 50)
        self.handler_type = config.get("handler", {}).get("type", "mcp_bridge")
        self.endpoint = config.get("handler", {}).get("endpoint", self.agent_id)

        _log.info("[*] {self.agent_id} initialized (trust_score: {self.trust_score})")
        _log.info("    Persona: {self.persona}")
        _log.info("    Capabilities: {', '.join(self.capabilities)}")
        _log.info("    Handler: {self.handler_type} -> {self.endpoint}")

    def _extract_capabilities(self, config: dict) -> list[str]:
        """从配置中提取能力列表"""
        caps = config.get("capabilities", {})
        if isinstance(caps, dict):
            # 格式: {"能力名": 等级} → 转换为通配符模式
            return [f"{name}" if "*" in name else f"{name}.*" for name in caps.keys()]
        elif isinstance(caps, list):
            # 格式: ["能力1", "能力2"]
            return caps
        return ["generic.*"]

    def process_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        处理任务的通用逻辑

        MCP 桥接模式：将任务转发到实际的 IDE/CLI 实例
        """
        _log.info("[>] {self.agent_id} processing task")
        _log.info("    Summary: {payload.get('summary', 'N/A')}")
        _log.info("    Phase: {payload.get('phase', 'N/A')}")

        if self.handler_type == "mcp_bridge":
            return self._handle_mcp_bridge(payload)
        elif self.handler_type == "direct_exec":
            return self._handle_direct_exec(payload)
        elif self.handler_type == "subprocess":
            return self._handle_subprocess(payload)
        elif self.handler_type == "python":
            return self._handle_python(payload)
        else:
            # fallback to mcp_bridge
            return self._handle_mcp_bridge(payload)

    def _handle_mcp_bridge(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        MCP 桥接模式：将任务转发到实际的 IDE/CLI 实例

        在这个模式下，daemon 只是一个"代理"
        实际的任务处理由 IDE/CLI 实例完成
        """
        _log.info("[→] Task forwarded to {self.endpoint}")

        # 返回成功，表示任务已接收
        return {
            "status": "FORWARDED",
            "endpoint": self.endpoint,
            "agent_id": self.agent_id,
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------
    # Real execution handlers
    # ------------------------------------------------------------------

    # 允许的命令白名单（可扩展）
    _ALLOWED_COMMANDS: frozenset[str] = frozenset(
        {
            "ls",
            "cat",
            "echo",
            "pwd",
            "cd",
            "mkdir",
            "rmdir",
            "cp",
            "mv",
            "rm",
            "find",
            "grep",
            "awk",
            "sed",
            "sort",
            "uniq",
            "wc",
            "head",
            "tail",
            "diff",
            "cmp",
            "stat",
            "file",
            "dirname",
            "basename",
            "realpath",
            "python3",
            "python",
            "node",
            "ruby",
            "perl",
            "bash",
            "sh",
            "zsh",
            "sleep",
            "kill",
            "date",
            "uptime",
            "df",
            "free",
            "uname",
            "hostname",
            "id",
            "whoami",
            "ps",
            "top",
        }
    )

    # 危险 shell metacharacters（命令注入检测）
    _DANGEROUS_CHARS = frozenset(";|&$`\\\"'<>(){}[]!#*?")

    def _is_command_safe(self, command: str) -> tuple[bool, str]:
        """验证命令安全性。

        Returns:
            (is_safe, error_message)
        """
        import shlex

        # 提取第一个 token 作为命令名
        parts = shlex.split(command, posix=True)
        if not parts:
            return False, "Empty command"

        cmd_name = parts[0]
        # 支持绝对路径命令（如 /usr/bin/python3）
        cmd_base = cmd_name.split("/")[-1] if "/" in cmd_name else cmd_name

        if cmd_base not in self._ALLOWED_COMMANDS:
            return False, f"Command '{cmd_base}' not in whitelist"

        # 检查危险字符
        if any(char in command for char in self._DANGEROUS_CHARS):
            # 允许 | (管道) 和 && (组合) 在特定情况下
            # 但拒绝 ; & $ ` 等直接 shell 注入
            dangerous_found = set(command) & set("$`\\\"';&|<>")
            if dangerous_found:
                return False, f"Dangerous characters found: {dangerous_found!r}"

        return True, ""

    def _handle_direct_exec(self, payload: dict[str, Any]) -> dict[str, Any]:
        """直接执行 shell 命令 (shell=True)，带输入验证"""
        command = payload["command"]
        cwd = payload.get("cwd", ".")
        timeout = payload.get("timeout", 30)

        # 安全验证
        is_safe, error_msg = self._is_command_safe(command)
        if not is_safe:
            _log.warning("[!] direct_exec blocked: %s (command=%r)", error_msg, command)
            return {
                "status": "FAILED",
                "stdout": "",
                "stderr": f"Command rejected: {error_msg}",
                "returncode": -1,
                "agent_id": self.agent_id,
                "timestamp": time.time(),
            }

        _log.info("[>] direct_exec: %s (cwd=%s, timeout=%ss)", command, cwd, timeout)
        try:
            result = subprocess.run(  # noqa: S602
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
            status = "SUCCESS" if result.returncode == 0 else "FAILED"
            return {
                "status": status,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "agent_id": self.agent_id,
                "timestamp": time.time(),
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "FAILED",
                "stdout": "",
                "stderr": f"TimeoutExpired after {timeout}s",
                "returncode": -1,
                "agent_id": self.agent_id,
                "timestamp": time.time(),
            }
        except (subprocess.SubprocessError, OSError) as exc:
            return {
                "status": "FAILED",
                "stdout": "",
                "stderr": str(exc),
                "returncode": -1,
                "agent_id": self.agent_id,
                "timestamp": time.time(),
            }

    def _handle_subprocess(self, payload: dict[str, Any]) -> dict[str, Any]:
        """执行带参数列表的子进程 (shell=False)"""
        args = payload["args"]
        extra_env = payload.get("env", {})
        timeout = payload.get("timeout", 60)

        merged_env = {**os.environ, **extra_env}
        _log.info("[>] subprocess: %s (timeout=%ss)", args, timeout)
        try:
            result = subprocess.run(  # noqa: S603
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=merged_env,
            )
            status = "SUCCESS" if result.returncode == 0 else "FAILED"
            return {
                "status": status,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "agent_id": self.agent_id,
                "timestamp": time.time(),
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "FAILED",
                "stdout": "",
                "stderr": f"TimeoutExpired after {timeout}s",
                "returncode": -1,
                "agent_id": self.agent_id,
                "timestamp": time.time(),
            }
        except (subprocess.SubprocessError, OSError) as exc:
            return {
                "status": "FAILED",
                "stdout": "",
                "stderr": str(exc),
                "returncode": -1,
                "agent_id": self.agent_id,
                "timestamp": time.time(),
            }

    def _handle_python(self, payload: dict[str, Any]) -> dict[str, Any]:
        """在沙箱中执行 Python 代码，捕获 stdout"""
        code = payload["code"]
        _log.info("[>] python exec (%d chars)", len(code))

        # Security: Use centralized sandbox execution
        from .organs.security_utils import safe_exec_sandbox  # type: ignore[import-not-found]

        exec_result = safe_exec_sandbox(code, capture_stdout=True)

        if exec_result["success"]:
            return {
                "status": "SUCCESS",
                "output": exec_result["output"],
                "error": "",
                "agent_id": self.agent_id,
                "timestamp": time.time(),
            }
        else:
            return {
                "status": "FAILED",
                "output": exec_result["output"],
                "error": exec_result["error"],
                "agent_id": self.agent_id,
                "timestamp": time.time(),
            }

    def get_health_report(self) -> dict[str, Any]:
        """返回 worker 健康状态报告"""
        state: str
        if not self.running:
            state = "STOPPED"
        elif self.current_load > 0:
            state = "RUNNING"
        else:
            state = "IDLE"

        return {
            "agent_id": self.agent_id,
            "state": state,
            "handler_type": self.handler_type,
            "capabilities": self.capabilities,
            "current_load": self.current_load,
            "max_concurrency": self.max_concurrency,
            "endpoint": self.endpoint,
            "timestamp": time.time(),
        }


class WorkerManager:
    """Worker 管理器：加载配置并启动所有 workers"""

    def __init__(self, config_path: str = "Z-Microkernel/config/workers.yaml") -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.workers: list[UniversalWorker] = []
        self.threads: list[threading.Thread] = []

    def _load_config(self) -> dict[str, Any]:
        """加载 YAML 配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def start_all(self) -> None:
        """启动所有配置的 workers"""
        _log.info("[*] Loading workers from {self.config_path}")
        _log.info("[*] Registry DB: {self.config.get('registry_db', 'N/A')}")
        _log.info("[*] MCP DB: {self.config.get('mcp_db', 'N/A')}")
        # (blank line removed)

        for worker_config in self.config.get("workers", []):
            worker = UniversalWorker(worker_config)
            self.workers.append(worker)

            # 在独立线程中启动每个 worker
            thread = threading.Thread(target=worker.run, daemon=True, name=f"Worker-{worker.agent_id}")
            thread.start()
            self.threads.append(thread)
            _log.info("[+] {worker.agent_id} started in background thread")
            # (blank line removed)

        _log.info("[*] All {len(self.workers)} workers started")
        _log.info("[*] Press Ctrl+C to stop all workers")
        # (blank line removed)

        # 主线程保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            _log.info("\n[*] Shutting down all workers...")
            self.stop_all()

    def start_worker(self, worker_id: str) -> UniversalWorker | None:
        """启动单个 worker"""
        worker_config = next((w for w in self.config.get("workers", []) if w.get("id") == worker_id), None)

        if not worker_config:
            _log.info("[!] Worker '{worker_id}' not found in config")
            return None

        worker = UniversalWorker(worker_config)
        self.workers.append(worker)

        # 在独立线程中启动
        thread = threading.Thread(target=worker.run, daemon=True, name=f"Worker-{worker.agent_id}")
        thread.start()
        self.threads.append(thread)

        _log.info("[+] {worker.agent_id} started")
        return worker

    def stop_all(self) -> None:
        """停止所有 workers"""
        for worker in self.workers:
            worker.stop()
        _log.info("[*] All workers stopped")

    def get_status(self) -> dict[str, Any]:
        """获取所有 workers 的状态"""
        workers_list: list[dict[str, Any]] = []
        status: dict[str, Any] = {"total_workers": len(self.workers), "workers": workers_list}

        for worker in self.workers:
            workers_list.append(
                {
                    "id": worker.agent_id,
                    "persona": worker.persona,
                    "running": worker.running,
                    "current_load": worker.current_load,
                    "max_concurrency": worker.max_concurrency,
                    "instance_id": worker.instance_id,
                }
            )

        return status


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Universal Worker Manager")
    parser.add_argument(
        "--config",
        default="Z-Microkernel/config/workers.yaml",
        help="Path to workers.yaml config file",
    )
    parser.add_argument("--worker", help="Start only specific worker by ID")
    parser.add_argument("--status", action="store_true", help="Show worker status")

    args = parser.parse_args()

    manager = WorkerManager(args.config)

    if args.status:
        # 显示状态
        status = manager.get_status()
        _log.info("\n{'=' * 60}")
        _log.info("Worker Status")
        _log.info("{'=' * 60}")
        _log.info("Total Workers: {status['total_workers']}")
        # (blank line removed)
        for _w in status["workers"]:
            _log.info("  {w['id']}")
            _log.info("    Persona: {w['persona']}")
            _log.info("    Running: {w['running']}")
            _log.info("    Load: {w['current_load']}/{w['max_concurrency']}")
            # (blank line removed)
    elif args.worker:
        # 启动单个 worker
        worker = manager.start_worker(args.worker)
        if worker:
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                _log.info("\n[*] Stopping worker...")
                worker.stop()
    else:
        # 启动所有 workers
        manager.start_all()
