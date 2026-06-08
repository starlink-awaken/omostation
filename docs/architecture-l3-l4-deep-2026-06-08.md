# eCOS v5 · L3-L4 分层架构深度分析

**2026-06-08 · 入口层 + 自我层全解剖**

---

## 一、L4 · 自我层 — 内部架构

### 1.1 架构概览

L4 是纯数据层，不运行代码。19 域分布在 `~/Documents/` 下，通过 cockpit MCP 被动消费。

```
L4 自我层 (19域 · 纯文档)
│
├── DocumentDomain (7域)
│   ├── @驾驶舱 (cockpit)    ← CARDS 目标追踪 + KEMS六面
│   ├── @学习进化 (vault)     ← Obsidian 知识库 (KEMS五面)
│   ├── @个人 (personal)      ← 个人档案 (KEMS五面)
│   ├── @公共 (shared)        ← 公共知识
│   ├── @家庭生活 (family)     ← 家庭管理
│   ├── 卫健委 (work-weijian) ← 卫健工作
│   └── 国转中心 (work-guozhuan) ← 国转工作
│
├── ConfigDomain (3域)
│   ├── ~/.ai (ai-config)
│   ├── ~/.agents (agents-config)
│   └── iCloud SharedConf
│
├── EngineDomain (1域) — Minerva 引擎配置
├── ToolDomain (2域)  — ~/bin + ~/ToolBox
├── WorkspaceDomain (1域) — SharedWork
├── StorageDomain (1域)  — SharedDisk
└── ModelDomain (2域)    — Model + SharedModel
```

### 1.2 CARDS 系统 — 目标追踪核心

```
CARDS/ (65 个卡片)
├── tasks/     — 15 个任务卡片
├── debts/     — 30 个债务卡片
├── deliverys/ — 12 个交付卡片
├── ideas/     — 5 个想法卡片
└── researchs/ — 3 个研究卡片

SSOT 模型:
  data/cards/cards.db (SQLite)  ← 唯一真源
       ↓ cards generate
  CARDS/*.md                    ← 自动生成视图
```

**卡片生命周期**:
```
Idea:  flash → incubating → promoted|discarded (14天孵化上限)
Task:  planned → active → blocked → done|cancelled
Debt:  open → in_progress → resolved|closed
Delivery: planned → in_progress → done
Research: planned → active → publish
```

### 1.3 Vault 知识库 — @学习进化

**KEMS 五面结构** (Knowledge Entity Memory Storage):
```
_control/    — STATE/MEMORY/INDEX/STATUS/signals/TIMELINE (控制面)
_entities/   — 实体定义 SSOT
_knowledge/  — 10-systems/20-creative/30-distribution/40-lessons/50-concepts
_storage/    — 资料库/知识订阅/灵感顿悟
_archive/    — 归档
```

**CLAUDE.md 入口协议**: STATUS → STATE → MEMORY → signals → TIMELINE → _inbox

### 1.4 L4 Gateway — CLAUDE_COWORK_GLOBAL.md

19 域全览 + 域类型映射 + Agent 工作流规范。核心原则：
1. SSOT — 每个事实只有一个权威位置
2. Agent 必须走 L3 — 不绕过 cockpit MCP
3. 约束优先 — 操作前 cards_check
4. CARDS 优先 — 任务/想法/债务走 CARDS MCP

---

## 二、L3 · 入口层 — 内部架构

### 2.1 命令路由树

```
cockpit CLI (24 顶层命令 + 27 research 子操作 = 51 入口)
│
├── research (27子操作) ← 核心管线
│   ├── search/compare/merge/digest       ← 分析
│   ├── audit/quarantine/restore          ← 治理
│   ├── list/open/dossier/timeline        ← 浏览
│   ├── tag/rename/publish/export         ← 操作
│   ├── archive/unarchive/backup/restore  ← 归档
│   ├── ask (追问) / agent (标记)          ← 交互
│   ├── health/heatmap/follow_up          ← 健康
│   └── batch                             ← 批量 (新增)
│
├── status/daily/demo          ← 工作台
├── health --full              ← 全栈体检 (新增)
├── context/cards/vault/domains/skill ← L4 桥接
├── quickstart/init            ← onboarding
├── contracts/data/profile     ← 治理
├── mcp/dashboard/events       ← 服务
├── governance/workflow/code   ← 工具
└── help/version               ← 元信息
```

### 2.2 存储层 — IDataAccess Protocol

```
IDataAccess (21个方法 Protocol)
    ↓ 实现
SQLiteDataAccess (WAL模式, busy_timeout=5000ms)
    ↓
~/.workspace/data.db (5张表)
    ├── research (核心)
    ├── research_relations (关系)
    ├── published_reports (产物)
    ├── research_events (时间线)
    └── research_fts (FTS5全文搜索)
```

**半衰期算法**: `decay = 2^(-days/14) × (1 + 追问加成0.2) × (1 + 发布加成0.1×n)`

