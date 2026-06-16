# PANORAMA.md — eCOS v5 系统全景架构

> 2026-06-10 | 8 层 5+4+1+1 · 10 项目 · 24 域 · 10k+ tests · 全栈 lint 0
> 配套: [JOURNEY-PROBES.md](./JOURNEY-PROBES.md) (6 条核心旅程白盒分析)

---

## 一、架构总览 (5+4+1+1)

```
┌────────────────────────────────────────────────────────────────────┐
│  L4 自我层 (Documents + l4-kernel)                                 │
│  ├── @驾驶舱 — 24 域 (7类型) · git:5d98dcc · DASHBOARD v6.4        │
│  ├── l4-kernel — 统一管理面 · 24 域注册表 · 43 MCP                  │
│  ├── _runtime/ — 6 治理脚本 (X1-X3 全维健康)                       │
│  └── CARDS — 61 活跃卡片 (文件系统 + l4-kernel CardsPlane)          │
├────────────────────────────────────────────────────────────────────┤
│  L3 入口层 (cockpit & agora-dashboard)                             │
│  ├── CLI (cockpit) — 25 子命令 (research/status/cards/health/...)   │
│  ├── MCP Server — 38 工具【已通过 agora :7431 代理 — stdio deprecated】│
│  ├── Web Dashboard (agora-dashboard) — Next.js 15+ 多模态观察视界  │
│  └── 测试: 564 collected / 544 passed                                │
├────────────────────────────────────────────────────────────────────┤
│  I0 织层 (agora)                                                   │
│  ├── MCP Mesh — 42 工具 · 40 BOS 路由 · 三层路由链                  │
│  ├── BOS URI — 5 域 (memory/governance/analysis/persona/capability) │
│  ├── Proxy Manager — 限流(20 QPS) / 熔断器 / 缓存 / L0 审计         │
│  ├── KNOWN_SERVICES — 21 代理启动服务                               │
│  └── 测试: 1371 passed, 0 lint                                      │
├────────────────────────────────────────────────────────────────────┤
│  L2 引擎面                                                          │
│  ├── kairon — 19+6 packages, ~4000 tests                           │
│  ├── gbrain — TS 知识库, 67 MCP, ~9700 tests                       │
│  ├── omo — 治理面, AppendOnlyLog, fcntl 跨进程锁, 100+ tests        │
│  └── metaos — 编排引擎, 11 MCP, 189 tests, 0 lint                  │
├────────────────────────────────────────────────────────────────────┤
│  L1 运行时 (runtime)                                               │
│  ├── Matrix Scheduler — 服务注册表 + 健康监控                       │
│  ├── KEI — 沙箱执行 + Ephemeral Agents                             │
│  ├── MCP — 30 工具, 171 tests                                      │
│  └── 跨仓: ecos-matrix-scheduler/runtime-cli 入口                   │
├────────────────────────────────────────────────────────────────────┤
│  L0 协议层 (ecos)                                                  │
│  ├── SSB 签名链 — 不可变日志 + 认知操作记录                          │
│  ├── MOF 元模型 — 984 M1 YAML 节点 + 24 M2 类型                     │
│  ├── BOS URI 路由 — 25 mof-* 工具链                                │
│  └── 测试: 195 passed, 0 lint                                       │
├────────────────────────────────────────────────────────────────────┤
│  M0 横切框架 (model-driven)                                        │
│  ├── 7 阶段引擎 (OKR→Spec→ADR→Dev→Deploy→Ops→BizOps)               │
│  ├── 12 工具链 (推导/触发/OKR/管道/自反验证)                        │
│  ├── 24 M2 类型, 190 tests, 0 lint                                  │
│  └── 被 L0/I0/L3/L4 四层消费, 零内部依赖                             │
├────────────────────────────────────────────────────────────────────┤
│  X1-X4 治理维                                                      │
│  ├── X1 审计 — facts.md 变更追踪                                    │
│  ├── X2 保鲜 — CLAUDE.md 版本/审查日期检查                           │
│  ├── X3 价值 — 22 域活跃度评分 (平均 32 分)                          │
│  └── X4 一致性 — 域注册表契约 (24域 100% ID 对齐)                    │
└────────────────────────────────────────────────────────────────────┘
```

