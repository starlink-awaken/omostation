"""ecos.l0.ssot.cli_main — CLI entry point (P110 拆分).

TASK-F7114ABA (omo lint god-module 800L 硬规则).
ecos/l0/ssot/cli.py 1198L 拆分: main() + _dispatch() (~243L) 独立到本模块,
cli.py 降至 ~955L (<800L 阈值).

业务: argparse 子命令路由 (init / compile / derive / check / graph / report
/ completion / verify / evolve / extract / stats / export + 子命令 sync 等).

模式: 顶层 re-export (PFC) 保持 `from .cli import main` 仍可用.
调用方 `from ecos.l0.ssot.cli import main` 不破.
"""

from __future__ import annotations

import argparse
import warnings

# Lazy import: 在 _dispatch 之前 import 所有 cmd_* (依名字查找)
# 这样 _dispatch 内的 `return cmd_init(args)` 等能正确找到函数
from .cli import (
    _TEMPLATES,
    MONITORING_AVAILABLE,
    _derive_watch,
    _emit,
    cmd_check,
    cmd_compile,
    cmd_completion,
    cmd_derive,
    cmd_evolve,
    cmd_export,
    cmd_extract,
    cmd_graph,
    cmd_init,
    cmd_report,
    cmd_stats,
    cmd_sync,
    cmd_verify,
)
from .reporter import Reporter


