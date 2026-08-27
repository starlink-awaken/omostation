---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# Phase A — 详细任务分解

> 从 28.5% → 45% 架构对齐度 / 产品健康度 13.7% → 27%
> 估时: 4-6 小时 | 当前状态: ⏳ 待启动

---

## A1: P0 层定义 — 架构文档更新 (20min)

### A1.1: 在 09-* 架构图中增加 P0 层

**文件**: `~/Documents/学习进化/基建架构/09-个人AI操作系统-最终架构方案.md`

**操作**: 在当前架构图最顶部（L4 层之上），插入 P0 层：

```
│  P0: 产品界面层 (UI/Presentation Layer)          [EXISTS/workspace CLI] │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ workspace CLI: 统一用户入口                                   │   │
│  │ research | import | status | daily | demo | help             │   │
│  │ contracts | governance | profile | dashboard                 │   │
│  │ ↑ 回答"怎么用"——不改变下层结构，只提供用户视图                │   │
│  │ ↑ P0 不是独立层，是横切界面——将 L4-L1 + X1-X3 翻译为用户操作 │   │
│  └──────────────────────────────────────────────────────────────┘   │
│├──────────────────────────────────────────────────────────────────────┤
```

**插入位置**: 当前第34行（`┌──`架构图顶部）之后

### A1.2: 在宪法/README 中添加 P0 层描述

**文件**: 根据实际宪法文件位置，添加：
- P0 层定义：产品界面层 = workspace CLI
- 职责：将 L4-L1 + X1-X3 的能力翻译为用户可理解的操作
- 边界：P0 不改变任何下层——每个用户操作在背面调用对应的架构层能力
- 状态: [EXISTS/workspace CLI v0.1.0]

---

## A2: workspace profile (40min)

### A2.1: 创建默认 PERSONA.yaml

**文件**: `~/.workspace/persona.yaml`

```yaml
# Workspace 身份档案
name: "夏铭星"
role: "技术型个人开发者"
timezone: "Asia/Shanghai"
principles:
  - "架构先行，理论驱动"
  - "隐私第一，信息不泄"
  - "结果导向，有家可归"
active_domain: "个人AI操作系统 / eCOS"
created_at: "2026-05-26"
```

### A2.2: 添加 cmd_profile 函数

**文件**: `wksp/cli.py`

在 cmd_help 函数之后（现在是第1543行附近），添加：

```python
_PROFILE_PATH = Path.home() / ".workspace" / "persona.yaml"

def _load_profile() -> dict[str, Any]:
    import yaml
    if _PROFILE_PATH.exists():
        try:
            with open(_PROFILE_PATH) as f:
                return yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError):
            return {}
    return {}

def cmd_profile(args: argparse.Namespace) -> int:
    profile = _load_profile()
    if not profile:
        console.print(Panel.fit(
            "[bold yellow]⚠️ 未设置身份档案[/bold yellow]\n"
            "[dim]运行 [cyan]workspace profile --edit[/] 创建你的身份档案[/dim]",
            border_style="yellow", box=box.ROUNDED,
        ))
        return 0

    from datetime import datetime
    created = profile.get("created_at", "未知")
    console.print(Panel.fit(
        f"[bold cyan]👤 {profile.get('name', '未命名')}[/bold cyan]\n"
        f"[dim]{profile.get('role', '')}[/dim]\n\n"
        f"[bold]时区:[/bold] {profile.get('timezone', '未设置')}\n"
        f"[bold]活跃领域:[/bold] {profile.get('active_domain', '未设置')}\n"
        f"[bold]原则:[/bold]\n" +
        "\n".join(f"  · {p}" for p in profile.get("principles", [])) +
        f"\n\n[dim]档案创建: {created}[/dim]",
        title="📋 身份档案",
        border_style="cyan", box=box.ROUNDED,
    ))
    console.print(Panel.fit(
        "下一步:\n"
        "- [cyan]workspace profile --edit[/] 编辑档案\n"
        "- [cyan]workspace status[/] 打开工作台\n"
        "- [cyan]workspace research \"主题\"[/] 开始研究",
        border_style="cyan", box=box.ROUNDED,
    ))
    return 0
```

### A2.3: 添加 profile 子命令解析器

**文件**: `wksp/cli.py`

在 `sub.add_parser("help", ...)` 之后（2146行），添加：
```python
profile_p = sub.add_parser("profile", help="查看/编辑身份档案")
profile_p.add_argument("--edit", action="store_true", help="编辑身份档案")
```

### A2.4: 添加 profile 命令分发