### 架构命名空间 (BOS URI)

```
bos://memory/        ← kairon (kos/kronos/sophia) + gbrain      — 记忆与事实
bos://governance/    ← omo + metaos                              — 治理与律法
bos://analysis/      ← minerva + ontoderive + codeanalyze        — 认知与推演
bos://persona/       ← runtime + cockpit                         — 人格与心智
bos://capability/    ← forge + agora + family-hub                — 能力与生态
```

---

## 二、项目全景

### 2.1 项目健康度

| 项目 | 层 | 栈 | 测试 | Lint | 域管理 | MCP |
|:----:|:--:|:--:|:----:|:----:|:------:|:---:|
| agora-dashboard | L3 | Next.js/React | 待定 | 0 | - | - |
| l4-kernel | L4 | Python | 250+ | 0 | 24 域 | 43 |
| cockpit | L3 | Python | 542/562 | 0 | — | 37 |
| agora | I0 | Python | 1371 | 0 | 40 BOS | 42 |
| kairon | L2 | Python | ~4000 | 0 | — | stdio |
| gbrain | L2 | TS | ~9700 | — | — | 67 |
| omo | L2 | Python | 100+ | 0 | — | — |
| metaos | L2 | Python | 189 | 0 | — | 11 |
| runtime | L1 | Python | 171 | 0 | — | 30 |
| ecos | L0 | Python | 195 | 0 | — | 25 |
| model-driven | M0 | Python | 190 | 0 | — | 12 |

### 2.2 L4 域注册表 (24 域 · 7 类型)

| 类型 | 域数 | SSOT | 注册位置 |
|:----:|:----:|------|---------|
| document | 11 | `@驾驶舱/_control/DOMAIN-INDEX.md` | cockpit, vault, creative, personal, shared, family, work-weijian, work-guozhuan, opc, family-shared, obsidian-vault |
| config | 3 | 同上 | ai-config, agents-config, icloud-sharedconf |
| engine | 3 | 同上 | minerva, knowledge-engine, l4-kernel |
| tool | 2 | 同上 | bin, toolbox-tools |
| workspace | 2 | 同上 | sharedwork, ecos-workbench |
| storage | 1 | 同上 | shareddisk |
| model | 2 | 同上 | model-volume, sharedmodel |

### 2.3 BOS 路由表 (40 条 · 5 域)

| 域 | 路由数 | 示例 |
|:--:|:------:|------|
| memory | 5 | `bos://memory/kos/search`, `bos://memory/kos/embed` |
| governance | 8 | `bos://governance/omo/debt-registry`, `bos://governance/omo/health` |
| analysis | 12 | `bos://analysis/minerva/research`, `bos://analysis/ontoderive/derive` |
| persona | 7 | `bos://persona/runtime/matrix`, `bos://persona/runtime/chat` |
| capability | 8 | `bos://capability/forge/tools`, `bos://capability/forge/integrate` |

---

## 三、核心流程

### 3.1 BOS URI 派发 (9 步路由链)

```
LLM / Agent
  → MCP "resolve_bos_uri" (tools_bos.py:238-303)
    → 限流器检查 (20 QPS/域)
    → 熔断器检查
    → 缓存命中检查
    → BOSRouter Trie 前缀匹配 (bos_router.py:169)
    → POC_SERVICES 精确匹配 (bos_resolver.py:1431)
    → FeatureGate 域启用检查
    → 传输层派发:
        mcp_stdio → mcp_stdio_bridge → subprocess
        stdio     → ProcessPool → subprocess PIPE
        internal  → importlib 同进程
    → L0 审计钩子 (post_audit)
    → 缓存写入 + 熔断器记录 + 事件发布
```

**韧性**: timeout/eof/JSON 解析失败 → 自动重试 1 次 → 清晰错误提示

### 3.2 OMO 治理闭环

