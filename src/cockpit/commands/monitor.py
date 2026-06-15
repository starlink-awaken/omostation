import os
import time
from pathlib import Path
import yaml
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.console import Console

def get_workspace_root() -> Path:
    # 递归向上寻找 .omo 目录，以定位 workspace root
    current = Path.cwd()
    while current != current.parent:
        if (current / ".omo").exists():
            return current
        current = current.parent
    # 默认 fallback
    return Path("/Users/xiamingxing/Workspace")

def read_sandbox_drafts(root: Path) -> list[str]:
    sandbox_dir = root / "runtime" / "sandbox"
    drafts = []
    if sandbox_dir.exists():
        for f in sandbox_dir.glob("OpenSpec-*.md"):
            drafts.append(f.name)
    return drafts

def read_omo_tasks(root: Path, state: str) -> list[dict]:
    target_dir = root / ".omo" / "tasks" / state
    tasks = []
    if target_dir.exists():
        for f in target_dir.glob("*.yaml"):
            try:
                with open(f, "r", encoding="utf-8") as file:
                    data = yaml.safe_load(file)
                    if data:
                        tasks.append(data)
            except Exception:
                # 并发控制：如果 omo_bridge 正在写文件，可能读到残缺 YAML
                # 此处保持静默，等待下一个 1.5s 周期重试
                pass
    return tasks

def generate_layout(root: Path) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main")
    )
    layout["main"].split_row(
        Layout(name="sandbox", ratio=1),
        Layout(name="planned", ratio=1),
        Layout(name="active", ratio=1),
    )
    
    # 顶部状态栏
    layout["header"].update(Panel(
        "[bold cyan]eCOS v5 C2G 双擎编排监控大盘[/] | [bold red][READ-ONLY 严禁在此修改][/] | 轮询间隔: 1.5s", 
        box=box.ROUNDED
    ))
    
    # 左侧: Sandbox
    drafts = read_sandbox_drafts(root)
    sandbox_table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE, expand=True)
    sandbox_table.add_column("草稿文件")
    for d in drafts:
        sandbox_table.add_row(f"📝 {d}")
    layout["sandbox"].update(Panel(sandbox_table, title=f"🧠 Sandbox (发散区) [{len(drafts)}]", border_style="magenta"))
    
    # 中间: Planned (含被拦截或待执行的 OMO CARDS)
    planned = read_omo_tasks(root, "planned")
    planned_table = Table(show_header=True, header_style="bold yellow", box=box.SIMPLE, expand=True)
    planned_table.add_column("ID", style="dim")
    planned_table.add_column("任务名称")
    for t in planned:
        planned_table.add_row(t.get("id", "UNK"), t.get("title", "Unknown"))
    layout["planned"].update(Panel(planned_table, title=f"⏳ Planned (预检/拦截区) [{len(planned)}]", border_style="yellow"))
    
    # 右侧: Active (真正流入执行区的任务)
    active = read_omo_tasks(root, "active")
    active_table = Table(show_header=True, header_style="bold green", box=box.SIMPLE, expand=True)
    active_table.add_column("ID", style="dim")
    active_table.add_column("任务名称")
    for t in active:
        active_table.add_row(t.get("id", "UNK"), t.get("title", "Unknown"))
    layout["active"].update(Panel(active_table, title=f"🚀 Active (执行区) [{len(active)}]", border_style="green"))
    
    return layout

def cmd_monitor(args):
    console = Console()
    root = get_workspace_root()
    
    try:
        with Live(generate_layout(root), refresh_per_second=1, screen=True) as live:
            while True:
                time.sleep(1.5)
                live.update(generate_layout(root))
    except KeyboardInterrupt:
        console.print("[dim]退出 C2G 监控大盘。[/]")
        return 0
