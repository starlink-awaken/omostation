"""Cockpit MOF Commands — MOF 元模型操作入口 (动态调度)"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[5]
MOF_CAPABILITIES_PATH = WORKSPACE / ".omo" / "_truth" / "registry" / "mof-capabilities.yaml"


def _load_mof_tools() -> dict[str, dict]:
    """Load MOF tools from mof-capabilities.yaml."""
    if not MOF_CAPABILITIES_PATH.exists():
        return {}
    try:
        with MOF_CAPABILITIES_PATH.open(encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
            if len(docs) > 1 and "tools" in docs[1]:
                return docs[1]["tools"]
            if len(docs) > 0 and "tools" in docs[0]:
                return docs[0]["tools"]
    except Exception:
        pass
    return {}


def cmd_mof(args) -> int:
    """MOF 元模型操作 (动态检查/验证/审计/强制执行)"""
    # 动态查表分发 (从 mof-capabilities.yaml 读取)
    if not args.extra:
        print("用法: cockpit mof <subcommand> [args...]")
        print("  可用的子命令从 .omo/_truth/registry/mof-capabilities.yaml 加载。")
        print("  常用: reason, decide, graph, autonomous, act, analyze, drift, enforce")
        return 1

    subcmd = args.extra[0]
    tool_key = f"mof-{subcmd}"
    tools = _load_mof_tools()

    if tool_key in tools:
        tool_info = tools[tool_key]
        tool_path = WORKSPACE / tool_info["path"]

        if not tool_path.exists():
            print(f"❌ 工具文件不存在: {tool_path}")
            return 1

        cmd_args = args.extra[1:]

        # Determine how to run it
        if tool_path.suffix == ".py":
            cmd = [sys.executable, str(tool_path)] + cmd_args
        else:
            cmd = [str(tool_path)] + cmd_args

        result = subprocess.run(cmd, capture_output=False, text=True, cwd=str(WORKSPACE))
        return result.returncode

    # Fallback to the legacy ecos mof CLI
    legacy_cmd = [sys.executable, "-m", "ecos.ssot.tools.mof"] + args.extra
    result = subprocess.run(legacy_cmd, capture_output=False, text=True, cwd=str(WORKSPACE))
    return result.returncode