```
Agent 操作
  → Phase 检查 (omo state → system.yaml)
  → CARDS 检查 (cockpit cards --check → .omo/_truth/ 治理策略)
  → 约束检查 (X1-X4 规则)
  → 执行变更
  → Audit 日志 (AppendOnlyLog 5 consumer: audit/bos_metrics/sync/alert/event)
  → Task 同步 (CARDS state)
  → Debt 注册 (如异常/违规)
  → Signal 发射 (l4-kernel SignalBus)
```

### 3.3 L4 健康检查 (双路径)

```
路径 A: cockpit health --full
  → L4 Context (l4-kernel bridge)          → 24 域存在性
  → L4 域健康 (l4-kernel DomainHealth)     → 聚合 dashboard
  → L4 文档域 (@驾驶舱/_runtime/子进程)    → 22 域 KEMS 健康
  → L3 Cockpit Status (内部状态)
  → I0 Agora Stats (agora stats subprocess)
  → L1 Runtime Matrix (matrix_state.json)
  → L2 OMO Governance (system.yaml)

路径 B: python3 _runtime/ecos-health-check.py
  → parse_domain_index() → 22 域
  → kems_planes() + CLAUDE.md + STATE.md
  → 🟢/🟡/🔴 输出表
```

---

## 四、对外接入 (入口收敛后 3 入口)

| 入口 | 协议 | 端口 | 用途 | 鉴权 | 状态 |
|:----:|:----:|:----:|------|:----:|:----:|
| **cockpit CLI** | subprocess | — | 终端入口（人类唯一） | shell | 🟢 |
| **agora MCP** | SSE | **:7431** | 统一 MCP 入口（135 工具） | API key | 🟢 已收敛 |
| **cockpit HTTP** | FastAPI | :8090 | Web Dashboard / REST | API key | 🟢 |

**已下线入口**:
| 原入口 | 协议 | 下线原因 | 替代方式 |
|:------:|:----:|---------|---------|
| cockpit MCP | stdio | 入口收敛 Phase 1 | agora MCP `bos://cockpit/context` |
| l4-kernel MCP | stdio | 入口收敛 Phase 2 | agora MCP `bos://l4-kernel/domains` |
| runtime MCP | stdio | 入口收敛 Phase 2 | agora MCP `bos://runtime/health` |
| agora HTTP | — | 从未独立存在 | cockpit HTTP :8090 |

---

## 五、集成验证

| 集成点 | 详情 | 状态 |
|--------|------|:----:|
| cockpit MCP `workspace_context` | cocktail_mcp.py:473 | ✅ |
| cockpit HTTP `/api/context` | dashboard_server.py → delegation | ✅ |
| cockpit MCP `cards_status`, `cards_check` | cocktail_mcp.py:514,541 | ✅ |
| cockpit CLI `cards --check` | cli.py:432 → l4bridge.py | ✅ |
| l4-kernel ↔ DOMAIN-INDEX ID | 24 域 100% 对齐 | ✅ |
| l4-kernel ↔ DOMAIN-INDEX 路径 | `expanduser()` 一致 | ✅ |
| `_runtime/` 治理脚本 | 6 脚本 + 共享库, git commit | ✅ |
| `cockpit health --full` L4 | 新增 L4 文档域子进程 | ✅ |
| 架构版本 | 统一 5+4+1+1 | ✅ |
| Phase 映射 | §3 双系统标注 | ✅ |
| @驾驶舱 git 跟踪 | 368 文件初始 commit | ✅ |
| DASHBOARD 刷新 | v6.4, 2026-06-10 | ✅ |
| 子模块指针 | ecos/l4-kernel 同步 | ✅ |

---

## 六、关键 SSOT

| 数据 | 唯一读源 | 回退机制 |
|------|---------|---------|
| L4 域注册表 | `@驾驶舱/_control/DOMAIN-INDEX.md` | l4-kernel registry.py 24 域硬编码 |
| Workspace Phase | `.omo/state/system.yaml` | — |
| Documents Phase | `@驾驶舱/_control/DASHBOARD.md` v6.4 | — |
| MOF M1 | `projects/ecos/src/ecos/ssot/mof/m1/` (984 YAML) | — |
| BOS 路由 | `projects/agora/src/agora-events.json` | POC_SERVICES 40 条 |
| 任务 | `.omo/tasks/active/` YAML | — |
| CARDS | `@驾驶舱/CARDS/` (文件) / `data/cards/cards.db` (SQLite) | 双系统 |
| 治理策略 | `.omo/_truth/x1-governance-policies.yaml` | 4 条硬编码 |
| OMO 目标 | `.omo/_truth/goals/current.yaml` | — |

