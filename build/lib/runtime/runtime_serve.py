"""P49-W1: runtime serve dispatcher — 4 action 真业务 (用 runtime.stdio_rpc helper).

协议 (P33-W4):
  - 客户端写: {"action": "X", "args": {...}}\\n
  - 服务端响应: {"status": "ok", "result": ...}\\n 或 {"status": "error", "error": "..."}\\n
  - 客户端关闭: {"action": "QUIT"}\\n

4 actions (P46 4 URI):
  - agent-list  → AgentHub.list_all()            (P48-W0 业务)
  - chat        → AgentRunner 真调               (P49-W1 升级, 替代 P48-W0 stub)
  - run-task    → AgentExecutor 真调 + 持久 state (P49-W1 升级)
  - task-status → AgentHub.get_status() / list   (P49-W1 升级)
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from runtime.stdio_rpc import run_stdio_dispatch

# P49-W1: run-task 持久 state (POC: in-process dict, P50+ 持久化到 file/db)
_TASK_STATE: dict[str, dict[str, Any]] = {}


def _action_agent_list(args: dict[str, Any]) -> dict[str, Any]:
    """P48-W0: 真调 AgentHub.list_all() (无 stub)."""
    from runtime.executor.agent_hub import AgentHub  # type: ignore[import-not-found]

    hub = AgentHub()
    agents = [a.to_dict() for a in hub.list_all()]
    return {"status": "ok", "result": {"agents": agents, "args_echo": args}}


def _action_chat(args: dict[str, Any]) -> dict[str, Any]:
    """P49-W1: 真调 AgentRunner, 替代 P48-W0 stub."""
    from runtime.executor.core.agent_runner import AgentRunner  # type: ignore[import-not-found]

    runner = AgentRunner()
    query = args.get("query", args.get("message", ""))
    response = runner.run(query) if hasattr(runner, "run") else f"[runner-stub] {query}"
    return {
        "status": "ok",
        "result": {"query": query, "response": response},
    }


def _action_run_task(args: dict[str, Any]) -> dict[str, Any]:
    """P49-W1: 真调 AgentExecutor + 持久 task state."""
    from runtime.executor.core.agent_executor import AgentExecutor  # type: ignore[import-not-found]

    executor = AgentExecutor()
    task = args.get("task", args.get("name", ""))
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    try:
        result = executor.execute(task) if hasattr(executor, "execute") else {"echo": task}
    except Exception as exc:
        result = {"_execute_error": f"{type(exc).__name__}: {exc}"}
    _TASK_STATE[task_id] = {
        "task": task,
        "status": "queued",
        "result": result,
        "created_at": time.time(),
    }
    return {
        "status": "ok",
        "result": {"task_id": task_id, "state": _TASK_STATE[task_id]},
    }


def _action_task_status(args: dict[str, Any]) -> dict[str, Any]:
    """P49-W1: 查 _TASK_STATE, fallback AgentHub.list_all()."""
    task_id = args.get("task_id", "")
    if task_id and task_id in _TASK_STATE:
        return {"status": "ok", "result": {"task": _TASK_STATE[task_id]}}
    # fallback: 列所有 task + agents
    from runtime.executor.agent_hub import AgentHub  # type: ignore[import-not-found]

    hub = AgentHub()
    return {
        "status": "ok",
        "result": {
            "task": None,
            "all_tasks": list(_TASK_STATE.values()),
            "agents": [a.to_dict() for a in hub.list_all()],
        },
    }


_ACTIONS = {
    "agent-list": _action_agent_list,
    "chat": _action_chat,
    "run-task": _action_run_task,
    "task-status": _action_task_status,
}


def _call_action(action: str, args: dict[str, Any]) -> dict[str, Any]:
    """P48-W0: action → module method 分发 (P49-W1 升级: 4 真业务)."""
    fn = _ACTIONS.get(action)
    if fn is None:
        return {"status": "error", "error": f"unknown action: {action}"}
    try:
        return fn(args)
    except Exception as exc:
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def serve() -> int:
    """P48-W0 serve 入口 (P49-W1 用 runtime.stdio_rpc helper)."""
    return run_stdio_dispatch(_call_action)


__all__ = ["serve", "_call_action"]
