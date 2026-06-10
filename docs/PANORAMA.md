# PANORAMA.md — eCOS v5 系统全景架构

> 2026-06-10 | 功能地图 · 系统架构 · 核心流程 · 模块依赖 · 用户旅程 · 对外接入
> 8 层 5+4+1+1 架构: L0-L4 + X1-X4 + I0 + M0

---

## 一、架构总览 (5+4+1+1)

```
┌─────────────────────────────────────────────────────────────────┐
│  L4 自我层 (Documents + l4-kernel)                              │
│  ├── @驾驶舱 — 24 域 (7类型: document/config/engine/...)        │
│  ├── l4-kernel — 统一管理面 (22域注册表 · 250 tests · 43 MCP)   │
│  └── CARDS — 个人事务跟踪 (文件系统 + SQLite 双系统)              │
├─────────────────────────────────────────────────────────────────┤
│  L3 入口层 (cockpit)                                            │
│  ├── CLI — 25 子命令 (research/status/cards/health/...)          │
│  ├── MCP Server — 37 工具 (主 + Agent Runtime + L0 + 遗留)       │
│  └── Web Dashboard — 16 REST API (:8090)                       │
├─────────────────────────────────────────────────────────────────┤
│  I0 织层 (agora)                                                │
│  ├── MCP Mesh — 42 工具 · 40 BOS 路由 · 三层路由链               │
│  ├── BOS URI 体系 — 5 域 (memory/governance/analysis/persona/capability) │
│  └── Proxy Manager — 限流/熔断/缓存/L0 审计钩子                   │
├─────────────────────────────────────────────────────────────────┤
│  L2 引擎面                                                       │
│  ├── kairon — 19+6 packages (kos/minerva/sophia/ontoderive/...) │
│  ├── gbrain — TS 知识数据库 (67 MCP tools, ~9700 tests)          │
│  ├── omo — 治理面 (AppendOnlyLog·fcntl跨进程锁·100+ tests)       │
│  └── metaos — 编排引擎 (11 MCP tools, 189 tests, 0 lint)        │
├─────────────────────────────────────────────────────────────────┤
│  L1 运行时 (runtime)                                            │
│  ├── Matrix Scheduler — 服务注册表 + 健康监控                     │
│  ├── KEI — 沙箱执行 + Ephemeral Agents                          │
│  └── MCP — 30 工具 (171 tests)                                  │
├─────────────────────────────────────────────────────────────────┤
│  L0 协议层 (ecos)                                               │
│  ├── SSB 签名链 — 不可变日志 + 认知操作记录                        │
│  ├── MOF 元模型 — 984 M1 YAML 节点 + 24 M2 类型                   │
│  └── BOS URI 路由 — 25 mof-* 工具链 (195 tests)                  │
├─────────────────────────────────────────────────────────────────┤
│  M0 横切框架 (model-driven)                                     │
│  ├── 全生命周期引擎 — 7 阶段 (OKR→Spec→ADR→Dev→Deploy→Ops→BizOps) │
│  ├── 12 工具链 — 推导/触发/OKR/管道/自反验证                       │
│  └── 被 L0/I0/L3/L4 四层消费 (190 tests, 零内部依赖)               │
├─────────────────────────────────────────────────────────────────┤
│  X1-X4 治理维                                                   │
│  ├── X1 审计 — 变更追踪 (facts.md/vault)                         │
│  ├── X2 保鲜 — CLAUDE.md 保鲜状态                                 │
│  ├── X3 价值 — 域活跃度评估                                       │
│  └── X4 一致性 — 域注册表契约 (eCOS ecos MOF)                     │
└─────────────────────────────────────────────────────────────────┘
```

### 架构命名空间

```
bos://memory/        ← kairon (kos/kronos/sophia) + gbrain      — 记忆与事实
bos://governance/    ← omo + metaos                              — 治理与律法
bos://analysis/      ← minerva + ontoderive + codeanalyze        — 认知与推演
bos://persona/       ← runtime + cockpit                         — 人格与心智
bos://capability/    ← forge + agora + family-hub                — 能力与生态
```

---

## 二、项目全景

### 2.1 项目健康度 (全栈 lint 清零 ✅)

| 项目 | 层 | 栈 | 测试 | Lint | 定位 |
|------|:--:|:--:|:----:|:----:|------|
| l4-kernel | L4 | Python | 250+ | 0 | 自我层统一管理面 · 22 域注册表 · 43 MCP |
| cockpit | L3 | Python | 567 | 0 | 统一入口 · 25 CLI · 37 MCP · 16 REST |
| agora | I0 | Python | 1371 | 0 | MCP Mesh · 42 工具 · 40 BOS 路由 |
| kairon | L2 | Python | ~4000 | 0 | 知识引擎 · 19+6 packages |
| gbrain | L2 | TS | ~9700 | — | 知识数据库 · 67 MCP |
| omo | L2 | Python | 100+ | 0 | 治理面 · AppendOnlyLog · fcntl |
| metaos | L2 | Python | 189 | 0 | 编排引擎 · 11 MCP |
| runtime | L1 | Python | 171 | 0 | 运行时 · Matrix + KEI |
| ecos | L0 | Python | 195 | 0 | SSB 协议 · MOF 元模型 |
| model-driven | M0 | Python | 190 | 0 | 全生命周期 · 12 工具链 |

### 2.2 L4 自我层域注册表 (24 域)

