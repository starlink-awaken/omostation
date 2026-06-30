# PANORAMA.md — eCOS 系统全景架构

> 本文是全景骨架与导航，不是运行时快照。
> 任何会漂移的测试数、路由数、健康分、Phase、端口状态，以各自 SSOT 与运行时探针为准。
> 配套: [I0-AGORA-CALLCHAIN.md](./I0-AGORA-CALLCHAIN.md)
> 项目级 `ARCHITECTURE.md` / `CALLCHAIN.md` / `BOUNDARY.md` 也只保留骨架与指针，不承担运行时快照职责。

## 全景 SSOT

| 主题 | 权威读源 |
|------|----------|
| Workspace 运行时状态 | `.omo/state/system.yaml` |
| Workspace 当前目标 | `.omo/goals/current.yaml` |
| `.omo` 三层治理契约 | `.omo/standards/omo-governance-surfaces.md` |
| `.omo` 治理面注册表 | `.omo/_truth/registry/omo-governance-surfaces.yaml` |
| `.omo` 持久化写入入口清单 | `.omo/_truth/registry/mutation-surfaces.yaml` |
| `.omo` internal/runtime 写路径清单 | `.omo/_truth/registry/internal-write-profiles.yaml` |
| `.omo` task policy 注册表 | `.omo/_truth/registry/task-policies.yaml` |
| `.omo` direct-io 基线 | `.omo/_truth/registry/direct-io-baseline.yaml` |
| X1-X4 治理规则 | `.omo/_truth/x1-governance-policies.yaml` ~ `x4-consistency-rules.yaml` |
| L0 强制约束 | `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` |
| BOS 路由实现 | `projects/agora/src/agora/mcp/resolver/services.py` |
| 项目边界与调用链 | 各项目 `ARCHITECTURE.md` / `CALLCHAIN.md` / `BOUNDARY.md` |

---

## 一、架构总览 (5+4+1+1)

```
┌────────────────────────────────────────────────────────────────────┐
│  L4 自我层 (Documents + l4-kernel)                                 │
│  ├── 个人知识与自我层状态                                           │
│  ├── l4-kernel — 自我层管理面                                       │
│  ├── 文档运行时与治理脚本                                            │
│  └── CARDS / dashboard / personal state                            │
├────────────────────────────────────────────────────────────────────┤
│  L3 入口层 (cockpit + mounted apps)                                │
│  ├── CLI / Web / mounted dashboard                                 │
│  ├── 人类唯一入口: cockpit                                          │
│  └── 其他入口通过 I0 收敛                                           │
├────────────────────────────────────────────────────────────────────┤
│  I0 织层 (agora)                                                   │
│  ├── MCP Mesh / BOS URI Router                                      │
│  ├── BOS URI — 5 域 (memory/governance/analysis/persona/capability) │
│  ├── Proxy / cache / circuit breaker / L0 audit                    │
│  └── 跨层统一路由                                                    │
├────────────────────────────────────────────────────────────────────┤
│  L2 引擎面                                                          │
│  ├── kairon / gbrain — 记忆与知识引擎                               │
│  ├── omo — 治理内核                                                 │
│  └── metaos — 编排与决策门控                                        │
├────────────────────────────────────────────────────────────────────┤
│  L1 运行时 (runtime)                                               │
│  ├── Matrix Scheduler — 服务注册表 + 健康监控                       │
│  ├── KEI — 沙箱执行 + Ephemeral Agents                             │
│  └── 跨仓: ecos-matrix-scheduler/runtime-cli 入口                   │
├────────────────────────────────────────────────────────────────────┤
│  L0 协议层 (ecos)                                                  │
│  ├── SSB 签名链 — 不可变日志 + 认知操作记录                          │
│  ├── MOF 元模型 / L0 约束 / 治理规则                                 │
│  └── BOS URI / protocol registry                                   │
├────────────────────────────────────────────────────────────────────┤
│  M0 横切框架 (model-driven)                                        │
│  ├── 生命周期阶段引擎                                                │
│  ├── M3→M2→M1 桥接与推导                                             │
│  └── 被 L0/I0/L3/L4 四层消费                                          │
├────────────────────────────────────────────────────────────────────┤
│  X1-X4 治理维                                                      │
│  ├── X1 审计 / 边界 / 写入 gate                                      │
│  ├── X2 保鲜 / 抗熵                                                  │
│  ├── X3 价值 / 成本归因                                              │
│  └── X4 一致性 / SSOT 收敛                                           │
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

### 2.1 项目分层

| 项目 | 层 | 角色 |
|:----:|:--:|------|
| l4-kernel | L4 | 自我层管理面 |
| cockpit | L3 | 人类 CLI / Web 统一入口 |
| agora | I0 | MCP Mesh 与 BOS 路由 |
| kairon | L2 | 知识与搜索引擎 |
| gbrain | L2 | TS 知识数据库 |
| omo | L2 | 治理内核 |
| metaos | L2 | 编排与门控 |
| runtime | L1 | 沙箱与调度 |
| ecos | L0 | 协议、MOF、约束 |
| model-driven | M0 | 生命周期横切框架 |
| aetherforge | X | 能力与算力横切框架 |
| c2g | X | 战略需求入口 |

### 2.2 L4 域注册表

| 类型 | 域数 | SSOT | 注册位置 |
|:----:|:----:|------|---------|
| document | 11 | `@驾驶舱/_control/DOMAIN-INDEX.md` | cockpit, vault, creative, personal, shared, family, work-weijian, work-guozhuan, opc, family-shared, obsidian-vault |
| config | 3 | 同上 | ai-config, agents-config, icloud-sharedconf |
| engine | 3 | 同上 | minerva, knowledge-engine, l4-kernel |
| tool | 2 | 同上 | bin, toolbox-tools |
| workspace | 2 | 同上 | sharedwork, ecos-workbench |
| storage | 1 | 同上 | shareddisk |
| model | 2 | 同上 | model-volume, sharedmodel |

### 2.3 BOS 路由域

| 域 | 职责 | 示例 |
|:--:|------|------|
| memory | 记忆与事实 | `bos://memory/...` |
| governance | 治理与律法 | `bos://governance/...` |
| analysis | 认知与推演 | `bos://analysis/...` |
| persona | 人格与心智 | `bos://persona/...` |
| capability | 能力与生态 | `bos://capability/...` |

