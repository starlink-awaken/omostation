"""cockpit iterate command — C2G 双擎编排流宏入口"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import yaml
from rich.console import Console
from rich.prompt import Confirm

console = Console()


def cmd_iterate(args) -> int:
    console.print("[bold cyan]🔄 正在启动 C2G 双擎编排流 (Creative-to-Governance)...[/]")

    topic = getattr(args, "topic", "未命名探索主题")

    workspace_root = Path(__file__).resolve().parents[5]
    sandbox_dir = workspace_root / "runtime" / "sandbox"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    omo_dir = workspace_root / "projects" / "omo"

    # [C2G v2] 解法二: 架构双轨制与“免签快车道”
    is_fast_track = Confirm.ask(
        "\n[bold magenta]❓ 认知复杂度分级 (Cognitive Triage):[/]\n"
        "这是一项复杂度极低的微观任务吗？(选 y 将触发 Fast-Track 免签快车道，跳过沙箱与架构审查)",
        default=False,
    )

    if is_fast_track:
        console.print("\n[bold yellow]► 🚀 触发 Mode B: Fast-Track 免签快车道[/]")
        task_id = f"FAST-{int(time.time())}"
        fast_task = {
            "id": task_id,
            "title": topic,
            "status": "candidate",
            "task_type": "feature",
            "risk_level": "L0",
            "depends_on": [],
            "source_docs": [],
            "deliverables": ["直接代码修改"],
            "imported_via": "fast_track_cli",
            "context_uri": f"bos://memory/fast-track/{task_id}",
            "evidence_required": ["代码修改自证"],
            "test_plan": ["冒烟测试"],
            "allowed_operation_level": "L0",
            "human_approval_required": False,
        }
        planned_dir = omo_dir / "tasks" / "planned"
        planned_dir.mkdir(parents=True, exist_ok=True)
        task_file = planned_dir / f"{task_id}.yaml"
        task_file.write_text(yaml.dump(fast_task, allow_unicode=True, sort_keys=False))

        console.print(
            f"[bold green]✅ Fast-Track 成功: 已直接落盘为 OMO CARDS ({task_id}.yaml)，立即进入 GSD 模式。[/]"
        )
        return 0

    console.print("\n[bold yellow]► Phase 1: 认知发散 (Mode A: MetaOS Sandbox)[/]")
    console.print(f"主题: '{topic}'")

    # 强制将发散期的契约隔离在 runtime 沙箱目录
    spec_path = sandbox_dir / f"OpenSpec-{topic.replace(' ', '_')}.md"

    if getattr(args, "mock", False):
        console.print(f"[dim]Mock 模式: 自动生成含 TODO 的示例 {spec_path.name}...[/]")
        spec_path.write_text(f"# {topic}\n- [ ] TODO: 补充详细需求\n- [ ] 实现核心模块")
    else:
        if not spec_path.exists():
            console.print(f"[dim]创建 5-Stage 深度审查契约草案: {spec_path.name}...[/]")
            template = f"""# {topic}

## 0.1 竞品与现状调研 (Research & Benchmarking)
> [强制要求] AI 必须在此处填写真实调研：
> 1. 系统内部是否已有现成代码/组件？
> 2. 开源界/工业界是否有成熟对标物？
> 3. 证明“为什么必须自研或二次开发”？

## 0.2 关键决策对齐 (Critical Decisions)
> [强制要求] AI 必须抛出至少 3 个影响全局架构的关键选择题，并给出推荐意见。用户需在此作答。
> 1. [决策点1] ?
>    - AI推荐:
>    - 您的选择:
> 2. [决策点2] ?
>    - AI推荐:
>    - 您的选择:
> 3. [决策点3] ?
>    - AI推荐:
>    - 您的选择:

---

## 1. 方案细化与定型 (Solution Refinement)
> 基于上方决策，明确最终的 What (具体做什么) 和 Why (核心逻辑)。

## 2. 可行性与必要性审查 (Feasibility & Necessity)
> 真的需要造这个轮子吗？现有的 5+4+1+1 机制不能满足吗？ROI 如何？

## 3. 架构审查 (Architecture Review)
> 放在哪一层最合理？是否跨层调用？BOS 域映射对吗？

## 4. 治理审查 (Governance Review)
> 是否违反 X1-X4 约束？是否会引入新的 OMO Debt？如何平滑演进？

## 5. 红队分析 (Red Team Analysis - Devil's Advocate)
> 强制写出 3 种最糟糕的失败场景、并发冲突或极端边界情况。

## 6. 用户视角审查 (User Perspective)
> 从最终使用者（如 Indie Dev）角度，抓手好用吗？概念容易理解吗？

## 7. 质量保障 (Quality Assurance)
> [强制要求] 必须填写以下两项，用于后续的 OMO 预检门控与 M2 防腐层校验。
### 7.1 测试计划 (Test Plan)
- [X1-X4 Governance] 必须在代码实现前完成治理与架构依赖的白盒分析。
### 7.2 验收证据 (Evidence Required)
- X1-X4 治理合规自证
- 单测覆盖率

---

## 🎯 任务拆解 (GSD Action Items)
> 警告：下方列表不得包含 TODO/TBD。必须是可以直接由 OMO 领卡执行的确定性原子指令。
- [ ] 任务1:
"""
            spec_path.write_text(template)
        console.print("提示: 请完成 5 级深度审查，并确保最后只剩下确定的 '- [ ]' 任务列表。")

    console.print("\n[bold yellow]► Phase 2/3: Model-Driven 桥接与 OMO 预检 (Devil's Gatekeeper)[/]")
    if not spec_path.exists():
        console.print("[red]错误: 未发现 OpenSpec.md 契约草案。[/]")
        return 1

    console.print(f"正在读取 {spec_path}，执行降维拦截与写入 OMO 稳态区...")

    # Locate omo project dir relative to cockpit
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
