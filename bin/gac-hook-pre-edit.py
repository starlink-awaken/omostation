#!/usr/bin/env python3
"""GaC PreToolUse hook (ADR-0106, 机制 3, Claude Code 编辑时强制).

Claude Code PreToolUse hook: 拦截 Edit/Write/MultiEdit, 检查 GaC SSOT 规则.
违规 → stderr 警告 (advisory, 不阻塞, exit 0).

机制 3 (泛化执行器) 的 Claude Code 通道:
  - 编辑时即时检查 SSOT drift (预防, 不等 gac-drift 事后发现)
  - advisory 模式 (警告不阻塞, 不破坏工作流)
  - 跨工具: MCP (omo, Cursor/Codex/Devin) + CI gate 兜底 (所有工具)

激活 (advisory, 项目级 .claude/settings.json):
  {
    "hooks": {
      "PreToolUse": [
        {"matcher": "Edit|Write|MultiEdit", "command": "python3 bin/gac-hook-pre-edit.py"}
      ]
    }
  }

输入 (Claude Code PreToolUse JSON, stdin):
  {"tool_name": "Edit", "tool_input": {"file_path": "...", "new_string": "..."}}
输出:
  exit 0 + stderr 警告 (advisory) 或 exit 0 静默 (合规)

注: advisory (不阻塞) 是有意设计 — 先观察, 稳定后可改 exit 2 阻塞.
"""

from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"


def load_ssot_rules() -> list[dict]:
    """加载 gac ssot_pointer active 规则 (机制 3 检查对象)."""
    import yaml

    if not REGISTRY.exists():
        return []
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    if not docs:
        return []
    rules = docs[-1].get("gac", {}).get("rules", [])
    return [
        r
        for r in rules
        if r.get("check_type") == "ssot_pointer" and r.get("lifecycle") == "active"
    ]


def check_content(file_path: str, new_content: str) -> list[str]:
    """检查内容是否违反 SSOT 规则. 返回 warnings 列表."""
    warnings: list[str] = []
    if not new_content:
        return warnings

    rules = load_ssot_rules()
    try:
        rel = str(Path(file_path).resolve().relative_to(WORKSPACE))
    except (ValueError, OSError):
        rel = file_path

    for rule in rules:
        target = rule.get("target", "")
        if "::" not in target:
            continue
        field = target.split("::", 1)[1]
        forbid = rule.get("forbid_copy_in", [])

        # file 是否在 forbid_copy_in glob
        matched = any(
            fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, f"**/{pat}")
            for pat in forbid
        )
        if not matched:
            continue

        # new_content 硬编码 field + 数字 (排除指针引用)
        pattern = re.compile(rf"(?<![\[\.]){re.escape(field)}\s*:\s*\d")
        for m in pattern.finditer(new_content):
            ctx = new_content[max(0, m.start() - 40) : m.end() + 80]
            if any(
                kw in ctx
                for kw in [
                    "_ref",
                    "见 ",
                    "see ",
                    "指向",
                    "指针",
                    "SSOT",
                    "system.yaml",
                    "示例值",
                ]
            ):
                continue  # 指针引用/示例标注, 合法
            warnings.append(
                f"GaC {rule['id']}: {rel} 硬编码 {field} 值 "
                f"(违反 SSOT, 应用指针引用 system.yaml 或加 # 示例值 注释)"
            )
    return warnings


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # 非 JSON 输入, 放行

    tool = data.get("tool_name", "")
    if tool not in ("Edit", "Write", "MultiEdit"):
        return 0  # 非 edit, 放行

    inp = data.get("tool_input", {})
    file_path = inp.get("file_path", "")

    # 收集 new_content (Edit: new_string; Write: content; MultiEdit: edits[])
    contents: list[str] = []
    if tool == "Write":
        contents.append(inp.get("content", ""))
    elif tool == "Edit":
        contents.append(inp.get("new_string", ""))
    elif tool == "MultiEdit":
        for e in inp.get("edits", []):
            contents.append(e.get("new_string", ""))

    all_warnings: list[str] = []
    for c in contents:
        all_warnings.extend(check_content(file_path, c))

    if all_warnings:
        # advisory: stderr 警告 (Claude 看到), exit 0 (不阻塞)
        print("⚠️  GaC SSOT 检查警告 (advisory, 不阻塞):", file=sys.stderr)
        for w in all_warnings:
            print(f"  - {w}", file=sys.stderr)

    return 0  # advisory, 永不阻塞 (稳定后可改 return 2 阻塞)


if __name__ == "__main__":
    sys.exit(main())