在 main() 函数中，`if args.command == "help"` 处理块之后，添加：
```python
if args.command == "profile":
    return cmd_profile(args)
```

### A2.5: 在 workbench 中显示 profile 快速入口

**文件**: `wksp/cli.py` 中的 `_render_workbench` 函数

在"快速行动"栏末尾添加 `profile` 入口：
```python
"[dim]|[/dim]   "
"[cyan]profile[/]"
```

### 验证 A2

```bash
workspace profile              # 应显示身份档案
workspace profile --edit       # 应提示(先做简单版,后续支持vim编辑)
workspace status               # 应显示 profile 快速入口
```

---

## A3: product-health 脚本 (30min)

### A3.1: 创建计算脚本

**文件**: `~/.hermes/scripts/product-health`

```python
#!/usr/bin/env python3
"""Workspace 产品健康度计算"""

import json, math, subprocess, sys

def _score() -> dict:
    # 1) 架构对齐度 (来自36-审计的打分 + 动态检测)
    arch_scores = {
        "P0": 0.60, "L4": 0.40, "L3": 0.20, "L2": 0.60,
        "L1": 0.80, "X1": 0.40, "X2": 0.30, "X3": 0.20
    }
    weights = {
        "P0": 0.15, "L4": 0.10, "L3": 0.10, "L2": 0.20,
        "L1": 0.15, "X1": 0.10, "X2": 0.10, "X3": 0.10
    }
    arch_alignment = sum(arch_scores[k] * weights[k] for k in weights)

    # 2) 用户旅程完整度 (检测命令是否存在)
    cmds = ["research", "import", "status", "daily", "demo", "help", "profile",
            "contracts", "governance"]
    existing = 0
    for cmd in cmds:
        r = subprocess.run(["workspace", cmd, "--help"], capture_output=True, text=True)
        if r.returncode == 0 or "用法" in r.stdout:
            existing += 1
    journey = existing / len(cmds)

    # 3) 产品原则满足率 (检测AGENTS.md中门禁)
    principles = 5
    active = 0
    # 每个原则检测一个特征命令
    principle_checks = [
        ("结果优先", existing == len(cmds)),  # 所有命令都存在 = 有家可归
        ("一条路径", existing >= 7),          # 大部分通过workspace进入
        ("旅程完整", existing >= 6),          # 核心旅程命令存在
        ("渐进披露", True),                    # 有help/demo/welcome (Phase 4)
        ("系统有记忆", True),                  # research持久化
    ]
    for _, ok in principle_checks:
        if ok:
            active += 1
    principle_rate = active / principles

    score = arch_alignment * journey * principle_rate
    return {
        "score": round(score * 100, 1),
        "arch_alignment": round(arch_alignment * 100, 1),
        "journey_completeness": round(journey * 100, 1),
        "principle_satisfaction": round(principle_rate * 100, 1),
        "layer_scores": arch_scores,
    }

if __name__ == "__main__":
    s = _score()
    print(f"Product Health Score: {s['score']}%")
    print(f"├── 架构对齐度: {s['arch_alignment']}%")
    print(f"├── 用户旅程完整度: {s['journey_completeness']}%")
    print(f"├── 产品原则满足率: {s['principle_satisfaction']}%")
    print(f"└── Phase A 目标: 27%")
    sys.exit(0 if s['score'] >= 27 else 1)
```

### A3.2: 注册为workspace子命令

直接在 workspace CLI main() 中添加:

```python
if args.command == "product-health":
    subprocess.run([sys.executable, str(Path.home() / ".hermes/scripts/product-health")])
    return 0
```

并在 subparser 中添加:
```python
sub.add_parser("product-health", help="产品健康度检测")
```

### 验证 A3

```bash
workspace product-health
# 应输出:
# Product Health Score: ~15%
# ├── 架构对齐度: 45%
# ├── 用户旅程完整度: ...
# └── Phase A 目标: 27%
```

---

## A4: MCP只读迁移 — research backend 第一步 (90min)

### 背景

当前 workspace CLI 读写 `~/.workspace/data.db` (SQLite)。目标是通过 Agora MCP 调用。

**Phase A 第一步**: 只把**读操作**迁移到 MCP，写操作保持原路径。并行运行验证。

### A4.1: 创建 Agora MCP 研究查询工具

**文件**: 在 Agora 项目的 MCP 服务目录中创建 `research_reader.py`

