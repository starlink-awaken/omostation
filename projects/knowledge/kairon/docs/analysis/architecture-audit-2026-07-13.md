---
title: architecture-audit-2026-07-13
type: doc
---

# kairon 架构审计 — 2026-07-13

> 数据驱动审计（包 LOC + 跨包 import + agora BOS 路由 + MCP server 盘点），非印象。
> 触发：God Module 5/5 拆完 + G1-G5 场景接入后的架构层复盘。

---

## 1. 现状

### 1.1 包清单（16 包 ~155K LOC）

| 包 | LOC | 职责 | 类型 |
|----|-----|------|------|
| **eidos** | 36286 | 认知记忆枢纽 (memory/nks/continuity/CRDT/learning) | ⭐ 枢纽 |
| **ontoderive** | 28515 | 本体推导与推理 (BOS 入口型) | 加工 |
| **minerva** | 26454 | 深度研究引擎 (8 engines + 4 LLMs) | 加工 |
| **kos** | 25138 | 跨域语义搜索 / 知识图谱 | ⭐ 次枢纽 |
| forge | 9331 | Agent/工具集市 | 工具 |
| codeanalyze | 9254 | AST 代码分析 | 加工 |
| iris | 8674 | 发现与召回 | 加工 |
| kronos | 3264 | 知识摄取管线 | 摄取 |
| kairon-utils | 2812 | 共享工具 | 支撑 |
| kairon-observability | 2053 | 指标/告警/SLO | 支撑 |
| core-models | 2027 | 核心数据模型 | 支撑 |
| sophia | 1759 | KEMS 运行时 | 支撑 |
| kairon-plugin-sdk | 1230 | 插件 SDK | 支撑 |
| kairon-pipeline | 1029 | 流水线 | 支撑 |
| kairon-lib-events | 555 | 事件库 | 支撑 |
| health-profile | 549 | 健康画像 | 支撑 |

**4 个巨包**（eidos/ontoderive/minerva/kos）占 ~75% LOC。

### 1.2 跨包依赖图（实测 grep import）

```
eidos  ← codeanalyze, iris, kos(7文件), minerva   # 4 消费者, 反向零耦合 ✅
kos    ← eidos, kronos, minerva(4)                 # 3 消费者 (次枢纽)
ontoderive ← (kairon 内零直接 import, 但 agora BOS 活路由 + kos/eidos/sophia 跨引用)
minerva ← iris
forge   ← kos
kronos  ← iris
```

**eidos 是好枢纽**：4 包依赖，反向不依赖任何 kairon 包（纯下沉，架构基座稳）。
**ontoderive 非"死包"**：28K LOC，agora BOS 活路由 `bos://analysis/ontoderive/derive`，3 包跨 import —— **BOS 入口型**而非 import 枢纽。

### 1.3 入口面

| 入口 | 机制 | 状态 |
|------|------|------|
| **agora BOS** | URI 路由 → `python -m <pkg>.cli` | ✅ 统一外部入口 |
| per-package `__main__` | 16 个 CLI | 🟡 开发调试用 |
| **MCP server** | **9 个分散** | 🔴 碎片化（见 §2） |
| forge CLI | console script | 🟡 弃用（cockpit 替代）+ SRC 路径坏 |

### 1.4 数据流

```
agora BOS URI
  → kronos (摄取 文件/URL/HTML)
  → eidos (记忆枢纽: memory/nks/CRDT)
  → ontoderive (推导) / minerva (研究) / codeanalyze (AST) / iris (召回)
  → kos (跨域索引 + 语义搜索)
  → MCP / BOS 暴露给 AI agent
```

---

## 2. MCP server 盘点（最大架构债）

**9 个 MCP server，协议割裂，~94 工具**：

| 包 | 文件 | LOC | 工具数 | 协议 |
|----|------|-----|--------|------|
| **kos** | mcp/server.py | 1114 | ~28 | **stdio 手写 JSON-RPC** |
| minerva | mcp_server/server.py | 656 | ~8 | FastMCP |
| eidos | mcp_server.py | 473 | ~8 | **stdio 手写** |
| ontoderive | mcp_server.py | 286 | ~11 | FastMCP |
| kronos | mcp_server.py | 253 | ~16 | FastMCP |
| iris | iris/mcp_server.py | 266 | ~8 | FastMCP |
| sophia | server/mcp_server.py | 295 | ~8 | FastMCP |
| forge | mcp_server.py | 130 | ~7 | FastMCP |
| ontoderive/toolforge | mcp_server.py | **37** | **~0** | FastMCP（🟡 空壳） |

### 问题
1. **协议割裂**：kos + eidos 用 stdio 手写 JSON-RPC（老式），其他 7 个 FastMCP。两套协议并存，维护/路由成本翻倍。
2. **9 个分散**：AI agent 要猜走哪个 MCP，agora 要路由 9 个协议面。ontoderive 自己 2 个（其中 toolforge 37L 空壳）。
3. **工具重叠未查**：search/embed/viz/index 等能力可能多 MCP 都暴露（待工具名 diff）。
4. **空壳**：ontoderive/toolforge/mcp_server.py 37L ~0 工具，死壳。

---

## 3. 问题诊断（按严重度）

### 🔴 P0 — MCP 面 9 碎片 + 协议割裂
最大架构债。违背单一入口面，影响"系统对外暴露什么"的可理解性。kos（28 工具，最大）用 stdio 手写，其他 FastMCP —— 两套协议。

### 🟡 P1 — ARCHITECTURE.md SSOT 失准
"19+ packages"（实际 16）、eidos "39K"（实际 36K）、缺 MCP 盘点、ontoderive 定性偏（标枢纽实 BOS 型）。违反 doc-ssot-contract。

### 🟡 P2 — 4 巨包内聚
eidos/ontoderive/minerva/kos 各 25-36K。God Module warn 已清（5/5），但**包级巨物**仍在。ontoderive 1051 函数。

### 🟢 P3 — 入口策略不一致
forge CLI 弃用 + agora BOS 统一 + 9 MCP 散。CLI/BOS/MCP 三套入口策略未收敛。

---

## 4. 演进规划

### P0 — MCP 面统一（9 → hub）
**目标**：单一 MCP 面（或少数几个），协议统一 FastMCP。
- **协议统一**：kos/eidos 的 stdio 手写 → 迁移 FastMCP（已有 tools_schema 声明式，迁移成本低）
- **server 收敛**：ontoderive 2 个合并（删 toolforge 空壳）；评估 9 → 2-3 个（按域：memory/kos 主 + analysis/ontoderive+minerva + tool/forge）
- **工具去重**：diff 9 个 MCP 的工具名，合并重叠（search/embed/viz 等）
- **先调研**：9 MCP 工具名全量 diff（定重叠 + 合并策略）

### P1 — ARCHITECTURE.md SSOT 校准
更新：16 包、实测 LOC、跨包依赖图、MCP server 盘点表、入口面、ontoderive BOS 型定性。

### P2 — 4 巨包持续内聚
God Module warn 已清。下一步包级职责审视（ontoderive 1051 函数 / minerva 26K 可否拆子模块）。持续非紧急。

### P3 — 入口策略定调
**agora BOS = 统一外部入口**，MCP 收敛（P0），per-package CLI 保留开发调试，forge CLI 弃用确认。

---

## 5. 基座判断

**架构基座稳**：eidos 枢纽无反向耦合（好）、agora BOS 统一入口（好）。
**最大杠杆点**：MCP 面 9 碎片 + 协议割裂。统一后系统可理解性 + 维护性大幅提升。
**本审计基线**：2026-07-13，God Module 5/5 + G1-G5 接入后。