def main(argv: list[str] | None = None) -> int:
    warnings.warn(
        "ecos CLI 为内部程序接口。人类用户请使用 cockpit。",
        DeprecationWarning,
        stacklevel=2,
    )
    parser = argparse.ArgumentParser(
        prog="ssot-kernel",
        description="SSOT Kernel — 单一事实源知识工程通用引擎 v2.0",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument(
        "--debug", action="store_true", help="出错时显示完整 Python 错误栈"
    )

    # 共享参数：所有子命令都继承 --debug
    _common = argparse.ArgumentParser(add_help=False)
    _common.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)

    sub = parser.add_subparsers(dest="command", help="子命令")

    # init
    p_init = sub.add_parser("init", help="初始化新的 SSOT 项目", parents=[_common])
    p_init.add_argument("--domain", "-d", default=None, help="领域名称")
    p_init.add_argument("--name", "-n", default=None, help="领域名称（别名）")
    p_init.add_argument("--dir", default=".", help="父目录")
    p_init.add_argument(
        "--template",
        "-t",
        default="",
        choices=["", "tech-transfer", "research-lab"],
        help="预置模板（tech-transfer / research-lab）",
    )

    # compile
    p_compile = sub.add_parser("compile", help="编译 YAML 为 JSON", parents=[_common])
    p_compile.add_argument("--dir", default=".")
    p_compile.add_argument(
        "--no-cache", action="store_true", help="跳过缓存，强制重新加载"
    )

    # derive
    p_derive = sub.add_parser("derive", help="执行规则引擎", parents=[_common])
    p_derive.add_argument("--dir", default=".")
    p_derive.add_argument("--rounds", type=int, default=1, help="多轮迭代次数")
    p_derive.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    p_derive.add_argument(
        "--watch", "-w", action="store_true", help="监听 YAML 文件变更自动重跑"
    )

    # check
    p_check = sub.add_parser("check", help="只检查不输出报告", parents=[_common])
    p_check.add_argument("--dir", default=".")
    p_check.add_argument("--verbose", "-v", action="store_true")

    # graph
    p_graph = sub.add_parser(
        "graph", help="可视化（mermaid 实体图/状态机）", parents=[_common]
    )
    p_graph.add_argument("--dir", default=".")
    p_graph.add_argument(
        "--type", choices=["entities", "state-machine"], default="entities"
    )
    p_graph.add_argument(
        "--html",
        action="store_true",
        help="输出自包含 HTML（内嵌 mermaid.js CDN，浏览器可直接打开）",
    )
    p_graph.add_argument(
        "--output",
        "-o",
        default="",
        help="HTML 输出路径（默认: {dir}/entities.html 或 machines.html）",
    )

    # report
    p_report = sub.add_parser("report", help="生成报告", parents=[_common])
    p_report.add_argument("--dir", default=".")
    p_report.add_argument("--format", choices=["md", "json"], default="md")
    p_report.add_argument("--rounds", type=int, default=1)

    # verify
    sub.add_parser("verify", help="验证元模型正交性")

    # extract
    p_extract = sub.add_parser("extract", help="从文本提取知识结构", parents=[_common])
    p_extract.add_argument("--dir", default=".", help="目标领域目录（校验和写入目标）")
    p_extract.add_argument("--file", "-f", default="", help="源文件路径")
    p_extract.add_argument(
        "--type",
        "-t",
        default="free_text",
        choices=["free_text", "document", "structured", "conversation"],
        help="源文本类型",
    )
    p_extract.add_argument("--name", "-n", default="", help="源名称（用于元信息）")
    p_extract.add_argument(
        "--write", "-w", action="store_true", help="校验通过后自动写入 YAML"
    )
    p_extract.add_argument(
        "--llm", action="store_true", help="强制使用 LLM 提取（跳过模板）"
    )
    p_extract.add_argument(
        "--llm-model", default="", help="LLM 模型名（如 qwen2.5:7b，默认自动检测）"
    )

    # completion
    p_comp = sub.add_parser(
        "completion", help="输出 Shell 自动补全脚本", parents=[_common]
    )
    p_comp.add_argument(
        "--shell", default="bash", choices=["bash", "zsh"], help="Shell 类型"
    )

    # stats
    p_stats = sub.add_parser("stats", help="输出知识库统计信息", parents=[_common])
    p_stats.add_argument("--dir", default=".", help="领域配置目录")

    # export
    p_export = sub.add_parser("export", help="导出知识库为通用格式", parents=[_common])
    p_export.add_argument("--dir", default=".", help="领域配置目录")
    p_export.add_argument(
        "--format", choices=["json", "csv", "md"], default="md", help="导出格式"
    )
    p_export.add_argument("--output", "-o", default="", help="输出文件路径")

    # sync
    sub.add_parser("sync", help="同步操作", parents=[_common])

    # evolve
    p_evolve = sub.add_parser(
        "evolve", help="进化分析：从数据挖掘新规则", parents=[_common]
    )
    p_evolve.add_argument("--dir", default=".")
    p_evolve.add_argument(
        "--action",
        default="analyze",
        choices=["analyze", "apply", "checkpoints", "restore"],
        help="操作",
    )
    p_evolve.add_argument("--id", default="", help="要应用的规则建议 ID")
    p_evolve.add_argument("--name", default="", help="检查点名称（用于 restore）")

    # 监控子命令
    if MONITORING_AVAILABLE:
        monitoring_sub = sub.add_parser(
            "monitor", help="智能监控系统", parents=[_common]
        )

        monitor_subparsers = monitoring_sub.add_subparsers(
            dest="monitor_command", help="监控子命令"
        )

        # monitor start
        p_monitor_start = monitor_subparsers.add_parser("start", help="启动监控")
        p_monitor_start.add_argument("--duration", type=int, help="监控时长（秒）")
        p_monitor_start.add_argument("--export", help="导出数据到文件")

        # monitor status
        monitor_subparsers.add_parser("status", help="查看监控状态")

        # monitor alerts
        p_monitor_alerts = monitor_subparsers.add_parser("alerts", help="查看告警信息")
        p_monitor_alerts.add_argument("--severity", help="过滤严重程度")
        p_monitor_alerts.add_argument(
            "--stats", action="store_true", help="显示统计信息"
        )
        p_monitor_alerts.add_argument(
            "--report", action="store_true", help="生成告警报告"
        )

        # monitor metrics
        p_monitor_metrics = monitor_subparsers.add_parser("metrics", help="查看指标")
        p_monitor_metrics.add_argument(
            "--category",
            choices=["system", "execution", "business", "quality", "all"],
            default="all",
            help="指标类别",
        )
        p_monitor_metrics.add_argument(
            "--history", type=int, help="历史时间窗口（分钟）"
        )
        p_monitor_metrics.add_argument("--export", help="导出数据到文件")

        # monitor report
        p_monitor_report = monitor_subparsers.add_parser("report", help="生成监控报告")
        p_monitor_report.add_argument("--export", help="导出报告到文件")

        # monitor dashboard
        p_monitor_dashboard = monitor_subparsers.add_parser(
            "dashboard", help="监控仪表板"
        )
        p_monitor_dashboard.add_argument(
            "--html", action="store_true", help="生成HTML仪表板"
        )
        p_monitor_dashboard.add_argument("--export", help="导出仪表板数据")

    args = parser.parse_args(argv)
    debug = getattr(args, "debug", False)

    try:
        return _dispatch(args, parser)
    except Exception as e:  # defensive fallback
        if debug:
            import traceback

            traceback.print_exc()
        else:
            print(f"❌ {e.__class__.__name__}: {e}")
            print("  使用 --debug 查看完整错误栈")
        return 1


def _dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.command == "init":
        return cmd_init(args)
    elif args.command == "compile":
        return cmd_compile(args)
    elif args.command == "derive":
        return cmd_derive(args)
    elif args.command == "check":
        return cmd_check(args)
    elif args.command == "graph":
        return cmd_graph(args)
    elif args.command == "report":
        return cmd_report(args)
    elif args.command == "evolve":
        return cmd_evolve(args)
    elif args.command == "verify":
        return cmd_verify(args)
    elif args.command == "extract":
        return cmd_extract(args)
    elif args.command == "stats":
        return cmd_stats(args)
    elif args.command == "export":
        return cmd_export(args)
    elif args.command == "sync":
        return cmd_sync(args)
    elif args.command == "completion":
        return cmd_completion(args)
    else:
        parser.print_help()
        return 0
