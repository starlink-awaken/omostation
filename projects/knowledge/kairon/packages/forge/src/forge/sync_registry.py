#!/usr/bin/env python3
"""
sync_registry — 从 tools-registry.json 生成 Markdown 快照 + 日志截断

功能:
1. 生成 tools-registry.md（人类可读的工具清单）
2. 截断 event_log（超过 1000 条时保留最近 500 条）
3. 发布同步事件至 Agora（可选）

用法:
  python3 src/sync_registry.py
  python3 src/sync_registry.py --skip-agora
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from typing import cast

from forge.forge_config import FORGE_ROOT, REGISTRY  # type: ignore[import-not-found]


def _load() -> dict:
    return cast("dict", json.loads(REGISTRY.read_text()))


def _save(reg: dict) -> None:
    tmp = REGISTRY.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    tmp.rename(REGISTRY)


def generate_markdown() -> str:
    """从注册表生成 Markdown 格式的工具清单。"""
    reg = _load()
    tools = reg.get("tools", [])
    event_log = reg.get("event_log", [])

    lines = []
    lines.append("# AI ToolBox — 工具资产注册表")
    lines.append("")
    lines.append(f"> 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')} | {len(tools)} 条记录")
    lines.append("")
    lines.append("| # | 名称 | 类型 | 状态 | 版本 | 描述 |")
    lines.append("|---|------|------|------|------|------|")

    status_icons = {"active": "🟢", "evaluating": "🟡", "inactive": "⚪"}
    for i, t in enumerate(tools, 1):
        status = t.get("status", "-")
        icon = status_icons.get(status, "⚪")
        name = t.get("name", "-")
        typ = t.get("type", "-")
        version = t.get("version", "-")
        desc = (t.get("description") or t.get("notes", ""))[:60]
        lines.append(f"| {i} | {name} | {typ} | {icon} {status} | {version} | {desc} |")

    if event_log:
        lines.append("")
        lines.append("## 最近事件")
        for ev in event_log[-5:]:
            ts = ev.get("time")
            src = ev.get("source", "")
            summary = ev.get("summary", "")
            lines.append(f"- [{ts}] **{src}**: {summary}")

    return "\n".join(lines)


def truncate_event_log() -> int:
    """截断超过 1000 条的 event_log，保留最近 500 条。"""
    reg = _load()
    event_log = reg.get("event_log", [])
    before = len(event_log)
    if before > 1000:
        reg["event_log"] = event_log[-500:]
        _save(reg)
        print(f"⚠️  event_log 截断: {before} → 500")
    else:
        print(f"   event_log: {before} 条 (正常)")
    return before


def publish_to_agora() -> None:
    """向 Agora 发布同步事件（如果 agora CLI 可用）。"""
    try:
        tools = len(_load().get("tools", []))
        payload = f'{{"tools":{tools}}}'
        subprocess.run(
            ["agora", "event", "publish", "registry:synced", "--payload", payload, "--source", "forge"],
            capture_output=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass  # agora CLI 不可用时不报错


def run(skip_agora: bool = False) -> int:
    """执行完整的同步流程。"""
    print("🔄 同步 Forge 注册表...")

    # 1. 生成 Markdown
    md_path = FORGE_ROOT / "tools-registry.md"
    md = generate_markdown()
    md_path.write_text(md)
    tools_count = len(_load().get("tools", []))
    print(f"✅ tools-registry.md 已更新 ({tools_count} 个工具)")

    # 2. 截断 event_log
    truncate_event_log()

    # 3. Agora 事件
    if not skip_agora:
        publish_to_agora()

    print("✅ 同步完成")
    return 0


def main() -> int:
    skip_agora = "--skip-agora" in sys.argv
    return run(skip_agora=skip_agora)


if __name__ == "__main__":
    sys.exit(main())