### 2.3 研究管线 — 17 阶段完整生命周期

```
创建 → 浏览 → 追问 → 标签 → 重命名 → 发布 → 导出
  → 关系(比较/合并/digest) → 档案(dossier/时间线)
  → 治理(审计/隔离/恢复) → 归档 → 健康(半衰期/热力图/追问工作台)
  → 备份恢复 → Agent标记 → 批量
```

### 2.4 MCP 工具矩阵 (20 tools)

| 类别 | 工具 | 数量 |
|------|------|------|
| 研究生命周期 | research_list/search/create/open/ask/archive/restore/tag/rename/dossier/half_life/agent_list | 12 |
| 状态/简报 | status_summary/status_json/daily_summary | 3 |
| L4 桥接 | workspace_context/cards_status/cards_check/vault_search/domains_list | 5 |

### 2.5 commands/ 目录统计 (17 文件, 4156 行)

| 模块 | 行数 | 角色 |
|------|------|------|
| research.py | 1271 (30.6%) | 核心研究管线 |
| status.py | 719 (17.3%) | 工作台/健康 |
| base.py | 457 (11.0%) | 共享工具 |
| contracts.py | 366 (8.8%) | 契约管理 |
| quickstart.py | 307 (7.4%) | onboarding |
| l4bridge.py | 207 (5.0%) | L4 桥接 |
| 其他 11 文件 | 829 (19.9%) | 治理/工具/MCP |

---

## 三、L4 ↔ L3 ↔ L2 数据流

```
┌─────────────────────────────────────────────────────────┐
│                     L4 · 自我层 (19域)                    │
│  CARDS(SQLite) + Vault(Obsidian) + Personal + ...        │
│  只读消费 · 不运行代码                                     │
└────────────┬──────────────┬──────────────┬──────────────┘
             │ MCP 读取      │ prompt 注入   │ 写入
             ▼               ▼               ▼
    ┌────────────────┐ ┌──────────┐ ┌──────────────┐
    │  L3 · cockpit   │ │L2·metaos│ │ L2 · minerva  │
    │                │ │         │ │              │
    │ workspace_     │ │cards_   │ │ VaultSink    │
    │ context()      │ │context()│ │ Stage        │
    │ cards_status() │ │→ Agent  │ │              │
    │ vault_search() │ │ prompt  │ │ 研究→归档     │
    │ domains_list() │ │         │ │              │
    │                │ │         │ │              │
    │ 5 MCP tools    │ │ 1 函数   │ │ 1 Pipeline   │
    │ + 5 CLI cmds   │ │         │ │ Stage        │
    └────────────────┘ └──────────┘ └──────────────┘
             │               │               │
             └───────────────┼───────────────┘
                             │
                    ┌────────▼────────┐
                    │   L0 · ecos     │
                    │ 18 DOMAIN-*.yaml│
                    │ M1 域模型注册   │
                    └─────────────────┘
```

### 3.1 L3 → L4 读取接口 (5 MCP tools + 5 CLI commands)

| MCP Tool | CLI Command | 功能 |
|----------|------------|------|
| workspace_context() | cockpit context | Phase + CARDS + 约束 + 引导 |
| cards_status() | cockpit cards | 活跃卡片列表 (按优先级) |
| cards_check(card_id) | cockpit cards --check | 操作前合规检查 |
| vault_search(keyword, domain) | cockpit vault <kw> | 跨域知识检索 |
| domains_list() | cockpit domains | 列出所有 L4 域状态 |

### 3.2 L2 → L4 注入

**metaos** (cards_context.py): 读取 P0 CARDS → 注入 Agent planning prompt
**minerva** (vault_sink.py): 研究完成 → 自动写入 @学习进化/_storage/

---

## 四、架构评估

### L4 优势
- ✅ 19 域 KEMS 六面结构 — 数据组织规范统一
- ✅ SSOT 双写 — SQLite (真源) + Markdown (人读)
- ✅ CARDS 生命周期 — 5 种类型 × 多状态流转
- ✅ Gateway 入口协议 — CLAUDE.md 引导 Agent 行为

### L4 弱点
- ⚠️ 19 域中仅 7 个有 cockpit MCP 映射 (_L4_DOMAINS 字典不完整)
- ⚠️ CARDS 无版本历史 — SQLite 不跟踪变更
- ⚠️ 纯本地 — 无跨设备同步

### L3 优势
- ✅ 51 个功能入口 (24 命令 + 27 子操作) — 功能密度极高
- ✅ IDataAccess Protocol — 存储后端可替换
- ✅ 三级降级链 — minerva→ollama→缓存
- ✅ 17 阶段研究生命周期 — 全程可追溯

### L3 弱点
- ⚠️ 入口碎片化 — `workspace` vs `cockpit` 双名 + `l4cards` 第三入口
- ⚠️ 无配置中心 — 硬编码路径/超时分散在各文件
- ⚠️ Web Dashboard 未完成 — 仅有骨架
