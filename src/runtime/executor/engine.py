"""Agent Runtime 核心引擎 — 无状态任务执行引擎。

原则：
1. 固定模型 (不跟随默认配置切换)
2. 不处理对话管理 (只做单次任务)
3. 所有工具通过 HTTP/MCP 调用 (不依赖 Hermes)
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from runtime.executor.config import (
    DEFAULT_MODEL,
    EXEC_LOG_FILE,
    WORKSPACE,
    log,
)
from runtime.executor.tools import Tools


def _log_execution(task_id: str, status: str, summary: str, result: dict, duration_sec: float):
    """写入执行日志到 JSONL 文件。"""
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "task_id": task_id,
        "status": status,
        "summary": summary[:500],
        "turns": result.get("turns", 0),
        "tokens_used": result.get("usage", {}).get("total_tokens", 0),
        "duration_sec": round(duration_sec, 2),
    }
    with open(EXEC_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _build_alert_message(task_id: str, result: dict) -> str:
    """构建失败告警消息。"""
    error = result.get("error", "unknown error")
    turns = result.get("turns", 0)
    usage = result.get("usage", {})
    tokens = usage.get("total_tokens", 0)
    summary = (result.get("result") or "")[:200]
    lines = [
        "⚠️ Agent Runtime 任务失败",
        f"任务: {task_id}",
        f"错误: {error}",
        f"轮次: {turns} | Token: {tokens}",
    ]
    if summary:
        lines.append(f"摘要: {summary}")
    return "\n".join(lines)


class AgentRuntime:
    """简化版任务执行引擎。

    接收 prompt → LLM 推理 → 工具编排 → 返回结果。
    """

    def __init__(self, model: str | None = None):
        self.model = model or DEFAULT_MODEL
        self.tools = Tools()
        self._tool_registry = self.tools.build_tool_registry()

    def _call_llm(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """调用 LLM API。使用 llm_gateway 统一网关。"""
        import asyncio

        from llm_gateway.detection import detect_backends
        from llm_gateway.provider import LLMRequest, ToolSchema

        providers = detect_backends()
        if not providers:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [],
                "finish_reason": "error",
                "error": "No LLM backend available via llm-gateway.",
            }

        provider = providers[0]

        mapped_tools = None
        if tools:
            mapped_tools = []
            for t in tools:
                if "function" in t:
                    f = t["function"]
                    mapped_tools.append(ToolSchema(
                        name=f["name"],
                        description=f.get("description", ""),
                        parameters=f.get("parameters", {})
                    ))

        try:
            system_prompt = ""
            prompt = ""
            context: list[dict[str, Any]] = []

            for idx, message in enumerate(messages):
                role = message.get("role", "")
                content = message.get("content", "")
                if idx == 0 and role == "system":
                    system_prompt = content
                    continue
                if role == "user":
                    prompt = content
                else:
                    context.append(message)

            req = LLMRequest(
                model=self.model or provider.default_model,
                prompt=prompt,
                system_prompt=system_prompt,
                context=context,
                metadata={"tools": mapped_tools or []},
            )
            resp = asyncio.run(provider.generate(req))

            tool_calls = getattr(resp, "tool_calls", None) or []
            usage = getattr(resp, "usage", None)
            if usage is None:
                usage = {
                    "prompt_tokens": getattr(resp, "input_tokens", 0),
                    "completion_tokens": getattr(resp, "output_tokens", 0),
                    "total_tokens": getattr(resp, "input_tokens", 0) + getattr(resp, "output_tokens", 0),
                }

            result = {
                "role": "assistant",
                "content": resp.content,
                "tool_calls": [],
                "finish_reason": getattr(resp, "finish_reason", "stop") or "stop",
                "usage": usage,
            }

            if tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    } for tc in tool_calls
                ]
                result["finish_reason"] = "tool_calls"

            return result
        except Exception as e:
            log.error(f"LLM Gateway error: {e}")
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [],
                "finish_reason": "error",
                "error": str(e),
            }

    def _execute_tool(self, tool_call: dict) -> dict:
        """执行单个工具调用。"""
        fn_name = tool_call.get("function", {}).get("name", "")
        try:
            args = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {}

        tool_info = self._tool_registry.get(fn_name)
        if not tool_info:
            return {"role": "tool", "tool_call_id": tool_call.get("id", ""), "content": f"Unknown tool: {fn_name}"}

        log.info(f"  🔧 Tool: {fn_name}")
        result = tool_info["fn"](**args)
        return {
            "role": "tool",
            "tool_call_id": tool_call.get("id", ""),
            "content": json.dumps(result, ensure_ascii=False)[:5000],
        }

    def run_task(self, prompt: str, tools_enabled: list[str] | None = None, context: dict | None = None) -> dict:
        """执行一个任务。返回最终结果。"""
        log.info(f"🎯 Task starting (model={self.model})")

        system_prompt = (
            "You are an AI task executor. Execute the user's request step by step.\n"
            "You have access to tools. Use them when needed.\n"
            "IMPORTANT: If a file or command references '~/Workspace/', "
            f"always expand it to '{WORKSPACE}/'.\n"
            "After completing all steps, provide a clear summary of what was done.\n"
            "Respond in Chinese unless otherwise specified.\n"
            "If the task has nothing to report (everything is fine), "
            "output exactly '[SILENT]' at the end of your response."
        )

        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.append(
                {"role": "user", "content": f"Context:\n{json.dumps(context, ensure_ascii=False, indent=2)}"}
            )
        messages.append({"role": "user", "content": prompt})

        schemas = self.tools.build_tool_schemas()
        if tools_enabled:
            schemas = [s for s in schemas if s["function"]["name"] in tools_enabled]
        tools = schemas if schemas else None

        max_turns = 30
        all_tool_calls: list[dict[str, Any]] = []
        usage = {}

        for turn in range(max_turns):
            response = self._call_llm(messages, tools=tools)
            finish = response.get("finish_reason", "stop")

            if response.get("error"):
                return {"error": response["error"], "result": ""}

            if response.get("usage"):
                usage = response["usage"]

            assistant_msg = dict(response)
            assistant_msg.pop("finish_reason", None)
            assistant_msg.pop("usage", None)
            assistant_msg.pop("error", None)
            messages.append(assistant_msg)
            tcs = response.get("tool_calls", [])

            if finish == "stop" or not tcs:
                result = response.get("content", "")
                log.info(f"✅ Task done (turn={turn + 1}, tokens={usage.get('total_tokens', '?')})")
                return {"result": result, "tool_calls": all_tool_calls, "turns": turn + 1, "usage": usage}

            for tc in tcs:
                tool_result = self._execute_tool(tc)
                messages.append(tool_result)
                all_tool_calls.append(
                    {
                        "name": tc.get("function", {}).get("name", ""),
                        "result": tool_result["content"][:200],
                    }
                )

            if finish == "error":
                break

        return {
            "result": messages[-1].get("content", "") if messages else "",
            "tool_calls": all_tool_calls,
            "turns": max_turns,
            "usage": usage,
            "truncated": True,
        }


# ── API key 解析（从多个来源） ──────────────────────────────────────────────


def _get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _resolve_api_key() -> str:
    """Resolve API key using the historical precedence order."""
    for key in ("AGENT_RUNTIME_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"):
        value = _get_env(key).strip()
        if value:
            return value

    home = Path.home()
    for path in (
        home / ".config" / "agent-runtime" / "api_key",
        home / ".agent-runtime" / "api_key",
        home / ".deepseek" / "api_key",
        home / ".openai" / "api_key",
    ):
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value

    return ""
