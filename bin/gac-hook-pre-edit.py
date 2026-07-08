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

注: 默认 advisory (不阻塞). 宪法 Wave 3 (ADR-0171): GAC_PRE_EDIT_BLOCK=1 启用 blocking (exit 2 事前拦).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"


def load_ssot_rules() -> list[dict]:
    """加载 gac active 规则 (机制 3 检查对象, 扩展到多 check_type)."""
    import yaml

    if not REGISTRY.exists():
        return []
    try:
        docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    except yaml.YAMLError:
        return []  # registry 坏了不阻塞编辑 (advisory), gac-drift 事后兜底
    if not docs:
        return []
    rules = docs[-1].get("gac", {}).get("rules", [])
    return [r for r in rules if r.get("lifecycle") == "active"]


# Pattern-based check types that can be enforced at edit time
HOOKABLE_CHECK_TYPES = {
    "ssot_pointer",
    "port_hardcode",
    "import_nucleus",
    "direct_omo_io",
    "broad_except",
}


def check_content(file_path: str, new_content: str) -> list[str]:
    """检查内容是否违反 GaC 规则. 返回 warnings 列表."""
    warnings: list[str] = []
    if not new_content:
        return warnings

    rules = load_ssot_rules()
    try:
        rel = str(Path(file_path).resolve().relative_to(WORKSPACE))
    except (ValueError, OSError):
        rel = file_path

    # Only check Python/YAML files for pattern-based rules
    is_py = rel.endswith(".py")
    is_yaml = rel.endswith((".yaml", ".yml"))

    for rule in rules:
        check_type = rule.get("check_type", "")
        if check_type not in HOOKABLE_CHECK_TYPES:
            continue

        rid = rule.get("id", "?")

        if check_type == "ssot_pointer":
            warnings.extend(_check_ssot_pointer(rule, rid, rel, new_content))
        elif check_type == "port_hardcode" and (is_py or is_yaml):
            warnings.extend(_check_port_hardcode(rule, rid, rel, new_content))
        elif check_type == "import_nucleus" and is_py:
            warnings.extend(_check_import_nucleus(rule, rid, rel, new_content))
        elif check_type == "direct_omo_io" and is_py:
            warnings.extend(_check_direct_omo_io(rule, rid, rel, new_content))
        elif check_type == "broad_except" and is_py:
            warnings.extend(_check_broad_except(rule, rid, rel, new_content))

    return warnings


def _check_ssot_pointer(rule, rid, rel, content):
    """SSOT 指针检查: 禁止在 markdown/yaml 中硬编码易变值."""
    warnings = []
    target = rule.get("target", "")
    if "::" not in target:
        return warnings
    field = target.split("::", 1)[1]
    forbid = rule.get("forbid_copy_in", [])
    matched = any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, f"**/{pat}") for pat in forbid)
    if not matched:
        return warnings
    pattern = re.compile(rf"(?<![\[\.]){re.escape(field)}\s*:\s*\d")
    for m in pattern.finditer(content):
        ctx = content[max(0, m.start() - 40): m.end() + 80]
        if any(kw in ctx for kw in ["_ref", "见 ", "see ", "指向", "指针", "SSOT", "system.yaml", "示例值"]):
            continue
        warnings.append(f"GaC {rid}: {rel} 硬编码 {field} 值 (违反 SSOT, 用指针引用)")
    return warnings


def _check_port_hardcode(rule, rid, rel, content):
    """端口硬编码检查: 禁止在源码中硬编码端口号."""
    warnings = []
    # Match patterns like :7422 or port=7422 (not in comments or env defaults)
    pattern = re.compile(r'(?<!\w)[:=](\d{4,5})(?!\d)')
    for m in pattern.finditer(content):
        port = int(m.group(1))
        if 1024 < port < 65536:
            ctx = content[max(0, m.start() - 30): m.end() + 30]
            if any(kw in ctx.lower() for kw in ["env", "os.environ", "getenv", "default", "registry", "port-registry"]):
                continue
            warnings.append(f"GaC {rid}: {rel} 疑似端口硬编码 :{port} (应走 protocols/port-registry.yaml + env)")
    return warnings


def _check_import_nucleus(rule, rid, rel, content):
    """nucleus import 检查: 禁止顶层 import nucleus."""
    warnings = []
    pattern = re.compile(r'^from\s+nucleus\b|^import\s+nucleus\b', re.MULTILINE)
    for m in pattern.finditer(content):
        ctx = content[max(0, m.start() - 20): m.end() + 20]
        if "type: ignore" in ctx or "TYPE_CHECKING" in ctx:
            continue
        warnings.append(f"GaC {rid}: {rel} 顶层 import nucleus (已废弃, 改为 lazy import 或移除)")
    return warnings


def _check_direct_omo_io(rule, rid, rel, content):
    """direct-omo-io 检查: 禁止直接 open()/write 到 .omo/."""
    warnings = []
    pattern = re.compile(r'(open|write_text|mkdir|Path)\s*\(\s*["\'].*\.omo/', re.IGNORECASE)
    for m in pattern.finditer(content):
        warnings.append(f"GaC {rid}: {rel} 疑似 direct .omo I/O (应走 omo CLI / projects/omo broker)")
    return warnings


def _check_broad_except(rule, rid, rel, content):
    """broad except 检查: 警告 bare except / except Exception."""
    warnings = []
    pattern = re.compile(r'except\s*(\s*:|\s+Exception\s*:)', re.MULTILINE)
    count = len(pattern.findall(content))
    if count > 3:
        warnings.append(f"GaC {rid}: {rel} 有 {count} 处 broad except (建议细化异常类型)")
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
        # 宪法 Wave 3 (ADR-0171): GAC_PRE_EDIT_BLOCK=1 启用 blocking (事前拦, exit 2)
        block_mode = os.environ.get("GAC_PRE_EDIT_BLOCK") == "1"
        prefix = "🚫 GaC SSOT 违规 (blocking, 事前拦 — Wave 3)" if block_mode else "⚠️  GaC SSOT 检查警告 (advisory, 不阻塞)"
        print(f"{prefix}:", file=sys.stderr)
        for w in all_warnings:
            print(f"  - {w}", file=sys.stderr)
        if block_mode:
            return 2  # PreToolUse exit 2 = 阻塞工具 (事前拦, 不让违规 edit 落地)

    return 0  # 默认 advisory; GAC_PRE_EDIT_BLOCK=1 启用 blocking


if __name__ == "__main__":
    sys.exit(main())
