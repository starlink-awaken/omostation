"""Agent Runtime 核心引擎 — 无状态任务执行引擎。

原则：
1. 固定模型 (不跟随默认配置切换)
2. 不处理对话管理 (只做单次任务)
3. 所有工具通过 HTTP/MCP 调用 (不依赖 Hermes)
"""

import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from runtime.executor.config import (
    DEFAULT_MODEL,
    EXEC_LOG_FILE,
    WORKSPACE,
    log,
)
from runtime.executor.io import AppendOnlyLog
from runtime.executor.io_schemas import ExecutorLogRecord
from runtime.executor.matrix_bridge import report_execution
from runtime.executor.tools import Tools


OMO_DEBT_DIR = WORKSPACE / ".omo" / "debt" / "items"


def _runtime_role_for_llm(tools: list[dict] | None = None) -> str:
    configured = os.environ.get("RUNTIME_LLM_ROLE", "").strip()
    if configured:
        return configured
    return "planner" if tools else "operator"


def _runtime_required_capabilities(tools: list[dict] | None = None) -> list[str]:
    capabilities = ["chat"]
    if tools:
        capabilities.append("tool_use")
    return capabilities


def _resolve_llm_provider_and_model(requested_model: str | None, tools: list[dict] | None = None) -> tuple[Any | None, str | None, dict[str, Any]]:
    from llm_gateway.detection import detect_backends
    from llm_gateway.registry_data_loader import route_role_request

    providers = [provider for provider in detect_backends() if getattr(provider, "provider_name", "") != "none"]
    route_role = _runtime_role_for_llm(tools)
    required_capabilities = _runtime_required_capabilities(tools)
    route_info: dict[str, Any] = {
        "role": route_role,
        "required_capabilities": required_capabilities,
        "selection_mode": "registry_route",
        "fallback_used": False,
    }

    if not providers:
        route_info["selection_mode"] = "no_provider_available"
        return None, None, route_info

    providers_by_name = {provider.provider_name: provider for provider in providers}
    selection = route_role_request(route_role, required_capabilities=required_capabilities)
    if selection is not None:
        route_info["selected_provider"] = selection.provider_name
        route_info["selected_model"] = selection.model.id
        route_info["selection_reasoning"] = selection.reasoning
    else:
        route_info["selected_provider"] = None
        route_info["selected_model"] = None
        route_info["selection_reasoning"] = "No registry route matched"

    provider = providers[0]
    routed_model: str | None = None
    if selection is not None and selection.provider_name in providers_by_name:
        provider = providers_by_name[selection.provider_name]
        routed_model = selection.model.name
    else:
        route_info["fallback_used"] = True
        route_info["fallback_provider"] = provider.provider_name
        route_info["fallback_model"] = getattr(provider, "default_model", None)

    explicit_model = requested_model if requested_model and requested_model != DEFAULT_MODEL else None
    if explicit_model:
        route_info["explicit_model_override"] = explicit_model
        if "/" in explicit_model:
            provider_name, model_name = explicit_model.split("/", 1)
            if provider_name in providers_by_name:
                provider = providers_by_name[provider_name]
                return provider, model_name, route_info
        return provider, explicit_model, route_info

    return provider, routed_model, route_info


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def _sanitize_debt_suffix(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").upper()
    return cleaned[:48] or "UNNAMED"


def _register_budget_debt(task_id: str, role: str, model: str, budget_usd: float, estimated_cost_usd: float) -> Path:
    """Register (or refresh) a budget-rejection debt.

    Reuse policy: the same task_id always maps to the same debt file. Repeated
    triggers do not accumulate new debt entries; instead the existing file is
    refreshed in place and ``last_seen_at`` / ``occurrence_count`` are bumped.
    This prevents the items/ directory from filling with redundant entries when
    audit demos or steady-state traffic keep hitting the same reject path.

    Concurrency: the read-modify-write loop is wrapped in ``fcntl.flock`` on a
    sidecar lock file. Without this, two runtime agents racing on the same
    task_id could each read occurrence_count=N and both write N+1, losing one
    increment. The lock file lives next to the debt yaml and is created on
    demand. The same ``_append_jsonl`` pattern (acquire before mutate, release
    after fsync) is the established convention in this codebase.

    Safety: the YAML body is constructed via ``yaml.safe_dump`` instead of
    string concatenation so that task_id / role / model values containing
    YAML metacharacters (``:``, ``#``, newlines, leading ``-``) cannot break
    the file. This is the same hardening as the LLM audit trail in
    ``llm_gateway.audit``.
    """
    import fcntl

    import yaml

    debt_id = f"DEBT-OPC-P4-BUDGET-{_sanitize_debt_suffix(task_id)}"
    debt_path = OMO_DEBT_DIR / f"{debt_id}.yaml"
    lock_path = debt_path.with_suffix(".lock")
    debt_path.parent.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    occurrence_count = 1
    first_seen_at = now_iso
    with open(lock_path, "w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            if debt_path.exists():
                try:
                    existing = yaml.safe_load(debt_path.read_text(encoding="utf-8")) or {}
                    if isinstance(existing, dict):
                        if "occurrence_count" in existing:
                            try:
                                occurrence_count = int(existing["occurrence_count"]) + 1
                            except (TypeError, ValueError):
                                pass
                        if "first_seen_at" in existing:
                            first_seen_at = str(existing["first_seen_at"]).strip('"')
                except (OSError, ValueError, yaml.YAMLError):
                    pass
            payload = {
                "id": debt_id,
                "title": "OPC P4 budget policy rejected an LLM execution path",
                "description": (
                    f"Runtime executor blocked task `{task_id}` before provider call because\n"
                    f"  estimated cost {estimated_cost_usd:.6f} USD exceeded budget {budget_usd:.6f} USD.\n"
                    f"  role={role}, model={model}."
                ),
                "severity": "medium",
                "source": "runtime",
                "first_seen_at": first_seen_at,
                "registered_at": first_seen_at,
                "last_seen_at": now_iso,
                "occurrence_count": occurrence_count,
                "status": "open",
                "prerequisite_for": "OPC-P4",
                "remediation": (
                    "1. Increase the task budget or select a cheaper route.\n"
                    "2. Re-run after confirming the selected model aligns with policy."
                ),
            }
            debt_path.write_text(
                yaml.safe_dump(payload, allow_unicode=True, sort_keys=False) + "\n",
                encoding="utf-8",
            )
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    return debt_path


def _maybe_enforce_budget(
    *,
    request_context: dict[str, Any] | None,
    provider: Any,
    requested_model: str | None,
    route_info: dict[str, Any],
    messages: list[dict],
) -> dict[str, Any] | None:
    from llm_gateway.registry_data_loader import estimate_model_cost

    context = request_context or {}
    raw_budget = context.get("llm_budget_usd", os.environ.get("RUNTIME_LLM_BUDGET_USD", "")).strip() if isinstance(context.get("llm_budget_usd", ""), str) else context.get("llm_budget_usd", os.environ.get("RUNTIME_LLM_BUDGET_USD", ""))
    if raw_budget in ("", None):
        return None

    budget_usd = float(raw_budget)
    task_id = str(context.get("task_id") or "runtime-task")
    role = route_info.get("role", "operator")
    model_name = requested_model or getattr(provider, "default_model", "unknown")
    provider_name = getattr(provider, "provider_name", "")
    registry_model_id = f"{provider_name}/{model_name}" if provider_name else model_name

    prompt_text = "\n".join(str(message.get("content", "")) for message in messages)
    estimated_input_tokens = _estimate_tokens(prompt_text)
    estimated_output_tokens = int(context.get("llm_max_output_tokens", 512))
    estimated_cost_usd = estimate_model_cost(registry_model_id, estimated_input_tokens, estimated_output_tokens)

    route_info["budget_policy"] = {
        "task_id": task_id,
        "budget_usd": budget_usd,
        "estimated_cost_usd": estimated_cost_usd,
        "model": registry_model_id,
    }
    if estimated_cost_usd <= budget_usd:
        return None

    debt_path = _register_budget_debt(task_id, role, registry_model_id, budget_usd, estimated_cost_usd)
    route_info["budget_policy"]["debt_path"] = str(debt_path)
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [],
        "finish_reason": "error",
        "error": (
            f"Budget policy blocked task {task_id}: estimated {estimated_cost_usd:.6f} USD "
            f"> budget {budget_usd:.6f} USD ({registry_model_id})"
        ),
        "route": route_info,
    }


def _log_execution(task_id: str, status: str, summary: str, result: dict, duration_sec: float):
    """写入执行日志到 JSONL 文件。R51 P0: AppendOnlyLog.append() 替换裸 open()"""
    entry = {
        # Python 3.14 isoformat() 返回 +00:00 而非 Z，用 strftime 硬编码 Z
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task_id": task_id,
        "status": status,
        "summary": summary[:500],
        "turns": result.get("turns", 0),
        "tokens_used": result.get("usage", {}).get("total_tokens", 0),
        "duration_sec": round(duration_sec, 2),
    }
    AppendOnlyLog(str(EXEC_LOG_FILE)).append(entry, schema=ExecutorLogRecord)

    # Bridge to Matrix for observability
    try:
        report_execution(
            task_id=task_id,
            status=status,
            tokens_used=entry["tokens_used"],
            duration_sec=duration_sec,
            error=result.get("error"),
        )
    except Exception:
        pass  # Matrix bridge failure must not break execution logging


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

    def _call_llm(self, messages: list[dict], tools: list[dict] | None = None, request_context: dict | None = None) -> dict:
        """调用 LLM API。使用 llm_gateway 统一网关。"""
        import asyncio

        from llm_gateway.audit import record_llm_audit
        from llm_gateway.provider import LLMRequest, ToolSchema

        provider, requested_model, route_info = _resolve_llm_provider_and_model(self.model, tools=tools)
        if provider is None:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [],
                "finish_reason": "error",
                "error": "No LLM backend available via llm-gateway.",
                "route": route_info,
            }

        budget_error = _maybe_enforce_budget(
            request_context=request_context,
            provider=provider,
            requested_model=requested_model,
            route_info=route_info,
            messages=messages,
        )
        if budget_error is not None:
            return budget_error

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
                model=requested_model or getattr(provider, "default_model", None),
                prompt=prompt,
                system_prompt=system_prompt,
                context=context,
                metadata={"tools": mapped_tools or []},
            )
            started_at = time.perf_counter()
            resp = asyncio.run(provider.generate(req))
            latency_ms = round((time.perf_counter() - started_at) * 1000.0, 3)

            tool_calls = getattr(resp, "tool_calls", None) or []
            usage = getattr(resp, "usage", None)
            if usage is None:
                usage = {
                    "prompt_tokens": getattr(resp, "input_tokens", 0),
                    "completion_tokens": getattr(resp, "output_tokens", 0),
                    "total_tokens": getattr(resp, "input_tokens", 0) + getattr(resp, "output_tokens", 0),
                }

            model_id = f"{getattr(resp, 'provider', getattr(provider, 'provider_name', ''))}/{getattr(resp, 'model', req.model or '')}"
            task_id = str((request_context or {}).get("task_id") or "runtime-task")
            total_cost_usd = 0.0
            try:
                from llm_gateway.registry_data_loader import estimate_model_cost

                total_cost_usd = estimate_model_cost(
                    model_id,
                    int(usage.get("prompt_tokens", 0)),
                    int(usage.get("completion_tokens", 0)),
                )
            except Exception:
                total_cost_usd = 0.0

            record_llm_audit(
                task_id=task_id,
                role=route_info.get("role", "operator"),
                provider=getattr(resp, "provider", getattr(provider, "provider_name", "")),
                model=getattr(resp, "model", req.model or ""),
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
                total_cost_usd=total_cost_usd,
                latency_ms=latency_ms,
                route=route_info,
                metadata={"tool_count": len(mapped_tools or [])},
            )

            result = {
                "role": "assistant",
                "content": resp.content,
                "tool_calls": [],
                "finish_reason": getattr(resp, "finish_reason", "stop") or "stop",
                "usage": usage,
                "provider": getattr(resp, "provider", getattr(provider, "provider_name", "")),
                "model": getattr(resp, "model", req.model or ""),
                "route": route_info,
                "audit": {"task_id": task_id, "latency_ms": latency_ms, "total_cost_usd": total_cost_usd},
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
            response = self._call_llm(messages, tools=tools, request_context=context)
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