```python
"""Agora MCP 工具: 只读研究查询 (Phase A 第一步)"""

import sqlite3
from pathlib import Path
from mcp.server import Server, stdio_server

DB_PATH = Path.home() / ".workspace" / "data.db"

def _query(sql: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

async def main():
    server = Server("workspace-research-reader")
    
    @server.list_tools()
    async def list_tools():
        return [
            {
                "name": "research_list",
                "description": "列出研究记录",
                "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}}
            },
            {
                "name": "research_get",
                "description": "获取单个研究详情",
                "inputSchema": {"type": "object", "properties": {"id": {"type": "integer"}}}
            },
            {
                "name": "research_dossier",
                "description": "获取研究关系与发布产物",
                "inputSchema": {"type": "object", "properties": {"id": {"type": "integer"}}}
            },
            {
                "name": "research_timeline",
                "description": "获取研究时间线",
                "inputSchema": {"type": "object", "properties": {"id": {"type": "integer"}}}
            },
        ]
    
    @server.call_tool()
    async def call_tool(name: str, args: dict) -> str:
        if name == "research_list":
            rows = _query("SELECT id, topic, created_at, source_count, summary FROM research ORDER BY id DESC LIMIT ?", (args.get("limit", 10),))
            return json.dumps(rows, ensure_ascii=False, default=str)
        elif name == "research_get":
            row = _query("SELECT * FROM research WHERE id = ?", (args["id"],))
            return json.dumps(row[0] if row else None, ensure_ascii=False, default=str)
        # ... 类似实现 dossier 和 timeline
    
    async with stdio_server(server):
        await server.run()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### A4.2: 注册到 Agora

在 Agora 的 MCP 服务注册表/配置中添加 `research_reader` 条目，使用 stdio 传输。

### A4.3: 更新 workspace CLI 读操作为 MCP 调用

**文件**: `wksp/storage.py` (或创建 `wksp/mcp_client.py`)

```python
"""MCP 客户端 — 调用 Agora MCP 的研究查询"""
import json, subprocess
from typing import Any

def _mcp_call(tool: str, args: dict) -> Any:
    """通过 Agora CLI 调用 MCP 工具"""
    result = subprocess.run(
        ["agora", "mcp", "call", f"workspace-research-reader.{tool}", json.dumps(args)],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)

# 替代 storage.py 中的读方法:
# get_research(id) → _mcp_call("research_get", {"id": id})
# list_research(limit) → _mcp_call("research_list", {"limit": limit})
# get_research_dossier(id) → _mcp_call("research_dossier", {"id": id})
# get_research_timeline(id) → _mcp_call("research_timeline", {"id": id})
```

### A4.4: 并行运行验证

```python
# 在 storage.py 中添加 fallback 机制:
def get_research(research_id):
    try:
        return _mcp_call("research_get", {"id": research_id}) or _sqlite_get(research_id)
    except Exception:
        return _sqlite_get(research_id)  # fallback to direct SQLite
```

### 验证 A4

```bash
# 启动 MCP server
cd agora && python research_reader.py &

# 测试 MCP 调用
agora mcp call workspace-research-reader.research_list '{"limit": 3}'

# 验证 workspace CLI 正常
workspace research --list
workspace research --open 1
workspace research --dossier 1
workspace research --timeline 1
```

---

## A5: 产品健康度首次基线采集 (10min)

```bash
workspace product-health | tee ~/.workspace/health-baseline-phase-a.json
```

输出存档到 `~/.workspace/health-baseline-latest.json` 供后续对比。

---

## A6: 测试验证 (10min)

```bash
cd ~/Workspace/wksp && python3.14 -m pytest -v
# 应: 54 passed (新增profile/product-health测试 + 原有54)

workspace profile              # 应有内容
workspace product-health        # 应输出分数
workspace research --list      # 应正常（MCP或回退SQLite）
```

---

## 执行顺序

```
A1 → A2 → A5 → A3 → A4 → A6
 (架构文档)(profile)(基线)(健康脚本)(MCP迁移)(验证)
    ↓       ↓      ↓       ↓      ↓       ↓
  20min   40min  10min   30min  90min   10min
                      ← 3h10min 总估时 →
```

**并行可能**: A1(文档) + A2(profile) + A3(脚本) 可并行，约50min。A4(MCP) 依赖 A2/A3 完成，是串行瓶颈。

---

## 验收门禁 (通过/不通过)

```bash
workspace profile              # 必须 ≠ "未设置身份档案"
workspace product-health        # 必须 ≥ 15.0 (Phase A 基线起点)
workspace research --list      # 必须能列出研究
workspace product-health        # Phase A 完成后 ≥ 27.0
pytest -q                       # 必须 54 passed
```