| 类型 | 域数 | 域 ID |
|:----:|:----:|-------|
| document | 11 | cockpit, vault, creative, personal, shared, family, work-weijian, work-guozhuan, opc, family-shared, obsidian-vault |
| config | 3 | ai-config, agents-config, icloud-sharedconf |
| engine | 3 | minerva, knowledge-engine, l4-kernel |
| tool | 2 | bin, toolbox-tools |
| workspace | 2 | sharedwork, ecos-workbench |
| storage | 1 | shareddisk |
| model | 2 | model-volume, sharedmodel |

---

## 三、核心流程

### 3.1 BOS URI 派发

```
User/Agent → cockpit (L3)
  → bos://memory/kos/search {query}
  → agora (I0) — BOSRouter Trie → POC_SERVICES → ProxyManager
  → stdio subprocess → kairon_kos (L2)
  → gbrain (L2) — 跨域知识查询
  → JSON 响应返回
```

**三层路由链**: `BOSRouter(前缀匹配) → POC_SERVICES(40条) → ProxyManager(限流/熔断/缓存)`

**跨层路由:**
- L4 @驾驶舱 → cockpit MCP (cards_status/cards_check)
- L4 l4-kernel → 43 MCP 工具
- L3 cockpit → I0 agora via bos:// URI
- I0 agora → L2 kairon/kos via stdio JSON-RPC
- I0 agora → L1 runtime via agent_runtime
- M0 model-driven → 被任意层消费

### 3.2 OMO 治理闭环

```
Agent 操作 → Phase 检查 (omo state)
           → CARDS 检查 (cockpit cards --check)
           → 约束检查 (X1-X4 规则)
           → 执行 → Audit 日志 (AppendOnlyLog 5 consumer)
           → Task 同步 (CARDS state)
           → Debt 注册 (如发现异常/违规)
           → Signal 发射 (SignalBus)
```

### 3.3 L4 健康检查

```
python3 @驾驶舱/_runtime/ecos-health-check.py
  → 解析 DOMAIN-INDEX (22 域)
  → 逐域检查: KEMS 平面 + CLAUDE.md + STATE.md
  → 输出: 🟢/🟡/🔴 状态表

cockpit health --full
  → L4 Context (l4-kernel bridge)
  → L4 文档域 (@驾驶舱/_runtime)
  → L3 Cockpit Status
  → I0 Agora Stats
  → L2 OMO Governance
  → L1 Runtime Matrix
```

---

## 四、对外接入

| 入口 | 协议 | 端口 | 用途 |
|:----:|:----:|:----:|------|
| cockpit CLI | subprocess | — | 终端入口 |
| cockpit MCP | stdio | — | Agent 调用 |
| cockpit HTTP | HTTP | :8090 | Web Dashboard |
| agora MCP | SSE | :7431 | LLM tool call |
| agora HTTP | HTTP | :7422 | 自动化脚本 |
| runtime MCP | stdio | — | Ephemeral Agents |
| l4-kernel MCP | stdio | — | L4 管理 |

---

## 五、关键 SSOT

| 数据 | 唯一读源 |
|------|---------|
| L4 域注册表 | `@驾驶舱/_control/DOMAIN-INDEX.md` (回退: l4-kernel registry.py) |
| Workspace Phase | `.omo/state/system.yaml` |
| Documents Phase | `@驾驶舱/_control/DASHBOARD.md` |
| MOF M1 | `projects/ecos/src/ecos/ssot/mof/m1/` (984 YAML) |
| BOS 路由表 | `projects/agora/src/agora-events.json` |
| 任务状态 | `.omo/tasks/active/` (YAML) |
| CARDS | `@驾驶舱/CARDS/` (文件) + `data/cards/cards.db` (SQLite) |
| 标准 | `.omo/standards/` |
| 目标 | `.omo/goals/current.yaml` |
| 治理审计 | `.omo/state/system.yaml` |

---

## 六、Phase 映射

> 当前存在两套独立 Phase 编号系统，不可交叉引用。

| 系统 | 范围 | Phase | 读源 |
|------|------|:-----:|------|
| Documents Phase | L4 自我层·个人知识管理 | 0→8.3 | `@驾驶舱/_control/DASHBOARD.md` |
| Workspace Phase | eCOS v5 工程 | 1→33+ | `.omo/state/system.yaml` |

---

## 七、集成验证 (Documents ↔ Workspace)

| 集成点 | 状态 |
|--------|:----:|
| cockpit MCP `workspace_context` | ✅ 真实存在 (cockpit_mcp.py) |
| cockpit HTTP `/api/context` | ✅ 真实存在 (dashboard_server.py) |
| cockpit MCP `cards_status/cards_check` | ✅ 真实存在 (cockpit_mcp.py) |
| cockpit CLI `cards --check` | ✅ 真实存在 (cli.py) |
| l4-kernel 域注册表 ↔ DOMAIN-INDEX | ✅ 24 域 100% ID 对齐 |
| l4-kernel registry ↔ DOMAIN-INDEX 路径 | ✅ 路径展开一致 |
| `_runtime/` 治理脚本 | ✅ 5 脚本 + 共享库 |
| `cockpit health --full` L4 集成 | ✅ 新增 L4 文档域检查 |
| 架构版本一致性 | ✅ 统一 5+4+1+1 |
| Phase 双系统标注 | ✅ §3 Phase 映射 |

---

*最后更新: 2026-06-10 | 全栈 lint: 0 errors | 全栈测试通过率: 95%+*
