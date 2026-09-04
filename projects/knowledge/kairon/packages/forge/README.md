---
title: README
type: doc
---

# Forge — 个人 AI 数字资产管理中心

[![Tests](https://img.shields.io/badge/tests-294%20passed-brightgreen)]()

Forge 是跨项目的统一工具注册、发现与治理层。它维护单一真相源（SSOT）的工具清单，暴露 MCP 工具集，并构建工具之间的知识图谱。

## 核心功能

| 功能 | 说明 |
|------|------|
| **工具注册表** | `tools-registry.json` — 167 工具的 SSOT，含 capabilities、health、telemetry |
| **统一配置** | `forge_config.py` — 所有路径常量、环境变量的单一入口 |
| **资产 CLI** | `asset_cli.py` — 统一的 asset 模型（v3/v4），支持 16 种实体类型 |
| **MCP Server** | `server/mcp_server.py` — 24 个 MCP 工具暴露注册表能力 |
| **HTTP API** | `http_api.py` — REST 查询 + 导出，167 资产/37 分类 |
| **CLI 引擎** | `forge.py` — 57 个命令统一注册表（装饰器分发，零 shell 调用） |
| **知识图谱** | `build_graph.py` + `query_graph.py` — 构建与查询 tool→capability→category 关系图 |
| **注册表同步** | `sync_registry.py` — 生成 Markdown 快照 + 日志截断 + Agora 事件 |
| **验证系统** | `verify.py` — Phases 1/2/3 闭环验证，纯 Python 实现 |
| **反熵系统** | `entropy.py` — 候选池（sunrise）、过期标记（sunset）、收敛检查 |
| **健康检查** | `health_check.py` — 每日健康巡检，11 项检查 |
| **看门狗** | `watchdog.py` — 后台守护进程监视关键路径与状态变化 |
| **Web 看板** | `dashboard.html` — 浏览器状态看板，实时项目概览，支持 CSV 导出 |
| **定时任务** | `cron_manager.py` + `cron_utils.py` — 统一管理 macOS launchd 定时任务 |

## 快速开始

```bash
# 安装
pip install -e .

# 运行测试
make test          # pytest tests/ -v
make lint          # ruff check src/ tests/
make format        # ruff format src/ tests/

# CLI
python3 -m forge --help
python3 src/forge.py health
python3 src/forge.py asset list
```

## 项目结构

```
Forge/
├── src/                    # Python 源码（核心模块）
│   ├── forge.py            # 主 CLI（57 命令统一注册表）
│   ├── forge_config.py     # 统一配置（路径/环境变量）
│   ├── asset_cli.py        # 统一资产模型 (v3/v4)
│   ├── http_api.py         # REST API（12 端点）
│   ├── build_graph.py      # 知识图谱构建
│   ├── query_graph.py      # 图谱查询
│   ├── recommend.py        # 知识推荐
│   ├── discover_links.py   # 自动关联发现
│   ├── verify.py           # 三阶段闭环验证
│   ├── sync_registry.py    # 注册表同步/Markdown 生成
│   ├── entropy.py          # 反熵系统
│   ├── health_check.py     # 健康巡检
│   ├── cron_manager.py     # 定时任务管理
│   ├── cron_utils.py       # 定时任务共享工具
│   ├── watchdog.py         # 看门狗守护进程
│   └── graph_*.py          # 图谱工具与可视化
├── server/                 # MCP Server
│   └── mcp_server.py       # 24 个 MCP 工具
├── scripts/                # 运维脚本（逐步迁移中）
│   └── rss-manager.py      # RSS 源管理
├── adapters/               # 外部系统桥接
│   ├── kos-bridge.sh
│   └── sync-agora.sh
├── tests/                  # 测试套件（294 tests）
├── tools-registry.json     # 主注册表（167 tools）
├── assets/                 # 统一资产注册表
│   └── registry.json       # v4 格式，9 类实体
└── docs/                   # 架构文档 + 定时任务清册
```

## RSS 源管理

```bash
# 列出所有 RSS 源
cd scripts && python3 rss-manager.py list

# 启用/禁用源
python3 rss-manager.py enable <id>
python3 rss-manager.py disable <id>

# 同步到 kronos
python3 rss-manager.py sync
```

## 定时任务管理

所有定时任务统一注册在 `assets/registry.json → entities.cron`，通过 `forge cron` 管理。

```bash
# 列出所有定时任务（41 个）
forge cron list

# 启用/禁用
forge cron enable forge-daily-maintenance
forge cron disable ai-toolbox-health-check

# 查看任务详情
forge cron status forge-weekly-report

# 注册新任务
forge cron register "my-task" --schedule "0 9 * * *" --script "check.sh" --desc "每日检查"

# macOS 提醒事项
forge cron reminder "friday-check" --title "周末检查" --body "过一遍待办" --schedule "每周五 9:00"
forge cron reminder-remove "候诊"      # 按关键词删除提醒
```

任务按时间维度分 4 类，详见 `docs/901-cron-inventory.md`。

## MCP 工具集

Forge MCP Server 提供 24 个工具，可通过 Claude Code 等 AI Agent 调用：

| 分类 | 工具 | 说明 |
|------|------|------|
| **工具注册表** | `list_tools`, `get_tool_info`, `search_tools` | 工具查询与发现 |
| **推荐/发现** | `recommend`, `discover_links` | 基于图谱的推荐与关联发现 |
| **资产 CRUD** | `asset_register`, `asset_remove`, `asset_scan` | 资产注册/删除/扫描 |
| **图谱** | `get_tool_graph`, `build_graph`, `query_graph`, `generate_graph_viz` | 知识图谱查询与构建，可视化 |
| **分类** | `list_categories` | 工具分类统计 |
| **项目状态** | `get_project_status` | 项目整体状态概览 |
| **定时任务** | `list_cron_jobs`, `update_cron_job` | 定时任务启停 |
| **运维** | `run_health_check`, `run_sniff`, `run_entropy`, `run_sediment` | 健康检查/嗅探/反熵/沉淀 |
| **验证** | `run_verify`, `run_classify` | 资产验证与自动分类 |
| **洞察** | `run_insight` | 周报/缺口分析 |

## CLI 命令一览

通过 `forge <command>` 调用，~30 个命令覆盖全功能：

```bash
# 运维
forge health              # 健康检查
forge sniff               # 环境嗅探
forge status              # 项目状态

# 图谱
forge build-graph         # 构建知识图谱
forge query-graph         # 查询图谱
forge recommend           # 知识推荐

# 工具管理
forge asset list          # 资产清册
forge asset scan          # 自动发现
forge asset register ...  # 注册工具

# 定时任务
forge cron list           # 列出定时任务
forge cron enable xxx     # 启用任务

# 内容
forge insight --weekly    # 周报
forge capture ...         # 记新工具
forge rss list            # RSS 源管理
```

## 架构决策

- **扁平模块布局**: `src/` 下为独立模块（非包），通过 `py_modules` 安装
- **类型归一化**: `orchestrator` → `daemon`, `feed` → `service` 等映射保证统一模型稳定
- **路径可移植**: 脚本使用 `Path(__file__).resolve().parent.parent` 定位项目根，无硬编码绝对路径

## 开发

- Python ≥3.10
- `ruff` for lint/format (target: py313)
- `pytest` for testing

## License

MIT
