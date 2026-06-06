# Workspace 全面重构与治理对齐路线图

> 编制日期: 2026-05-27
> 当前基线: 58.2% 🟡 (产品健康度) / 72/100 (架构成熟度)
> 下一目标: 85% 🟢
> 文档位置: `~/Documents/学习进化/基建架构/38-Workspace全面重构与治理对齐路线图.md`

---

## 目录

1. [战略方向](#1-战略方向)
2. [根因链与差距分析](#2-根因链与差距分析)
3. [战术路径（5 Wave）](#3-战术路径5-wave)
4. [TASK_POOL 任务定义](#4-task_pool-任务定义)
5. [验收门禁](#5-验收门禁)
6. [风险与缓解](#6-风险与缓解)

---

## 1. 战略方向

### 1.1 核心命题

> **如何让 workspace CLI 成为一个独立、可维护、可扩展的产品级入口，不再寄生在 Hermes Agent 的基础设施上？**

### 1.2 三大战略支柱

```
┌────────────────────────────────────────────────────────────────────┐
│ 支柱1: 项目自洽                               │
│  消除对 ~/.hermes/scripts/ 的路径依赖                              │
│  → scripts/ 迁入项目内 → softlink 到 .hermes/ 保持 cron 兼容       │
│  → pyproject.toml 代替 setup.py                                    │
│  → README.md + docs/ 项目内建文档                                  │
├────────────────────────────────────────────────────────────────────┤
│ 支柱2: 架构可进化                               │
│  storage.py 加抽象层 → 可切换 SQLite/MCP/HTTP 后端                 │
│  cli.py 按命令模块拆分 → 降低 2602 行认知负载                      │
│  统一错误处理框架 → 消除散落 try/except                             │
├────────────────────────────────────────────────────────────────────┤
│ 支柱3: 治理可观测                               │
│  产品健康度自动监控运行中 → 双基线对比每周推送                      │
│  半衰期驱动保鲜决策 → 在 daily/status 中可视化                     │
│  64 测试基线 → 每模块独立测试 + E2E 门禁                           │
└────────────────────────────────────────────────────────────────────┘
```

### 1.3 约束条件

- 30/70 原则：治理投入 ≤30%，产品功能 ≥70%
- 每次变更必须保持 64 tests 全绿
- 所有脚本迁入后，软链保持 cron 运行不中断

---

## 2. 根因链与差距分析

### 2.1 根因链 1：历史寄生

```
workspace 最初是 Hermes Agent 的一个附属物
→ 脚本自然放在 ~/.hermes/scripts/ (共用 cron 调度器)
→ product-health 作为 Phase A 产物直接写在那里
→ Phase B/C/D 延续了这个习惯
→ 现在 6 个脚本寄生在外部，但只读 workspace 数据
```

**影响**：无法脱离 Hermes 独立部署、版本管理分裂（脚本不参与 wksp git）

### 2.2 根因链 2：架构不做抽象

```
storage.py 直接暴露 sqlite3.connect()
→ cli.py 里 cmd_daily/cmd_status cmd_dashboard 也都各自 sqlite3.connect()
→ 没有任何地方检查 DB_PATH 是否可达
→ 要切换后端（如走 Agora MCP 调用）得改所有文件
```

**影响**：L2 能力层永远锁死在 SQLite 上

### 2.3 差距分析

| 维度 | 当前 | 目标 | 差距 | 核心缺失 |
|------|------|------|------|---------|
| **项目自洽** | 文档0%, scripts 100%在外部 | 文档80%, scripts 全迁入 | 🔴 80pp | scripts/ + README + docs/ |
| **架构抽象** | 0 抽象层, 直接 sqlite3 | IDataAccess 接口 + dict适配 | 🔴 80pp | 接口定义+实现分离 |
| **模块拆分** | cli.py 2602行 1文件 | ≤400行/模组, 6-8文件 | 🟡 60pp | commands/ 目录 |
| **错误处理** | 散落 try/except | 统一 Err 框架 | 🟡 50pp | ErrorChain + 回调 |
| **配置系统** | 硬编码 path/port | ~/.workspace/config.toml | 🔴 70pp | 配置读入+覆盖 |
| **测试覆盖** | 64 tests (单元+E2E) | 80+ tests (含集成) | 🟡 20pp | 后端切换测试 |
| **产品体验** | 半衰期已算但未展示 | daily/status 显示 decay | 🟢 10pp | 半衰期可视化 |
| **治理对齐** | 健康度58.2% | 85% 🟢 | 🟡 27pp | 文档+抽象+拆分 |

---

## 3. 战术路径（5 Wave）

### Wave 13.1: 解耦 ⭐ 当前入口

**目标**：消除对 `~/.hermes/scripts/` 的路径依赖，项目具备独立文件结构

**交付清单**：

| # | 任务 | 文件 | 估时 |
|---|------|------|------|
| T001 | 创建 `wksp/scripts/` 目录，迁入6个脚本：product-health, freshness-watch, health-monitor, dual-baseline, auto-archive, agora-register-workspace | `scripts/` | 20min |
| T002 | 创建软链：`~/.hermes/scripts/<name>` → `~/Workspace/wksp/scripts/<name>`，保持 cron 调度不中断 | shell | 10min |
| T003 | 更新 `cli.py` 引用路径：`product-health` 从 `Path.home()/".hermes/scripts/..."` → 相对项目路径 | `cli.py` | 10min |
| T004 | 更新所有 cron job 的 script 路径指向软链（确认软链即可，不做额外变更） | 验证 | 10min |
| T005 | 建 `pyproject.toml` 代替 `setup.py`（Python 3.14 生态） | `pyproject.toml` | 15min |

**门禁**：
```bash
cd ~/Workspace/wksp && /opt/homebrew/bin/python3.14 -m pytest -q   # 64 passed
ls -la ~/.hermes/scripts/product-health | grep "\.\."              # 是软链不是副本
PYTHONPATH=.. /opt/homebrew/bin/python3.14 -m wksp product-health  # 还能跑
```

---

### Wave 13.2: 文档基建

**目标**：项目内建完整文档体系，消除"文档在外部"的短板

**交付清单**：

| # | 任务 | 文件 | 估时 |
|---|------|------|------|
| T006 | 写 README.md：愿景、快速开始、命令清单、架构概览 | `README.md` | 30min |
| T007 | 写 docs/ARCHITECTURE.md：4+1+3+P0 架构说明、closing the loop 图 | `docs/ARCHITECTURE.md` | 30min |
| T008 | 写 docs/COMMANDS.md：所有命令的完整参考、参数、示例 | `docs/COMMANDS.md` | 20min |
| T009 | 写 docs/CONTRIBUTING.md：开发指南、测试规范、PR 流程 | `docs/CONTRIBUTING.md` | 15min |
| T010 | 清理空目录：删除空的 `eidos/`、`agora/`（如果无内容） | 项目根 | 5min |

**门禁**：
```bash
ls README.md docs/ARCHITECTURE.md docs/COMMANDS.md docs/CONTRIBUTING.md  # 全存在
head -5 README.md | grep -q "workspace"                                    # 有内容
pytest -q                                                                  # 64 passed
```

---

### Wave 13.3: 架构抽象

**目标**：storage.py 加接口层，消除"玻璃门"

**交付清单**：

| # | 任务 | 文件 | 估时 |
|---|------|------|------|
| T011 | 定义 IDataAccess 接口协议：`class IDataAccess(Protocol): save/get/list/search/set_tags/...` | `storage.py` | 20min |
| T012 | 实现 SQLiteDataAccess 适配器：将现有 storage 函数封装为类方法 | `storage.py` | 30min |
| T013 | 创建全局 accessor：`get_data_access() -> IDataAccess`，单例懒加载 | `storage.py` | 10min |
| T014 | 重构 cli.py 入口：导入 `get_data_access()`，不再直接 import storage | `cli.py` | 20min |
| T015 | 添加 IDataAccess 的后端切换验证测试：mock 实现 + 验证 storage 函数可 mock 替换 | `tests/` | 20min |

**门禁**：
```bash
pytest -q                                  # 64 passed
# 代码确认：cli.py 里无 "from . import storage" 之外的直连
grep -c "sqlite3.connect" cli.py           # 只有 storage.py 里有
python3 -c "from wksp.storage import IDataAccess, SQLiteDataAccess, get_data_access; print('✅')"
```

---

### Wave 13.4: 模块拆分

**目标**：cli.py 2602行 → 按命令分组拆为 6-8 文件

**交付清单**：

| # | 任务 | 文件 | 估时 |
|---|------|------|------|
| T016 | 创建 `commands/__init__.py` + `commands/base.py` 共享工具 | `commands/` | 10min |
| T017 | 拆出 `commands/research.py`：所有 research_* 命令（~600行） | `commands/research.py` | 30min |
| T018 | 拆出 `commands/contracts.py`：contracts 相关命令（~300行） | `commands/contracts.py` | 20min |
| T019 | 拆出 `commands/status.py`：status/daily/dashboard/help（~400行） | `commands/status.py` | 20min |
| T020 | 拆出 `commands/profile.py` + `commands/governance.py`（~200行） | `commands/` | 15min |
| T021 | cli.py main() 收缩为：import handlers + parser 定义 + dispatch（~300行） | `cli.py` | 20min |
| T022 | 更新 `__init__.py`、`__main__.py`、所有 test import 路径 | `__init__.py` 等 | 15min |

**门禁**：
```bash
pytest -q                                  # 64 passed
wc -l cli.py | awk '{print $1}'             # ≤500行
python3 -c "from wksp.commands.research import *; print('✅')"
```

---

### Wave 13.5: 体验 + 治理

**目标**：半衰期可视化、产品健康度提升到 85%

**交付清单**：

| # | 任务 | 文件 | 估时 |
|---|------|------|------|
| T023 | daily 中显示每条研究的半衰期 decay 值（0.0-1.0 绿色→黄色→红色） | `cli.py` | 20min |
| T024 | status 工作台增加半衰期概览行（活跃/保鲜/荒废计数） | `cli.py` | 15min |
| T025 | freshness-watch cron 的推送消息改为更可读（含趋势） | `scripts/freshness-watch` | 15min |
| T026 | 补全缺失的错误处理：import 的 URL 解析错误、research 的存储错误 | `cli.py` | 20min |
| T027 | 治理对齐：更新 product-health 公式，反映新架构能力（半衰期/heatmap/agent 等权重） | `scripts/product-health` | 15min |

**门禁**：
```bash
pytest -q                                  # 64+ passed
PYTHONPATH=.. python3 -m wksp daily        # 显示 decay 值
PYTHONPATH=.. python3 -m wksp product-health  # ≥80%
```

---

## 4. TASK_POOL 任务定义

以下为 `.omo/TASK_POOL.md` 的追加内容：

### Phase 13: Workspace 全面重构与治理对齐

| ID | Task | Phase→Wave | 状态 | Dependencies |
|----|------|-----------|------|-------------|
| T001 | 创建 `wksp/scripts/` 迁入6个外部脚本 | P13→13.1 | backlog | — |
| T002 | 软链保持 cron 兼容 | P13→13.1 | backlog | T001 |
| T003 | 更新 cli.py 引用路径 | P13→13.1 | backlog | T001 |
| T004 | 验证 cron 脚本路径一致性 | P13→13.1 | backlog | T002 |
| T005 | pyproject.toml 代替 setup.py | P13→13.1 | backlog | — |
| T006 | 写 README.md | P13→13.2 | backlog | — |
| T007 | 写 docs/ARCHITECTURE.md | P13→13.2 | backlog | — |
| T008 | 写 docs/COMMANDS.md | P13→13.2 | backlog | — |
| T009 | 写 docs/CONTRIBUTING.md | P13→13.2 | backlog | — |
| T010 | 清理空目录 eidos/ + agora/ | P13→13.2 | backlog | — |
| T011 | 定义 IDataAccess 接口 Protocol | P13→13.3 | backlog | — |
| T012 | 实现 SQLiteDataAccess 适配器 | P13→13.3 | backlog | T011 |
| T013 | 创建全局 accessor: get_data_access() | P13→13.3 | backlog | T012 |
| T014 | 重构 cli.py 入口改用 accessor | P13→13.3 | backlog | T013 |
| T015 | 添加后端切换验证测试 | P13→13.3 | backlog | T014 |
| T016 | 创建 commands/ 目录 + base.py | P13→13.4 | backlog | T014 |
| T017 | 拆出 commands/research.py | P13→13.4 | backlog | T016 |
| T018 | 拆出 commands/contracts.py | P13→13.4 | backlog | T016 |
| T019 | 拆出 commands/status.py | P13→13.4 | backlog | T016 |
| T020 | 拆出 commands/profile.py + governance.py | P13→13.4 | backlog | T016 |
| T021 | cli.py main() 收缩为 dispatch 入口 | P13→13.4 | backlog | T017-T020 |
| T022 | 更新 __init__.py + 所有 test imports | P13→13.4 | backlog | T021 |
| T023 | daily 显示半衰期 decay | P13→13.5 | backlog | T006 |
| T024 | status 工作台增加半衰期概览 | P13→13.5 | backlog | T006 |
| T025 | freshness-watch 推送优化 | P13→13.5 | backlog | — |
| T026 | 补全缺失错误处理 | P13→13.5 | backlog | — |
| T027 | 更新 product-health 公式 | P13→13.5 | backlog | T005 |

---

## 5. 验收门禁

### 5.1 全 Phase 门禁

```bash
# 代码质量
pytest -q                                   # 64+ passed
ruff check .                                # 0 errors

# 架构完整性
PYTHONPATH=.. python3 -m wksp --help        # 入口正常
PYTHONPATH=.. python3 -m wksp daily         # 半衰期可视化
PYTHONPATH=.. python3 -m wksp product-health # ≥80%
PYTHONPATH=.. python3 -m wksp status        # 工作台正常
PYTHONPATH=.. python3 -m wksp research --heatmap  # 热力图

# 解耦验证
ls ~/.hermes/scripts/product-health         # 软链存在
test -L ~/.hermes/scripts/product-health    # 是软链不是副本
```

### 5.2 每 Wave 自检规则

- Wave 完成时：当前 wave 所有测试通过 + 下个 wave 的依赖具备
- 连续 2 个 wave 失败 → 停下复盘
- 每 wave 治理投入 ≤30%（约 1/3 任务是治理性质的）

---

## 6. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 软链迁移后 cron 找不到脚本 | 低 | 高 | 先建软链再删除源文件，保持窗口期双份存在 |
| 拆 cli.py 时引入 import 循环 | 中 | 中 | 用 Protocol 接口 + 懒加载，不用 cross-import |
| pyproject.toml 与现有 setup.py 冲突 | 低 | 中 | 保留 setup.py 作为 fallback 直到验证 pyproject 可用 |
| 半衰期 decay 展示增加 daily 加载时间 | 低 | 低 | 每个研究只做一次 timeline 查询，limit=50 |
| IDataAccess 重构破坏现有测试 | 中 | 高 | 先写接口再改实现，保持单测隔离 |

---

> **下一步**：确认后进入 Wave 13.1 — 脚本迁移 + 软链 + pyproject.toml