---

## 七、Phase 映射

| 系统 | 范围 | Phase | 读源 |
|------|------|:-----:|------|
| Documents Phase | L4 自我层·个人知识管理 | 0→8.3 | `@驾驶舱/_control/DASHBOARD.md` |
| Workspace Phase | eCOS v5 工程 | 1→33+ | `.omo/state/system.yaml` |

---

## 八、债务与熵

| 指标 | 数值 | 说明 |
|------|:----:|------|
| health_score | 98.0 | 接近完美 |
| debt_health | 98.0 | 0 活跃债务 |
| xplane_score | 85.0 | 跨层感知良好 |
| backlog_pressure | 0.0 | 无积压 |
| 活跃债务 | 0 | 3 个噪音已归档 |
| 已归档 debt | 95 | 2026-06-08 + 2026-06-10 |

---

## 九、用户旅程韧性 (6 条核心链路)

详细白盒探针分析 → [JOURNEY-PROBES.md](./JOURNEY-PROBES.md)

| 旅程 | 入口 | 链路深度 | 故障点 | 韧性评分 |
|:----:|:----:|:-------:|:------:|:-------:|
| A: 知识搜索 | `cockpit research search` | 5 跳 | 4 🟢 | 🟢 |
| B: 全栈健康 | `cockpit health --full` | 7 跳 | 5 🟢 | 🟢 |
| C: 约束检查 | `cockpit cards --check` | 3 跳 | 3 🟡 | 🟡 |
| D: BOS URI | `resolve_bos_uri` MCP | 9 跳 | 9 🟢 | 🟢 (重试+熔断+缓存) |
| E: 卡片状态 | `cards_status` MCP | 3 跳 | 4 🟢 | 🟢 |
| F: 域管理 | l4-kernel MCP | 3 跳 | 3 🟢 | 🟢 |

---

---

## 附录：架构可视化与演进

- [ARCHITECTURE-DIAGRAM.md](./ARCHITECTURE-DIAGRAM.md) — eCOS v6 5+4+1+1 Mermaid 全景图
- [I0-AGORA-CALLCHAIN.md](./I0-AGORA-CALLCHAIN.md) — I0 织层 BOS URI 9 步派发调用链
- [ARCHITECTURE-EVOLUTION.md](./ARCHITECTURE-EVOLUTION.md) — 2026-05 收敛提案 vs eCOS v6 当前状态

## 附录：项目级架构文档索引

每个子项目均包含 `ARCHITECTURE.md`（架构图）、`CALLCHAIN.md`（调用链）、`BOUNDARY.md`（系统边界）：

