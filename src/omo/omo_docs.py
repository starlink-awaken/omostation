"""omo docs — CLI 文档自动生成.

从 omo CLI 的各个模块中提取 docstring 和帮助文本,
生成 Markdown 格式的 CLI 参考文档.
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _get_module_docstring(module_name: str) -> str:
    """获取模块的 docstring."""
    try:
        module = importlib.import_module(module_name)
        return module.__doc__ or ""
    except ImportError:
        return ""


def _extract_commands_from_cli() -> list[dict[str, Any]]:
    """从 cli.py 提取命令列表."""
    commands = []

    # 顶层命令
    top_level = [
        ("doctor", "omo.omo_doctor", "统一健康检查入口"),
        ("inspect", "omo.omo_inspect", "统一检查入口"),
        ("health", None, "服务探活 / 看板"),
        ("lint", None, "静态校验"),
        ("manage", "omo.omo_manage", "目录管理"),
        ("validate", "omo.omo_validate", "目录验证"),
        ("audit", None, "X 审计"),
        ("worker", None, "Worker 调度"),
        ("task", "omo.omo_task", "任务管理"),
        ("debt", "omo.omo_debt_cli", "债务管理"),
        ("state", "omo.omo_state", "状态管理"),
        ("governance", "omo.omo_governance", "治理操作"),
    ]

    for name, module_name, desc in top_level:
        doc = _get_module_docstring(module_name) if module_name else ""
        commands.append(
            {
                "name": name,
                "description": desc,
                "docstring": doc.strip() if doc else "",
                "subcommands": [],
            }
        )

    return commands


def _extract_subcommands(command_name: str) -> list[dict[str, str]]:
    """提取子命令列表."""
    subcommands = {
        "health": [
            ("check", "探活 agora-routes.json 注册的服务端点"),
            ("dashboard", "Keeper Dashboard — 读取 .omo/ 状态文件渲染运维看板"),
        ],
        "lint": [
            ("schemas", "扫 7 consumer 模块, 校验 .append() 都传 schema="),
            ("yaml-bypass", "扫 .omo/debt/items/*.yaml 拦截 status 字段越权写入"),
            ("direct-omo-io", "拦截非 broker 对 .omo / spaces 的直接文件系统改写"),
            (
                "projection-guard",
                "P74: 验证 runtime-projections.yaml 声明的路径存在且可解析",
            ),
            (
                "stamp-policy",
                "P74: 验证 runtime/ 下文件必须 gitignored/tracked/allowlisted",
            ),
            (
                "sensitive-governed-writes",
                "拦截对 system/goals/tasks/capabilities 等敏感治理面的直接落盘",
            ),
            ("god-module", "单文件 LOC 硬规则 (warn>600L, error>800L)"),
        ],
        "manage": [
            ("status", "显示 .omo 目录状态"),
            ("health", "检查 .omo 目录健康度"),
            ("tasks", "列出任务状态"),
        ],
        "validate": [
            ("completeness", "验证 .omo 目录完整性"),
            ("references", "验证关键文件引用完整性"),
            ("state", "验证状态一致性"),
            ("all", "执行全部验证"),
        ],
        "audit": [
            ("cards", "CARDS X3 value metrics (SQLite 聚合)"),
            ("vault", "Vault X1 audit (Markdown content hash + author tracking)"),
            ("freshness", "X2 freshness audit (3 条 P43 巡检规则)"),
        ],
        "worker": [
            ("task", "任务相关命令"),
            ("worker", "Worker 相关命令"),
        ],
    }
    result = []
    for name, desc in subcommands.get(command_name, []):
        result.append({"name": name, "description": desc})
    return result


def generate_cli_docs(output_path: Path | None = None) -> str:
    """生成 CLI 文档."""
    lines = [
        "# omo CLI Reference",
        "",
        f"> Auto-generated on {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## Overview",
        "",
        "omo is the L2 governance kernel CLI for omostation. It provides commands for",
        "health checking, linting, validation, auditing, and worker management.",
        "",
        "## Commands",
        "",
    ]

    commands = _extract_commands_from_cli()

    for cmd in commands:
        lines.append(f"### `omo {cmd['name']}`")
        lines.append("")
        lines.append(cmd["description"])
        lines.append("")

        if cmd["docstring"]:
            lines.append("**Details:**")
            lines.append("")
            lines.append("```")
            lines.append(cmd["docstring"][:500])
            lines.append("```")
            lines.append("")

        subcommands = _extract_subcommands(cmd["name"])
        if subcommands:
            lines.append("**Subcommands:**")
            lines.append("")
            lines.append("| Command | Description |")
            lines.append("|---------|-------------|")
            for sub in subcommands:
                lines.append(f"| `{sub['name']}` | {sub['description']} |")
            lines.append("")

    # Usage examples
    lines.extend(
        [
            "## Common Usage",
            "",
            "```bash",
            "# Health check",
            "omo doctor                  # Unified health check",
            "omo inspect                 # Unified inspection",
            "",
            "# Health",
            "omo health check            # Probe agora services",
            "omo health dashboard        # Keeper dashboard",
            "",
            "# Lint",
            "omo lint schemas            # Schema validation",
            "omo lint projection-guard   # P74 projection guard",
            "omo lint stamp-policy       # P74 stamp policy",
            "",
            "# Manage",
            "omo manage status           # Directory status",
            "omo manage health           # Health check",
            "omo manage tasks            # Task status",
            "",
            "# Validate",
            "omo validate all            # Full validation",
            "",
            "# Audit",
            "omo audit cards --json      # CARDS X3 metrics",
            "omo audit vault --json      # Vault X1 audit",
            "omo audit freshness --json  # X2 freshness audit",
            "",
            "# Worker",
            "omo worker task validate --all-planned",
            "omo worker task promotion-readiness",
            "```",
            "",
        ]
    )

    content = "\n".join(lines)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        print(f"CLI docs written to {output_path}")
    else:
        print(content)

    return content


def cmd_docs(output: str | None = None) -> int:
    """生成 CLI 文档."""
    if output:
        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path
    else:
        output_path = None

    generate_cli_docs(output_path)
    return 0
