"""omlxc Compute Fabric MCP Tools — agora 侧.

提供 3 个算力网格治理与意图分诊 MCP 工具:
  - fabric_inspect()                                   : 采集异构节点温控、模型架构与两级缓存状态
  - fabric_triage(prompt)                              : 对 Prompt 意图复杂度做 AST 初筛 (FAST/STANDARD/REASONING)
  - fabric_vram_budget(model_id, context_tokens)       : 计算模型动态 KV Cache 显存预算与准入判定
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastmcp import FastMCP

from agora.mcp.tools_template import FORMAT_VERSION, _error, _ok

mcp = FastMCP("agora-compute-fabric")


def _omlxc_root() -> Path:
    ws = Path(__file__).resolve().parents[5]
    return ws / "projects" / "omlxc"


@mcp.tool()
def fabric_inspect() -> dict:
    """检查 omlxc 本地算力织网的实时健康度、温控惩罚、意图分级与缓存大盘."""
    try:
        proc = subprocess.run(
            ["uv", "run", "omlxc", "fabric", "inspect", "--json"],
            cwd=str(_omlxc_root()),
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )
        if proc.returncode != 0:
            return _error(f"omlxc_fabric_inspect_failed: {proc.stderr or proc.stdout}")
        data = json.loads(proc.stdout)
        return _ok({"format_version": FORMAT_VERSION, "fabric": data.get("data", {})})
    except Exception as exc:
        return _error(f"fabric_inspect_error: {exc}")


@mcp.tool()
def fabric_triage(prompt: str) -> dict:
    """分析 Prompt 的意图复杂度等级 (FAST / STANDARD / REASONING).

    Args:
        prompt: 待分析的任务提示词或代码片段
    """
    try:
        proc = subprocess.run(
            ["uv", "run", "omlxc", "fabric", "triage", prompt, "--json"],
            cwd=str(_omlxc_root()),
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )
        if proc.returncode != 0:
            return _error(f"omlxc_fabric_triage_failed: {proc.stderr or proc.stdout}")
        data = json.loads(proc.stdout)
        return _ok({"format_version": FORMAT_VERSION, "triage": data.get("data", {})})
    except Exception as exc:
        return _error(f"fabric_triage_error: {exc}")


@mcp.tool()
def fabric_vram_budget(model_id: str, context_tokens: int) -> dict:
    """预估长上下文推理的动态 KV Cache 显存增长与准入安全性.

    Args:
        model_id: 模型标识符 (例如 coding, qwen-72b, gemma-9b)
        context_tokens: 预估的上下文 Token 数量
    """
    try:
        proc = subprocess.run(
            [
                "uv",
                "run",
                "omlxc",
                "fabric",
                "vram",
                model_id,
                str(context_tokens),
                "--json",
            ],
            cwd=str(_omlxc_root()),
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )
        if proc.returncode != 0:
            return _error(f"omlxc_fabric_vram_failed: {proc.stderr or proc.stdout}")
        data = json.loads(proc.stdout)
        return _ok(
            {"format_version": FORMAT_VERSION, "vram_budget": data.get("data", {})}
        )
    except Exception as exc:
        return _error(f"fabric_vram_budget_error: {exc}")