---

## 三、核心流程

### 3.1 BOS URI 派发

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

### 3.2.1 `.omo` 持久化机制

```
script / wrapper / cron
  → projects/omo 内核函数 or omo CLI
    → truth registry / task policy / write profile 校验
    → 原子写 / 锁 / 审计追加
    → .omo/ state/control/truth/delivery 落盘

禁止路径:
  script 直接 open(..., "w") / write_text() / yaml dump 到 .omo/
```

- 当前治理基线要求 `.omo/_truth/registry/direct-io-baseline.yaml` 保持空基线 `entries: []`。
- `omo lint direct-omo-io` 先校验空基线，再调用 gatekeeper 扫描脚本直写。
- `omo lint mutation-surfaces` / `omo lint internal-write-profiles` 用来保证“允许写哪里、谁能写、怎么写”有机器可读注册表，而不是靠 reviewer 记忆。
- 因此，新机制不是“多写几份文档”，而是“registry + lint + kernel helper + CI”四件套一起落地。

### 3.3 L4 健康检查

```
路径 A: cockpit health --full
  → L4 Context (l4-kernel bridge)          → 域存在性
  → L4 域健康 (l4-kernel DomainHealth)     → 聚合 dashboard
  → L4 文档域 (@驾驶舱/_runtime/子进程)    → KEMS 健康
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
| **agora MCP** | SSE | `:7431` | 统一 MCP 入口 | API key | 🟢 已收敛 |
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

> 这一节只保留验证点类型，不记录会漂移的通过数/版本号。

| 集成点 | 验证方式 | 状态 |
|--------|---------|:----:|
| cockpit MCP `workspace_context` | `cockpit_mcp.py` workspace_context 工具 | ✅ |
| cockpit HTTP `/api/context` | `dashboard_server.py` → delegation | ✅ |
| cockpit MCP `cards_status`, `cards_check` | `cockpit_mcp.py` cards 工具 | ✅ |
| cockpit CLI `cards --check` | `cli.py` → `l4bridge.py` | ✅ |
| l4-kernel ↔ DOMAIN-INDEX ID | 域注册表对齐 | ✅ |
| l4-kernel ↔ DOMAIN-INDEX 路径 | `expanduser()` 一致 | ✅ |
| 治理脚本链路 | 共享治理脚本链路存在 | ✅ |
| `cockpit health --full` L4 | L4 文档域子进程 | ✅ |
| 架构版本 | 统一 5+4+1+1 口径 | ✅ |
| Phase 映射 | 双系统映射存在 | ✅ |
| @驾驶舱跟踪 | 受版本控制 | ✅ |
| Dashboard 刷新 | 独立状态面与刷新链路 | ✅ |
| 子模块指针 | ecos/l4-kernel 同步 | ✅ |

---

## 六、关键 SSOT

| 数据 | 唯一读源 | 回退机制 |
|------|---------|---------|
| L4 域注册表 | `@驾驶舱/_control/DOMAIN-INDEX.md` | l4-kernel registry |
| Workspace Phase | `.omo/state/system.yaml` | — |
| Documents Phase | `@驾驶舱/_control/DASHBOARD.md` | — |
| MOF M1 | `projects/ecos/src/ecos/ssot/mof/m1/` | — |
| BOS 路由 | `projects/agora/src/agora/mcp/resolver/services.py` | Agora resolver |
| 任务 | `.omo/tasks/active/` YAML | — |
| CARDS | `@驾驶舱/CARDS/` (文件) / `data/cards/cards.db` (SQLite) | 双系统 |
| 治理策略 | `.omo/_truth/x1-governance-policies.yaml` | X1-X4 链 |
| OMO 目标（运行时） | `.omo/goals/current.yaml` | `_truth/goals/` 只作事实面镜像/索引，不作为 broker 写入目标 |

---

## 七、Phase 映射

| 系统 | 范围 | Phase | 读源 |
|------|------|:-----:|------|
| Documents Phase | L4 自我层·个人知识管理 | 0→8.3 | `@驾驶舱/_control/DASHBOARD.md` |
| Workspace Phase | eCOS v6 工程 | 1→33+ | `.omo/state/system.yaml` |

---

## 八、债务与熵

| 指标 | 权威读源 |
|------|----------|
| health_score / debt_health / xplane_score | `.omo/state/system.yaml` 或治理报表 |
| 活跃债务 / 已归档 debt | `.omo/debt/` |
| backlog_pressure | 当前任务与治理报表 |

---

## 九、用户旅程韧性 (6 条核心链路)

详细白盒探针分析见 `docs/_archived/JOURNEY-PROBES.md` (归档历史参考)

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

- [I0-AGORA-CALLCHAIN.md](./I0-AGORA-CALLCHAIN.md) — I0 织层 BOS URI 9 步派发调用链
- 架构图和历史演进文档已归档至 `docs/_archived/`

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
| aetherforge-swarm-ext | X | **ARCHIVED** — 快照在 `/_archived/aetherforge-swarm-ext/`，扩展已并入 [aetherforge/packages/swarm/src/swarm_engine/ext](../projects/aetherforge/packages/swarm/src/swarm_engine/ext/) |
| agora-dashboard | L3 | **LEGACY SNAPSHOT** — 独立入口已收敛；仓库快照仍保留在 `projects/agora-dashboard/` 供历史追溯 |
| bus-foundation | X | [ARCHITECTURE.md](../projects/bus-foundation/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/bus-foundation/CALLCHAIN.md) · [BOUNDARY.md](../projects/bus-foundation/BOUNDARY.md) |
| c2g | X | [ARCHITECTURE.md](../projects/c2g/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/c2g/CALLCHAIN.md) · [BOUNDARY.md](../projects/c2g/BOUNDARY.md) |
| compute-mesh | L1 | **ARCHIVED** — 快照在 `/_archived/compute-mesh/`，能力已并入 [aetherforge/packages/mesh](../projects/aetherforge/packages/mesh/) |
| family-hub | X | [ARCHITECTURE.md](../projects/family-hub/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/family-hub/CALLCHAIN.md) · [BOUNDARY.md](../projects/family-hub/BOUNDARY.md) |
| hermes-console | L3 | **ARCHIVED** — 项目已移除（L3 入口能力已收敛到 cockpit/agora）|
| l4-kernel | L4 | [ARCHITECTURE.md](../projects/l4-kernel/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/l4-kernel/CALLCHAIN.md) · [BOUNDARY.md](../projects/l4-kernel/BOUNDARY.md) |
| llm-gateway | X | **ARCHIVED** — 快照在 `/_archived/llm-gateway/`，能力已并入 [aetherforge/packages/gateway](../projects/aetherforge/packages/gateway/) |
| model-driven | M0 | [ARCHITECTURE.md](../projects/model-driven/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/model-driven/CALLCHAIN.md) · [BOUNDARY.md](../projects/model-driven/BOUNDARY.md) |
| observability | X | [ARCHITECTURE.md](../projects/observability/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/observability/CALLCHAIN.md) · [BOUNDARY.md](../projects/observability/BOUNDARY.md) |
| omo-debt | L2 | [ARCHITECTURE.md](../projects/omo-debt/ARCHITECTURE.md) · [CALLCHAIN.md](../projects/omo-debt/CALLCHAIN.md) · [BOUNDARY.md](../projects/omo-debt/BOUNDARY.md) |
| spaces | L0/L1 | [ARCHITECTURE.md](../spaces/ARCHITECTURE.md) · [CALLCHAIN.md](../spaces/CALLCHAIN.md) · [BOUNDARY.md](../spaces/BOUNDARY.md) |
| swarm-engine | X | **ARCHIVED** — 快照在 `/_archived/swarm-engine/`，能力已并入 [aetherforge/packages/swarm](../projects/aetherforge/packages/swarm/) |

*最后更新: 2026-06-17 · 本文只保留全景骨架与指针，不再维护运行时快照*
