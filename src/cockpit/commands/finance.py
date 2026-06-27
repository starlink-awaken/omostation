"""cockpit.commands.finance — 个人财务门户引导 (产品走查 BET-6 #6B868907 全场景门户).

C 方案 (仿 gongwen): cockpit 作为门户加轻量财务引导命令 (保持 KISS, 不实现财务逻辑);
个人财务能力保持在 @个人 域独立演进. 参见全局 CLAUDE.md §3 路由 (@个人: 个人事务·健康·财务).
理由: 财务是个人垂直域 (记账/预算/税务/保险), 塞进通用 cockpit 会耦合违 SRP;
但 cockpit 作为门户应能发现引导 — 这就是这扇门 (B 方案能力留在 @个人 域独立).
"""

from __future__ import annotations

from argparse import Namespace

from .base import _get_console, _panel

# 个人财务常见场景 — 仅引导描述, 非财务逻辑实现
_FINANCE_SCENARIOS: list[tuple[str, str]] = [
    ("收支记录", "日常收入支出记账, 收支两条线, 量入为出"),
    ("预算管理", "月度/年度预算编制与执行追踪, 控制非必要支出"),
    ("资产管理", "存款/投资/房产等资产盘点与配置, 复利长期主义"),
    ("负债管理", "房贷/车贷/信用卡等负债规划, 优化还款结构"),
    ("税务规划", "个税/年终奖/专项附加扣除, 合规优化税负"),
    ("保险保障", "社保/商业险配置, 应急储备 (3-6 月家庭支出)"),
]


def cmd_finance(_args: Namespace) -> int:
    """个人财务门户引导 — 列场景/原则/入口, 引导用户到 @个人 域 (不实现财务逻辑)."""
    console = _get_console()
    console.print(_panel("[bold cyan]💰 个人财务门户[/]", "cyan"))

    console.print("\n[bold]📊 常见场景:[/]")
    for name, desc in _FINANCE_SCENARIOS:
        console.print(f"  [cyan]·[/] [bold]{name}[/] — {desc}")

    console.print("\n[bold]📐 理财原则:[/]")
    console.print("  [dim]·[/] 收支两条线 / 量入为出 / 先储蓄后消费")
    console.print("  [dim]·[/] 应急储备 3-6 月家庭支出 (流动性优先)")
    console.print("  [dim]·[/] 风险分散 / 资产配置 (不把鸡蛋放一个篮子)")
    console.print("  [dim]·[/] 定期复盘: 月度对账 → 季度调整 → 年度预算")

    console.print("\n[bold green]🚪 管理入口:[/]")
    console.print("  [cyan]·[/] 个人域: ~/Documents/@个人/ (个人事务 SSOT)")
    console.print("  [cyan]·[/] 家庭健康联动: cockpit scenario health (健康支出)")
    console.print("  [cyan]·[/] 决策 skill: metaos-gate (大额支出决策) / weekly-report (周复盘)")

    console.print("\n[dim]💡 cockpit 只做门户引导; 个人财务能力在 @个人 域独立演进 (保持解耦, 专业逻辑留给垂直域)。[/]")
    return 0
