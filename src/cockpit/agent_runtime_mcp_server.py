"""Agent Runtime MCP Server — 供 Hermes 作为 MCP 工具调用

注册后 Hermes 可通过工具调用 Agent Runtime 的:
- run_task: 执行预定义任务
- chat: 对话交互
- terminal_run: 执行终端命令
- file_read: 读取文件
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

from fastmcp import FastMCP  # type: ignore[import-not-found]

from cockpit.adapters import capability_binding, governance_context

mcp = FastMCP("agent-runtime")

# 延迟导入避免启动时挂住
_runtime = None


_log = logging.getLogger(__name__)


def _log_execution(task_name: str, status: str, summary: str, result: dict[str, Any], elapsed: float) -> None:
    """Log task execution details."""
    _log.info("Task %s [%s] in %.2fs — %s", task_name, status, elapsed, summary)


def get_runtime():
    global _runtime
    if _runtime is None:
        from cockpit.adapters.runtime import AgentRuntime

        if AgentRuntime is None:
            raise RuntimeError("runtime package missing")
        _runtime = AgentRuntime()
    return _runtime


def extract_authority_fields(principal_authority: dict | None) -> dict | None:
    """透传式提取 (BET-Y1Q3-T4-04 spec §2): Cockpit 只接收并转发 authority fields。

    不构造、不验证、不补全 — 缺键/多键/非字符串一律返回 None (拒绝形态交给
    下游 OMO 权威验证)。credential secret 在这里就不允许出现 (spec §2)。
    """
    if not isinstance(principal_authority, dict):
        return None
    if set(principal_authority) != {"authority_ref", "receipt_digest"}:
        return None
    ref = principal_authority["authority_ref"]
    digest = principal_authority["receipt_digest"]
    if not isinstance(ref, str) or not ref or not isinstance(digest, str) or not digest:
        return None
    return {"authority_ref": ref, "receipt_digest": digest}


def _authority_request_context(principal_authority: dict | None) -> dict | None:
    fields = extract_authority_fields(principal_authority)
    if fields is None:
        return None
    return {
        "principal_authority_ref": fields["authority_ref"],
        "principal_receipt_digest": fields["receipt_digest"],
    }


@mcp.tool()
def run_task(task_name: str, binding_receipt: dict = None, principal_authority: dict = None) -> str:
    """Run a predefined task by name (e.g. WF-005, codexbar-quota, daily-summary).

    Tasks are loaded from task_definitions/<name>.json.
    Effectful execution requires a verified capability binding receipt.
    """
    if not capability_binding.verify_binding_envelope(binding_receipt):
        return _json_envelope(
            {
                "error": "effectful agent-runtime tools require a verified capability binding",
                "authority_state": "non_authoritative",
            }
        )
    runtime = get_runtime()
    task_def_dir = Path(__file__).parent / "task_definitions"
    task_file = task_def_dir / f"{task_name}.json"
    if not task_file.exists() or not task_def_dir.exists():
        return f"Task '{task_name}' not found. task_definitions directory is empty or missing."

    task_def = json.loads(task_file.read_text())
    prompt = task_def.get("prompt", "")
    if not prompt:
        return f"Task '{task_name}' has no prompt defined."

    t0 = time.time()
    request_context = _authority_request_context(principal_authority)
    if request_context is None:
        result = runtime.run_task(prompt)
    else:
        result = runtime.run_task(prompt, context=request_context)
    elapsed = time.time() - t0

    # 记录执行日志
    try:
        status = "error" if "error" in result else "ok"
        summary = result.get("result", "")[:200]
        _log_execution(task_name, status, summary, result, elapsed)
    except Exception:  # defensive fallback
        pass

    if result.get("error"):
        return f"[ERROR] {result['error']}"
    return result.get("result", "(empty response)")


@mcp.tool()
def chat(message: str, history_json: str = "", binding_receipt: dict = None, principal_authority: dict = None) -> str:
    """Send a message to Agent Runtime and get a reply.

    Use this for interactive conversations where you want Agent Runtime's
    capabilities. Supports multi-turn via history_json.

    Args:
        message: The user's message
        history_json: Optional JSON array of previous exchanges
                      [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    binding_supplied = isinstance(binding_receipt, dict) and bool(binding_receipt)
    if binding_supplied and not capability_binding.verify_binding_envelope(binding_receipt):
        return _json_envelope(
            {
                "error": "effectful agent-runtime tools require a verified capability binding",
                "authority_state": "non_authoritative",
                "tools": [],
            }
        )
    bound = binding_supplied
    runtime = get_runtime()
    history = []
    if history_json:
        try:
            history = json.loads(history_json)
        except json.JSONDecodeError:
            pass

    # 构建 system prompt
    system_prompt = (
        "你是 Agent Runtime，一个 AI 助手。你可以使用工具来完成任务。\n"
        "请用中文回复。\n"
        "如果你需要执行命令、读取文件或查询系统，使用相应的工具。\n"
        "如果只是聊天，直接回复即可。"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-20:]:
        if isinstance(h, dict) and "role" in h and "content" in h:
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    schemas = runtime._build_tool_schemas() if bound else []  # type: ignore[union-attr]
    request_context = _authority_request_context(principal_authority)
    max_turns = 30

    for turn in range(max_turns):
        if request_context is None:
            response = runtime._call_llm(messages, tools=schemas)
        else:
            response = runtime._call_llm(messages, tools=schemas, request_context=request_context)
        finish = response.get("finish_reason", "stop")

        if response.get("error"):
            return f"抱歉，我遇到了错误: {response['error']}"

        assistant_msg = dict(response)
        assistant_msg.pop("finish_reason", None)
        assistant_msg.pop("usage", None)
        assistant_msg.pop("error", None)
        messages.append(assistant_msg)
        tcs = response.get("tool_calls", [])

        if finish == "stop" or not tcs:
            return response.get("content", "")

        if not bound:
            return _json_envelope(
                {
                    "response": response.get("content", "") or "",
                    "authority_state": "non_authoritative",
                    "tools": [],
                }
            )

        for tc in tcs:
            tool_result = runtime._execute_tool(tc)
            messages.append(tool_result)

    return messages[-1].get("content", "")


def _json_envelope(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


@mcp.tool()
def workspace_context() -> str:
    """Read the Workspace phase, Documents domains, and CARDS summary from their SSOT owners."""

    return _json_envelope(governance_context.workspace_context())


@mcp.tool()
def domains_list() -> str:
    """List validated Documents knowledge domains with paths, BOS URIs, and capabilities."""

    return _json_envelope(governance_context.domains_list())


@mcp.tool()
def domain_context(domain_id: str) -> str:
    """Resolve one Documents domain and its optional Workspace Cowork binding."""

    return _json_envelope(governance_context.mcp_safe_domain_context(governance_context.domain_context(domain_id)))


@mcp.tool()
def domain_project_status(domain_id: str = "") -> str:
    """Read one or all Documents domain project bindings and gateway files."""

    return _json_envelope(governance_context.domain_project_status(domain_id))


@mcp.tool()
def domain_facts_audit(domain_id: str = "") -> str:
    """Audit registered Documents document-domain facts files without reading content."""

    return _json_envelope(governance_context.domain_facts_audit(domain_id))


@mcp.tool()
def domain_facts_validation_status(domain_id: str) -> str:
    """Read Runtime's bounded structured-Facts validation receipt for one Documents domain."""

    return _json_envelope(governance_context.domain_facts_validation_status(domain_id))


@mcp.tool()
def domain_model_freshness_status(domain_id: str) -> str:
    """Read Runtime's bounded model-freshness receipt for one Documents domain."""

    try:
        result = governance_context.domain_model_freshness_status(domain_id)
    except Exception:
        result = governance_context.model_freshness_unavailable_envelope(
            domain_id,
            "model_freshness_mcp_unavailable",
        )
    return _json_envelope(result)


@mcp.tool()
def domain_sanyi_status_consistency_status(domain_id: str) -> str:
    """Read Runtime's bounded aggregate CR08 status-consistency receipt for one Documents domain."""

    try:
        result = governance_context.domain_sanyi_status_consistency_status(domain_id)
    except Exception:
        result = governance_context.sanyi_status_consistency_unavailable_envelope(
            domain_id,
            "sanyi_status_mcp_unavailable",
        )
    return _json_envelope(result)


@mcp.tool()
def domain_controller_shadow_status(domain_id: str) -> str:
    """Read Runtime's incomplete legacy controller-shadow receipt for one Documents domain."""

    return _json_envelope(governance_context.domain_controller_shadow_status(domain_id))


@mcp.tool()
def cards_status() -> str:
    """List CARDS through the OMO authority."""

    return _json_envelope(governance_context.cards_status())


@mcp.tool()
def cards_check(card_id: str = "") -> str:
    """Run the OMO CARDS constraint authority and preserve its result envelope."""

    return _json_envelope(governance_context.cards_check(card_id=card_id))


@mcp.tool()
def kems_status() -> str:
    """Read Documents content-audit and KEMS owner reachability status."""

    return _json_envelope(governance_context.kems_status())


# ── L0 治理查询工具 (P78 audit 发现 8 个工具定义在 l0_mcp_tools.py 但未注册) ──
# 让 Agent Runtime MCP 客户端可直接调 L0 状态/校验/审计
# 用 fallback 防止 l0_mcp_tools 不可用时整个 server 挂掉
try:
    from cockpit.l0_mcp_tools import MCP_TOOLS as _L0_TOOLS

    for _name, _meta in _L0_TOOLS.items():
        _fn = _meta["function"]
        # 闭包绑定: FastMCP 用名字作为 tool identifier
        globals()[_name] = _fn
        mcp.tool(name=_name, description=_meta["description"])(_fn)
except ImportError:
    _log.warning("l0_mcp_tools 不可用, 跳过 L0 治理工具注册 (cockpit.l0_mcp_tools 模块未找到)")


def main():
    """MCP server entry point (used by pyproject.scripts)."""
    logging.basicConfig(level=logging.ERROR)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
