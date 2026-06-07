"""P48-W0 runtime serve dispatcher — 让 `python -m runtime serve --action X` 工作.

协议 (stdio JSON-RPC 简化, P33-W4 同模式):
  - 客户端写: {"action": "X", "args": {...}}\\n
  - 服务端响应: {"status": "ok", "result": ...}\\n 或 {"status": "error", "error": "..."}\\n
  - 客户端关闭: {"action": "QUIT"}\\n
  - 服务端退出: EOF on stdin

4 actions 分发 (P46 4 URI):
  - agent-list  → AgentHub.list_all()
  - chat        → AgentRunner.run() (stub)
  - run-task    → AgentExecutor.execute() (stub)
  - task-status → AgentHub.list_all() (POC: status = registered agents 列表)
"""
from __future__ import annotations

import json
import sys
from typing import Any


def _call_action(action: str, args: dict[str, Any]) -> dict[str, Any]:
    """P48-W0: action → module method 分发."""
    try:
        if action == "agent-list":
            from runtime.executor.agent_hub import AgentHub  # type: ignore[import-not-found]

            hub = AgentHub()
            return {
                "status": "ok",
                "result": {"agents": [a.to_dict() for a in hub.list_all()]},
            }
        if action == "chat":
            from runtime.executor.core.agent_runner import AgentRunner  # type: ignore[import-not-found]

            _runner = AgentRunner()  # noqa: F841
            query = args.get("query", args.get("message", ""))
            return {
                "status": "ok",
                "result": {"response": f"[POC runner] received: {query}"},
            }
        if action == "run-task":
            from runtime.executor.core.agent_executor import AgentExecutor  # type: ignore[import-not-found]

            _executor = AgentExecutor()  # noqa: F841
            task = args.get("task", args.get("name", ""))
            return {
                "status": "ok",
                "result": {"task_id": f"task-{hash(task) % 10000}", "status": "queued"},
            }
        if action == "task-status":
            from runtime.executor.agent_hub import AgentHub  # type: ignore[import-not-found]

            hub = AgentHub()
            return {
                "status": "ok",
                "result": {"tasks": [a.to_dict() for a in hub.list_all()]},
            }
        return {"status": "error", "error": f"unknown action: {action}"}
    except Exception as exc:
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def serve() -> int:
    """P48-W0: serve 模式入口, stdio JSON-RPC."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line == "QUIT":
            break
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            sys.stdout.write(
                json.dumps({"status": "error", "error": f"json_decode: {exc}"}) + "\n"
            )
            sys.stdout.flush()
            continue
        action = req.get("action", "")
        args = req.get("args", {}) or {}
        resp = _call_action(action, args)
        sys.stdout.write(json.dumps(resp, ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()
    return 0


__all__ = ["serve", "_call_action"]