| 项目 | 层 | 文档入口 |
|:--|:--|:--|
| agora | I0 | [ARCHITECTURE.md](../projects/agora/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/agora/CALLCHAIN.md) · [BOUNDARY.md](../projects/agora/BOUNDARY.md) |
| cockpit | L3 | [ARCHITECTURE.md](../projects/cockpit/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/cockpit/CALLCHAIN.md) · [BOUNDARY.md](../projects/cockpit/BOUNDARY.md) |
| kairon | L2 | [ARCHITECTURE.md](../projects/kairon/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/kairon/CALLCHAIN.md) · [BOUNDARY.md](../projects/kairon/BOUNDARY.md) |
| gbrain | L2 | [ARCHITECTURE.md](../projects/gbrain/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/gbrain/CALLCHAIN.md) · [BOUNDARY.md](../projects/gbrain/BOUNDARY.md) |
| omo | L2 | [ARCHITECTURE.md](../projects/omo/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/omo/CALLCHAIN.md) · [BOUNDARY.md](../projects/omo/BOUNDARY.md) |
| metaos | L2 | [ARCHITECTURE.md](../projects/metaos/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/metaos/CALLCHAIN.md) · [BOUNDARY.md](../projects/metaos/BOUNDARY.md) |
| runtime | L1 | [ARCHITECTURE.md](../projects/runtime/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/runtime/CALLCHAIN.md) · [BOUNDARY.md](../projects/runtime/BOUNDARY.md) |
| ecos | L0 | [ARCHITECTURE.md](../projects/ecos/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/ecos/CALLCHAIN.md) · [BOUNDARY.md](../projects/ecos/BOUNDARY.md) |
| aetherforge | X | [ARCHITECTURE.md](../projects/aetherforge/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/aetherforge/CALLCHAIN.md) · [BOUNDARY.md](../projects/aetherforge/BOUNDARY.md) |
| aetherforge-swarm-ext | X | [ARCHITECTURE.md](../projects/aetherforge-swarm-ext/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/aetherforge-swarm-ext/CALLCHAIN.md) · [BOUNDARY.md](../projects/aetherforge-swarm-ext/BOUNDARY.md) |
| agora-dashboard | L3 | [ARCHITECTURE.md](../projects/agora-dashboard/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/agora-dashboard/CALLCHAIN.md) · [BOUNDARY.md](../projects/agora-dashboard/BOUNDARY.md) |
| bus-foundation | X | [ARCHITECTURE.md](../projects/bus-foundation/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/bus-foundation/CALLCHAIN.md) · [BOUNDARY.md](../projects/bus-foundation/BOUNDARY.md) |
| c2g | X | [ARCHITECTURE.md](../projects/c2g/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/c2g/CALLCHAIN.md) · [BOUNDARY.md](../projects/c2g/BOUNDARY.md) |
| compute-mesh | L1 | [ARCHITECTURE.md](../projects/compute-mesh/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/compute-mesh/CALLCHAIN.md) · [BOUNDARY.md](../projects/compute-mesh/BOUNDARY.md) |
| family-hub | X | [ARCHITECTURE.md](../projects/family-hub/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/family-hub/CALLCHAIN.md) · [BOUNDARY.md](../projects/family-hub/BOUNDARY.md) |
| hermes-console | L3 | [ARCHITECTURE.md](../projects/hermes-console/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/hermes-console/CALLCHAIN.md) · [BOUNDARY.md](../projects/hermes-console/BOUNDARY.md) |
| l4-kernel | L4 | [ARCHITECTURE.md](../projects/l4-kernel/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/l4-kernel/CALLCHAIN.md) · [BOUNDARY.md](../projects/l4-kernel/BOUNDARY.md) |
| llm-gateway | X | **ARCHIVED** — 快照在 `/_archived/llm-gateway/`，能力已并入 [aetherforge/packages/gateway](../projects/aetherforge/packages/gateway/) |
| model-driven | M0 | [ARCHITECTURE.md](../projects/model-driven/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/model-driven/CALLCHAIN.md) · [BOUNDARY.md](../projects/model-driven/BOUNDARY.md) |
| observability | X | [ARCHITECTURE.md](../projects/observability/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/observability/CALLCHAIN.md) · [BOUNDARY.md](../projects/observability/BOUNDARY.md) |
| omo-debt | L2 | [ARCHITECTURE.md](../projects/omo-debt/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/omo-debt/CALLCHAIN.md) · [BOUNDARY.md](../projects/omo-debt/BOUNDARY.md) |
| spaces | L0/L1 | [ARCHITECTURE.md](../spaces/ARCHITECTURE.md) · [CALLCHAIN.md](../spaces/CALLCHAIN.md) · [BOUNDARY.md](../spaces/BOUNDARY.md) |
| swarm-engine | X | [ARCHITECTURE.md](../projects/swarm-engine/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/swarm-engine/CALLCHAIN.md) · [BOUNDARY.md](../projects/swarm-engine/BOUNDARY.md) |

*最后更新: 2026-06-16 | 全栈 lint 清零 ✅ | 全栈测试 95%+ | 债务健康 98.0 | 入口收敛 7→3 ✅ | Agent 入口: agora MCP :7431*
