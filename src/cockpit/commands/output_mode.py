"""cockpit.commands.output_mode — 全局 ``--output json`` 探测式分发 (Phase A4).

现状修复: 全局 ``--output {text,json,tui,markdown}`` 此前只有 ``tui`` 有分发逻辑,
``json``/``markdown`` 解析后被静默忽略。

策略 (探测式, 禁止静默):
  · 命令在 ``JSON_CAPABLE`` 集合内 → 注入 ``args.json = True`` (复用各命令既有 ``--json`` 语义)
  · 不在集合内 → stderr 打印明确提示, 按原样执行 (不静默降级)

扩容由 Phase D command-audit 审查结论 (io_readability 维度) 驱动, 逐步补齐。
"""

from __future__ import annotations

import argparse

# 声明支持结构化 JSON 输出的顶级命令 (各命令自带 --json / --format json)
JSON_CAPABLE: frozenset[str] = frozenset({
    "status",          # status --json
    "daily",           # daily --json
    "health",          # health --json
    "data",            # data index/types/gc --json
    "readiness",       # readiness --format json (注入 format)
    "research",        # research list/open --json
    "scenario",        # scenario --json
    "watchdog",        # watchdog --json
    "swarm",           # swarm --json
    "audit",           # audit --format json (注入 format)
    "kems",            # kems status --json
    "ops",             # ops --json
    "agent-onboard",   # agent-onboard --json
    "quickstart-check",  # --json
    "domain-status",
    "facts-audit",
    "facts-validation",
    "model-freshness",
    "sanyi-status",
    "controller-shadow",
    "events-watch",
})

# --format json 型命令 (注入 format=json 而非 json=True)
FORMAT_JSON_COMMANDS: frozenset[str] = frozenset({"readiness", "audit"})


def apply_json_mode(args: argparse.Namespace) -> None:
    """全局 --output json 的分发钩子 (cli.py main() 分发前调用).

    JSON_CAPABLE 内命令注入 json/format 属性; 其余明确提示不静默。
    """
    cmd = getattr(args, "command", "")
    if cmd in FORMAT_JSON_COMMANDS:
        setattr(args, "format", "json")
        return
    if cmd in JSON_CAPABLE:
        setattr(args, "json", True)
        return
    # 未适配命令: 明确提示 (stderr), 按原样执行
    import sys

    print(
        f"[cockpit] 提示: 命令 '{cmd}' 暂未适配 --output json (沿用其自身参数输出)。\n"
        f"          完整适配状态见 docs/command-audit 评分卡 io_readability 维度。",
        file=sys.stderr,
    )


__all__ = ["JSON_CAPABLE", "FORMAT_JSON_COMMANDS", "apply_json_mode"]
