"""cockpit iterate command — C2G 双擎编排流宏入口"""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console

console = Console()


def cmd_iterate(args) -> int:
    console.print("[bold cyan]🔄 正在启动 C2G 双擎编排流 (Creative-to-Governance)...[/]")

    topic = getattr(args, "topic", "未命名探索主题")

    console.print("\n[bold yellow]► Phase 1: 认知发散 (MetaOS Sandbox)[/]")
    console.print(f"主题: '{topic}'")

    spec_path = Path("OpenSpec.md")

    if getattr(args, "mock", False):
        console.print("[dim]Mock 模式: 自动生成含 TODO 的示例 OpenSpec.md...[/]")
        spec_path.write_text(f"# {topic}\n- [ ] TODO: 补充详细需求\n- [ ] 实现核心模块")
    else:
        if not spec_path.exists():
            console.print("[dim]创建空白 OpenSpec.md 契约草案...[/]")
            spec_path.write_text(f"# {topic}\n\n## 目标\n\n## 任务拆解\n- [ ] 设计模块A\n")
        console.print("提示: 您的草稿必须包含 '- [ ] 任务名' 列表，且不得包含 TODO/TBD 等未决项。")

    console.print("\n[bold yellow]► Phase 2/3: Model-Driven 桥接与 OMO 预检 (Devil's Gatekeeper)[/]")
    if not spec_path.exists():
        console.print("[red]错误: 未发现 OpenSpec.md 契约草案。[/]")
        return 1

    console.print(f"正在读取 {spec_path}，执行降维拦截与写入 OMO 稳态区...")

    # Locate omo project dir relative to cockpit
    omo_dir = Path(__file__).resolve().parents[5] / "projects" / "omo"
    if not omo_dir.exists():
        console.print(f"[red]错误: 无法定位 OMO 域: {omo_dir}[/]")
        return 1

    cmd = ["uv", "run", "omo", "bridge", "--format", "openspec", str(spec_path.absolute())]

    result = subprocess.run(cmd, cwd=str(omo_dir), check=False)

    if result.returncode != 0:
        console.print("\n[bold red]❌ C2G 编排中断: 契约预检失败或 OMO 拒收。[/]")
        console.print(
            "[dim]Devil's Gatekeeper 已触发：由于存在 TODO/TBD 等不确定项，不允许进入 OMO 执行态。请在 MetaOS 层面将其思考清楚。[/]"
        )
        return 1

    console.print("\n[bold green]✅ C2G 编排成功: 创意已安全降维，落盘为 OMO CARDS。[/]")
    return 0
