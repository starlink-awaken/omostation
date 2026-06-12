# OPC 系统与生命周期分析报告

> 生成日期: 2026-06-12
> 分析范围: 项目整体架构 · 任务 · 目标 · 阶段 · 债务 · 需求 · 规划 · 里程碑 · 实施 · 治理
> 视角: OPC 路线图主线（与 `GOVERNANCE-ANALYSIS-REPORT.md` 的治理视角互补）
> 基线: P2 closeout 2026-06-11 · P3 D1+D2 passed 2026-06-12

---

## 0. 阅读指引

本报告回答 10 个问题：
1. 项目整体架构是什么样的？目标架构与现状差距在哪？
2. **任务**如何注册、流转、收口？
3. **目标**如何分解为 Wave → Phase → Milestone？
4. **阶段**（Phase）之间如何衔接？OPC 8 阶段与历史 Phase 编号什么关系？
5. **债务（跌打）**如何定义、跟踪、SLA、关账？
6. **需求**如何从用户旅程/治理探针转化为可执行任务？
7. **规划**产物（Roadmap/Playbook/阶段文档）有何约束？
8. **里程碑**当前在哪？下一站在哪？
9. **实施**机制：合同派发、试运行、收口、再审的循环？
10. **治理**四平面、信号总线、健康度趋势如何把系统粘合成一台机器？

> **SSOT 引用规范**：本报告是**索引与导读**，不复制原始数据。所有事实证据通过 `path:line` 反向链接至 `.omo/`、`docs/`、`projects/*` 下的 SSOT 文件。

---

## 1. 项目整体架构

### 1.1 现状架构：5+4+1+1 分层（eCOS v5）

```
┌─────────────────────────────────────────────────────────────┐
│ L4 自我层   │ l4-kernel · model-driven · 21域·KEMS·CARDS     │
├─────────────────────────────────────────────────────────────┤
│ L3 入口层   │ cockpit (CLI + Web) + hermes-console           │
├─────────────────────────────────────────────────────────────┤
│ I0 织层     │ agora (MCP Hub · 服务发现/路由/代理)           │
├─────────────────────────────────────────────────────────────┤
│ L2 引擎面   │ kairon · gbrain · omo · metaos · omo-debt     │
│             │ model-driven                                  │
├─────────────────────────────────────────────────────────────┤
│ L1 运行时   │ runtime · swarm-engine · aetherforge          │
│             │ llm-gateway · compute-mesh                     │
├─────────────────────────────────────────────────────────────┤
│ L0 协议     │ ecos (SSB 协议 · 签名链 · 涌现计算)            │
└─────────────────────────────────────────────────────────────┘
```

来源: `AGENTS.md:13-26` · `docs/PANORAMA.md:33-90`

### 1.2 OPC 视角下的 7 大能力域（OPC-ROADMAP §2）

| 能力域 | 主要项目 | OPC 角色 |
|--------|----------|----------|
| 自我层 | `l4-kernel` | 域注册表 · 自我状态 · KEMS 健康度 · 个人控制面 |
| 人类入口 | `cockpit`, `hermes-console` | CLI/Web 驾驶舱 · 状态 · 卡片 · 用户操作 |
| 代理入口与织层 | `agora` | MCP 收敛 · BOS URI 路由 · 代理 · 限流 · 熔断 · 审计 |
| 知识与记忆 | `kairon`, `gbrain` | KOS · 摄取 · 图谱/结构化记忆 · 研究与回溯 |
| 治理 | `omo`, `omo-debt`, `metaos`, `model-driven` | 目标 · 任务 · 债务 · 审计 · 生命周期模型 · 门禁 · 免疫 |
| 运行时与协议 | `runtime`, `ecos` | 沙箱 · 调度 · 矩阵 · SSB 协议日志 · L0 锚定 |
| 蜂群与能力 | `swarm-engine`, `aetherforge` | 任务市场 · DAG · 工人生命周期 · 规划/感知扩展 |
| 模型与算力 | `llm-gateway`, `compute-mesh` | 模型抽象 · 模型调度 · 算力发现 · 工人资源 |
| 产品场景 | `family-hub`, cockpit/Web | 家庭健康 · 公务辅助 · 技术雷达用户旅程 |

来源: `docs/OPC-ROADMAP.md:14-28`

### 1.3 目标架构（5 大产品能力）

1. **One way in** — 人类 → `cockpit`；代理 → `agora MCP :7431`；Web/API → `cockpit HTTP :8090`
2. **One memory spine** — 摄取 · 搜索 · 回溯 · 来源归属 · 归档共享规范源
3. **One swarm execution spine** — OMO Task → 蜂群 DAG → 工人执行 → 运行时隔离 → 结果回流记忆
4. **One model/compute plane** — `llm-gateway` + `compute-mesh` 是唯一模型与算力抽象
5. **One evolution loop** — 雷达发现升级 → OMO 规划 → 蜂群执行 → 审计验证

来源: `docs/OPC-ROADMAP.md:31-37`

### 1.4 现状 ↔ 目标差距

| 能力域 | 目标 | 现状（2026-06-12） | 差距 |
|--------|------|-------------------|------|
| One way in | 3 入口收敛 | 入口 1+1.5（3 入口已上线，仍需硬化验证） | 行程探针已重做；标记为"已上线未充分硬化" |
| One memory spine | 跨域规范源 | P2 Gate C 已 passed：多区可见性 + trace full_text 真实化 | ✅ P2 closeout 2026-06-11 |
| One swarm execution | OMO Task → DAG | P3 D1+D2 passed：任务对象运行时绑定 + 派发 | 🟡 D3-D5 未启动 |
| One model/compute plane | llm-gateway + compute-mesh 唯一 | 算力调度统一（Wave 2）已 done，但 P4 路线图刚注册 | 🟠 P4 计划阶段 |
| One evolution loop | 雷达 → OMO → 蜂群 → 审计 | P5/P6 计划已注册 | 🟠 计划阶段 |

---

## 2. 任务系统

### 2.1 任务生命周期

```
[Planned] → [Active] → [In Progress] → [Review] → [Done]
                                  ↓
                              [Deferred / Cancelled]
```

- **SSOT**: `.omo/tasks/planned/`、`.omo/tasks/active/`、`.omo/tasks/in_progress/`、`.omo/tasks/review/`、`.omo/tasks/done/`
- **YAML 契约**: 每个 task 至少包含 `id`, `desc`, `phase`, `priority`, `acceptance`, `evidence`, `status`, `created_at`, `owner`
- **状态约束**:
  - 完成任务必须更新 `status` 并落 `closed_at`
  - OPC Gate 任务额外需要 `gate_status` 和 `sub_gates` 结构
  - P2 已固化："单子门单次出现 + 无 not_started 泄漏 + 无 XML 脏标记"（P2-GATE-C.check.py 10/10 自检）

来源: `.omo/tasks/done/OPC-P2-GATE-C.yaml` · `.omo/tasks/done/OPC-P2-GATE-C.check.py`

### 2.2 任务分类

| 类别 | 前缀 | 流向 | 例 |
|------|------|------|-----|
| 治理审计 | `C1-C6` / `HIGH-` / `MEDIUM-` | done/ | `C1-fix-immune-nameerror.yaml` |
| 债务关账 | `D2_*` / `SB_*` | done/ + debt_weight_items | `D2-CI-E2E-TEST-ENV.yaml` |
| OPC 阶段 | `OPC-P{0-7}-{GATE}-{SUB}` | planned/active/done/ | `OPC-P2-GATE-C.yaml` |
| 阶段实施计划 | `P{30-60}-W{0-5}-{ACTION}` | planned/ | `P33-W0-FOLD` (44 planned) |
| 试点/验证 | `PILOT-*` | done/ | `PILOT-external-worker-dispatch-validation.yaml` |
| 导入任务 | `IMPORTED-{hash}` | planned/ | 12 个导入 |

来源: `ls .omo/tasks/done/ | grep -E "OPC-"` · `system.yaml:181-238`

### 2.3 任务关账的硬证据规则

- **OPC 阶段任务**: 必须有"证据链"（commit SHA、test 输出、self-check 通过记录）
- **YAML hygiene**: 单 status、单 closed_at、无重复子门、无 XML 脏标记（强制通过 P2-GATE-C.check.py）
- **证据红线**（OPC-MASTER-EXECUTION-PLAYBOOK §3）:
  - 禁止"假设通过" / "应该 OK" / "看了代码是对的"
  - 必须有可重放的命令 + 输出文件路径
  - 跨子门时禁止提前"开下一门"
- **来源**: `docs/OPC-MASTER-EXECUTION-PLAYBOOK.md`（664 行执行合同）

---

## 3. 目标系统

### 3.1 当前 Wave / Phase / Goal 树

```
theme: OMO 蜂群网络纪元 — 全量审计与接口修复
  phase: 28
  current_wave: W3
  entry_gate: phase26_completed
  health_targets: {mcp_isolation_score:100, overall:99, audit_complete:2026-06-06}
  objectives:
    W1: Agora MCP Safe Mesh (I0 隔离固化)        ← done
    W2: LLM Gateway (算力调度大一统)              ← done
    W3: gbrain Shared Context (L4 图谱记忆共享)   ← active
    W4: OMO MCP Server (硬件级剥夺与防越权)       ← done
```

来源: `.omo/goals/current.yaml:1-98`

### 3.2 已完成 P30-P31 重构（10 任务全部 100%）

- **M1 低风险搬家** (P30.1-P30.3): metaos / ecos / wksp → cockpit
- **M2 中风险拆分** (P30.4-P30.5): cron-service / agent-runtime
- **M3 高风险核心** (P30.6): agora 从 kairon 独立（38K → 35K）
- **M4 收尾** (P30.7): kairon-governance → omo 合并
- **I0 精简** (P31.1-P31.2): web/dashboard → cockpit；a2a → metaos
- **M3 核心重做** (P31.3): agora 独立为 projects/agora

来源: `.omo/goals/current.yaml:28-77`

### 3.3 OPC 5 大产品能力 ↔ 当前 Wave 对应

| 能力 | 当前 Wave | 完成度 |
|------|-----------|--------|
| One way in | W1 (I0 隔离) | done ✅ |
| One model/compute plane | W2 (LLM Gateway) | done ✅ |
| One memory spine | W3 (gbrain 共享) | active 🟡 |
| One swarm execution | (P3-P7 路线图) | D1+D2 passed 🟢 |
| One evolution loop | (P5-P6 计划) | 计划阶段 🟠 |

---

## 4. 阶段（Phase）系统

### 4.1 历史 Phase 编号与 OPC 阶段的关系

```
历史 Phase 1-46                  OPC 8 阶段路线图
─────────────────                ──────────────────
Phase 0    (产品雏形)             P0   Baseline
Phase 1-8  (Phase 0 收尾)         P1   Entry Convergence
Phase 9-15 (治理循环)             P1.5 Governance
Phase 16-20 (产品追踪)            P2   Memory Spine       ← 当前完成
Phase 21-28 (蜂群网络)            P3   Swarm Execution    ← 当前进行
Phase 29-35 (架构审计)            P4   Model/Compute      ← 已注册计划
Phase 36-46 (数据/治理)           P5   Scenarios
                                 P6   Evolution Loop
                                 P7   Release Train
```

来源: `docs/OPC-ROADMAP.md:39-226` · `.omo/state/system.yaml:35-65`

### 4.2 当前已确认状态（截至 2026-06-12）

| Phase | Status | Completed At |
|-------|--------|--------------|
| phase2 (核心) | completed | 2026-05-30 |
| phase3 (Foundation/Cap/Accept) | completed | 2026-05-30 |
| phase4 (Worker Collab) | wave2_completed | — |
| phase5-9 | completed | 2026-05-31 |
| phase10 | completed | 2026-05-31 |
| phase11-15 | completed | 2026-06-01 |
| phase17-25 | completed | 2026-06-03~04 |
| phase26 (Entry Gate) | phase24_completed | — |
| phase27-28 | active | — |
| phase29-30 | completed | 2026-06-05~06 |
| phase32, 35, 36, 39, 41 | completed | 2026-06-07~11 |
| phase45, 46 | active | — |

来源: `.omo/state/system.yaml:35-65`

### 4.3 阶段切换的硬约束

- **不跨阶段不跨门**: OPC 阶段内子门（Gate）有严格顺序，例如 Gate D (P3) 必须 D1 → D2 → D3 → D4 → D5
- **不跳门**: "no later gate without prior close"（OPC-MASTER-EXECUTION-PLAYBOOK §2）
- **回退协议**: 任何阶段红黄灯信号必须立即注册 debt 并回退到上一已通过门

---

## 5. 债务（跌打）系统

### 5.1 债务四层架构

```
┌──────────────────────────────────────────────────┐
│  预防层 │ pre-commit hook · 原子写入 · 测试覆盖   │
├──────────────────────────────────────────────────┤
│  检测层 │ debt-audit.sh · debt-leaderboard       │
│         │ CI 集成 · YAML hygiene 检查            │
├──────────────────────────────────────────────────┤
│  修复层 │ omo-debt register · 治理流程 · SLA     │
├──────────────────────────────────────────────────┤
│  监控层 │ 健康度趋势 · 治理仪表板 · BOS URI     │
└──────────────────────────────────────────────────┘
```

来源: `docs/GOVERNANCE-ANALYSIS-REPORT.md:63-122`（与本报告互补）

### 5.2 当前债务健康度（2026-06-11 16:30 审计）

| 指标 | 值 |
|------|-----|
| debt_health | 100.0 |
| classification_entropy | 0.0 |
| state_entropy | 0.0 |
| pointer_entropy | 0.0 |
| time_entropy | 0.0 |
| backlog_pressure | 0.0 |
| coupling_load | 0.0 |
| resolved_count | 9 |
| unresolved_count | 0 |
| watchlist_count | 0 |
| gate_count | 0 |
| health_score | 82.0（raw 100.0） |

来源: `.omo/state/system.yaml:104-178`

### 5.3 已关账债务（9/9 = 100%）

| ID | 权重 | 描述 | 验证 |
|----|------|------|------|
| D2_CI_E2E | 0.15 | CI E2E 容器化 | docker-compose.yml + Postgres+gbrain+kairon-test |
| D3_EU_PRICING | 0.03 | eu-pricing 独立测试 | 包已删除（Phase 30 清理，5972899） |
| SB_DECOMPOSITION | 0.20 | SharedBrain 拆解 | 已全部迁移至 kairon |
| SB_UNTESTED_PKGS | 0.15 | 无测试包补齐 | core-models 6 个测试文件 |
| SB_ORPHANED_TASKS | 0.10 | 结构化 registry | tasks/registry/INDEX.md 47 planned + 43 done |
| SB_ROOT_CLEANUP | 0.05 | 根目录空壳清理 | SharedBrain/ 仅含 data/db + README |
| SB_BRIDGE_FIX | 0.10 | sharedbrain-bridge 死代码 | 已整合至 eidos/adapters/sharedbrain.py |
| SB_PROJECTS_YAML | 0.05 | PROJECTS.yaml 行数 | AGENTS.md 374+386 行维护 |
| SB_PHASE17_PLAN | 0.05 | Phase 17 Wave 1 计划 | debt-cleanup-plan.md 已存在 |

来源: `.omo/state/system.yaml:104-150`

### 5.4 跌打 SLA 标准

来源: `.omo/_knowledge/governance/sla.md`

- **Critical**: 24h 响应 / 72h 修复 / 1 周内关账
- **High**: 48h 响应 / 1 周修复
- **Medium**: 1 周响应 / 2 周修复
- **Low**: 下个 Phase 顺手关账

### 5.5 治理快速入门与仪表板

- 治理快速入门: `.omo/_knowledge/governance/quickstart.md`
- 治理仪表板（HTML）: `governance-report.html`（根目录） + 生成脚本 `scripts/generate-governance-dashboard.py`
- 债务 dashboard: `.omo/_control/debt-dashboard/current.yaml`
- 健康度趋势: `.omo/_control/debt-dashboard/health-trend.md`

---

## 6. 需求（Requirements）系统

### 6.1 需求源（4 类）

1. **用户旅程探针**（R46-R50 探针系列）: 6 画像 × 8 场景域 × 58 条旅程 → 7 类摩擦点 → 3 个新功能需求
2. **治理审计探针**: 14,500+ tests / 99.4% 通过率 → 4 Critical / 5 High / 5 Medium / 4 Low
3. **架构差距分析**（OPC-ARCHITECTURE-GAPS.md）: 9 大差距 → 4 类债务
4. **产品 UX 差距**（product_ux_gap_analysis_20260610.md）: P0-P3 优先级

来源: `docs/JOURNEY-PROBES.md` · `docs/OPC-ARCHITECTURE-GAPS.md` · `docs/GOVERNANCE-ANALYSIS-REPORT.md`

### 6.2 需求 → 任务转化路径

```
用户旅程/审计发现
  ↓
需求（.omo/standards/ 下的 capability schema 验证）
  ↓
债务（.omo/debt/items/，按 SLA 分级）
  ↓
任务（planned → active → done）
  ↓
里程碑（OPC Gate 子门）
```

### 6.3 阶段需求登记

| 阶段 | 关键需求 | 来源 |
|------|----------|------|
| P0 | 19 子模块 inventory + 10 debts proposed | `docs/OPC-PHASE0-BASELINE.md` |
| P1 | 3 入口收敛（cockpit/agora/cockpit HTTP） | `docs/OPC-PHASE1-CONVERGENCE.md` |
| P1.5 | 治理文档基线（standards/ + Quick Start） | `docs/OPC-PHASE15-GOVERNANCE.md` |
| P2 | 多区记忆 + trace full_text + YAML hygiene | `docs/OPC-PHASE2-MEMORY-SPINE.md` |
| P3 | 任务对象运行时 + 派发 + 心跳 + 重试 | `docs/OPC-PHASE3-SWARM-SPINE.md` · `OPC-PHASE3-IMPLEMENTATION.md` |
| P4 | 模型/算力调度大一统 | `docs/OPC-PHASE4-MODEL-COMPUTE.md` |
| P5 | 场景化（家庭/公务/技术雷达） | `docs/OPC-PHASE5-SCENARIOS.md` |
| P6 | 进化闭环（雷达→规划→执行→审计） | `docs/OPC-PHASE6-EVOLUTION-LOOP.md` |
| P7 | 发布列车（Cross-repo rollout template） | `docs/OPC-PHASE7-RELEASE-TRAIN.md` · `cross-repo-rollout-template-2026-06-11.md` |

---

## 7. 规划（Planning）系统

### 7.1 规划产物层次

```
Roadmap (OPC-ROADMAP.md, 225 行)
  └─ 8 阶段里程碑 (M0-M7)
       └─ Phase Plan (OPC-PHASE{N}-*.md)
            └─ Playbook (OPC-MASTER-EXECUTION-PLAYBOOK.md, 664 行)
                 └─ Task Contract (YAML in .omo/tasks/{planned,active,done}/)
                      └─ Self-check script (e.g. OPC-P2-GATE-C.check.py)
```

### 7.2 规划红线（OPC-MASTER-EXECUTION-PLAYBOOK §1-3）

1. **范围纪律**: 不扩范围，不推进下一 phase（仅在 OPC 显式指令时）
2. **证据红线**: 命令 + 输出可重放，禁止"看了代码是对的"
3. **子门纪律**: "no later gate without prior close"
4. **零容忍虚假声称**（OPC 验收审查模式）: 逐条证据核对、区分 evidence type
5. **主代理路径**: 必须通过 `agora MCP :7431`，不走 stdio MCP
6. **不 git commit 跨阶段**: 主代理在 OPC 阶段内不提交跨阶段代码，由原子 commit 钩子治理

来源: `docs/OPC-MASTER-EXECUTION-PLAYBOOK.md`（664 行）

### 7.3 治理承运商（Carriers）—— P3-P7 责任人索引

来源: `docs/OPC-GOVERNANCE-CARRIERS-INDEX.md`（157 行）

- 每个阶段明确：承运项目、关键文件、关键命令、关键测试
- 治理承运商 = "phase → project → module → test" 的可追溯链

---

## 8. 里程碑（Milestone）系统

### 8.1 OPC 8 阶段里程碑

| Milestone | 阶段 | 状态 | 关键 Gate |
|-----------|------|------|-----------|
| M0 Baseline | P0 | ✅ passed (Gate A) | submodule inventory + 10 debts |
| M1 Entry Convergence | P1 | ✅ passed (Gate B) | 3 入口收敛 + 7→3 |
| M1.5 Governance | P1.5 | ✅ passed | doc baseline + SLA |
| M2 Memory Spine | P2 | ✅ passed (Gate C1-C4) | 多区可见 + trace 真实化 + YAML hygiene |
| M3 Swarm Execution | P3 | 🟡 in progress (D1+D2 passed) | D1: Task Object Runtime · D2: Dispatch |
| M4 Model/Compute | P4 | 🟠 planned | 路线图已注册 |
| M5 Scenarios | P5 | 🟠 planned | 路线图已注册 |
| M6 Evolution | P6 | 🟠 planned | 路线图已注册 |
| M7 Release | P7 | 🟠 planned | T1-T5 + Cross-repo rollout template |

来源: `git log --oneline -20` · `docs/OPC-PHASE{0-7}-*.md` · `.omo/tasks/done/OPC-P2-GATE-C.yaml`

### 8.2 下一里程碑

- **P3 D3-D5**: 任务对象 + 重试/失败/超时路径 + 收口验证
- **P3 收口**: Gate D 全 pass → 启动 P4 模型/算力规划

### 8.3 跨阶段"暂停点"风险

- **agora MCP 升级** (P34-W1-AGORA-W4-UPGRADE): 跨阶段基础设施改造，需要 OMO 审批
- **FamilyShared 未注册 l4-kernel** (documents_claude_md_deep_audit_20260610.md 遗留): 已知登记缺失
- **opc 域未注册 l4-kernel**（同上）: 后续阶段需补齐

---

## 9. 实施（Implementation）机制

### 9.1 合同派发流程（Contract-based Dispatch）

```
主代理（planning）                          工作代理（execution）
─────────────                            ─────────────
读 YAML 任务契约                         接收契约 + 入场条件
    ↓                                         ↓
列出证据要求 + 红线                       执行命令并落 evidence
    ↓                                         ↓
签发 acceptance criteria                  自检 + 报审
    ↓                                         ↓
收口验证（gate review）                    commit + 提交
    ↓
更新 YAML 状态（in_progress → done）
    ↓
注册债务（若有） / 同步 OMO 审计
```

来源: `docs/OPC-MASTER-EXECUTION-PLAYBOOK.md` · 反馈 `feedback_opc_phase_execution_contract.md`

### 9.2 试运行（Pilot）机制

- **目的**: 验证跨进程 / 跨包边界假设
- **形式**: `PILOT-external-worker-dispatch-validation.yaml` · `PILOT-worker-reclaim-handoff-validation.yaml`
- **位置**: `.omo/tasks/done/`
- **价值**: 真实跑通"代理 → 织层 → 工人 → 回流"链路，发现跨包耦合

### 9.3 收口（Closeout）机制

- **触发**: 阶段最后一步，发现 3 类缺口（治理一致性 / 证据质量 / 边界）
- **步骤**:
  1. 列缺口清单（3-5 项）
  2. 不扩范围，按缺口逐项修复
  3. 加最小测试（防回归）
  4. YAML hygiene 自检
  5. 同步 docs/ 与 .omo/state/
  6. git commit（原子）+ 根仓库指针更新
- **案例**: P2 closeout 2026-06-11 = 3 缺口（多区可见 + trace full_text + YAML 卫生）→ 9 新测试 + 10/10 self-check

### 9.4 再审（Re-review）闭环

- 用户偏好（`feedback_review_optimize_rereview.md`）: review → optimize → re-review
- 验证完成后立即 grep 全局确认无残留（治理一致性强约束）
- 关键经验: "汇总 agent 轮次需提高、跨包实现优先统一、验证环节发现深层 bug"（`fix_audit_team_retro.md`）

---

## 10. 治理（Governance）系统

### 10.1 OMO 四平面

```
┌─────────────────────────────────────────────────────────────┐
│  控制平面 │ 目标、阶段、Wave、entry_gate（.omo/goals/, state/）│
├─────────────────────────────────────────────────────────────┤
│  事实平面 │ 任务、债务、审计、债务 dashboard（.omo/tasks/, debt/）│
├─────────────────────────────────────────────────────────────┤
│  知识平面 │ 标准、能力、文档（.omo/standards/, _knowledge/） │
├─────────────────────────────────────────────────────────────┤
│  交付平面 │ commits, evidence, cross-repo rollout（git + bin/）│
└─────────────────────────────────────────────────────────────┘
```

来源: `AGENTS.md:208-247` · `docs/OPC-PHASE15-GOVERNANCE.md`

### 10.2 治理强约束（各层职责矩阵）

| 层 | Phase | Task | Debt | Audit |
|----|:---:|:---:|:---:|:---:|
| L4 l4-kernel + 21域 | ✅ | ✅ | ✅ | ✅ |
| L3 cockpit | ✅ | — | — | — |
| I0 agora | — | — | ✅ | ✅ |
| L2 kairon | ✅ | ✅ | ✅ | ✅ |
| L2 omo | 中枢 | 中枢 | 中枢 | 中枢 |
| L2 metaos | ✅ | — | ✅ | ✅ |
| L1 runtime | — | — | ✅ | ✅ |
| L0 ecos | — | — | ✅ | ✅ |

来源: `AGENTS.md:213-237`

### 10.3 信号总线（Signal Bus）

- 4 类信号：🟢 green · 🟡 yellow · 🔴 red · ⚪ idle
- 🔴 强制响应：24h 内注册 debt + 修复
- 🟡 48h 内响应
- 🟢 周期审计
- 来源: `l4-kernel/src/l4_kernel/signal_bus.py`（参考 GOVERNANCE-ANALYSIS-REPORT §10）

### 10.4 KEMS 六面（l4-kernel 域健康度）

- **K**nowledge · **E**ntities · **M**eta · **S**torage · **C**ontrol · **R**untime
- 每域独立 score，整体 health_score 加权
- 当前 health_score_raw: 100.0，显示 82.0（考虑权重与时效）

来源: `.omo/state/system.yaml:11-12`

### 10.5 治理工具链

| 工具 | 用途 | 入口 |
|------|------|------|
| `omo` | 治理 CLI | `omo governance` / `omo bos status` / `omo event emit` |
| `omo-debt` | 债务注册与排行榜 | `omo-debt register/list/leaderboard` |
| `bin/governance-audit.sh` | 6 项治理审计 | `make governance-verify` |
| `bin/omo-health.py` | 健康度检查 | `bin/omo-health.py` |
| `bin/scan_hardcoded.sh` | 硬编码扫描 | CI 集成 |
| `cockpit health --full` | L4 域健康度展示 | `cockpit` CLI |
| `ecos-ssb` / `ecos-dashboard` | 协议日志 | SSB 9090 |

来源: `AGENTS.md:170-205` · `Makefile`（根）

### 10.6 BOS URI 命名空间

- 5 大域: `bos://memory` · `bos://omo` · `bos://analysis` · `bos://persona` · `bos://forge`
- 唯一跨层调用路径（AGENTS.md:259）
- 取代直接文件 I/O 与子进程调用

来源: `AGENTS.md:208-265` · `docs/GOVERNANCE-ANALYSIS-REPORT.md:255-278`

---

## 11. 当前状态评估（2026-06-12 基线）

### 11.1 健康度快照

| 维度 | 数值 | 含义 |
|------|------|------|
| `health_score` | 82.0 | 显示分（raw 100.0） |
| `ecosystem_maturity_score` | 100 | 生态系统成熟度满分 |
| `metacognition_safety_score` | 100 | 自我认知安全满分 |
| `ecosystem_expansion_safety_score` | 100 | 扩展安全满分 |
| `governance_loop_safety_score` | 100 | 治理循环安全满分 |
| `user_value_traceability_score` | 100 | 用户价值可追溯满分 |
| `product_surface_traceability_score` | 100 | 产品面可追溯满分 |
| `knowledge_capture_search_readiness_score` | 100 | 知识捕获与搜索就绪 |
| `debt_health` | 100.0 | 债务健康满分 |
| `debt_watchlist_count` | 0 | 观察名单为 0 |
| `debt_gate_count` | 0 | 门禁债务为 0 |
| `active_tasks` | 0 | 当前活跃任务为 0 |
| `blocked_tasks` | 0 | 阻塞任务为 0 |
| `completed_tasks` | 15 | 历史完成 15 |
| `total_tasks` | 59 | 历史总任务 59 |
| `planned_tasks` | 44 | 计划队列 44 |

来源: `.omo/state/system.yaml:11-237`

### 11.2 关键里程碑进度

- ✅ P0-P2 全部通过（Baseline → Entry Convergence → Memory Spine）
- ✅ P3 D1+D2 通过（任务对象运行时绑定 + 派发）
- 🟡 P3 D3-D5 未启动
- 🟠 P4-P7 计划已注册，未启动
- ✅ 9/9 债务关账（100%）

### 11.3 待办与风险

| 类别 | 项目 | 优先级 |
|------|------|--------|
| OPC | P3 D3-D5（重试/失败/超时） | P0 |
| OPC | P4 模型/算力调度规划 | P0 |
| 注册缺失 | opc / FamilyShared 未注册 l4-kernel | P1 |
| 数据 | xplane_score 12.5（覆盖率 100% 但深度待补） | P1 |
| 健康度 | health_score 显示 82.0（raw 100）需校准 | P2 |
| 路线图 | P5-P7 计划文档已注册但 carrier index 待补 | P2 |

---

## 12. 开放问题与建议

### 12.1 已识别开放问题

1. **P3 D3-D5 的子门顺序与 D1+D2 衔接**: D2 已通过 omo native API，但 D3 (worker reclaim/handoff) 与 D4 (failure path) 与 runtime/swarm-engine 强耦合，需要更多试运行
2. **P4 路线图只有文档没有 carrier**: `docs/OPC-PHASE4-MODEL-COMPUTE.md` 存在但 P3-P7 的承运商索引可能不完整
3. **跨阶段基础设施改造的"暂停点"**: agora MCP 升级、FamilyShared 注册需要 OMO 审批流程
4. **历史 Phase 编号与 OPC 阶段的双轨**: 短期不冲突但需统一术语

### 12.2 推荐下一步

1. **本周末**: 启动 P3 D3（worker reclaim/handoff 试运行）
2. **下周**: 启动 P4 承运商索引补齐（参考 OPC-GOVERNANCE-CARRIERS-INDEX.md）
3. **持续**: 治理仪表板（`governance-report.html` + `.omo/_control/debt-dashboard/current.yaml`）的 xplane_score 12.5 → 提升到 80+
4. **Q3 末**: 完成 P3 → P4 → P5 阶段路线图，确保 P7 Release Train 启动条件成熟

### 12.3 风险点

- **债务 SLA 维持 100% 健康**: 9/9 关账后若新发现 debt 未及时关账会快速降级
- **P3 收口若发现新缺口**: 需重走 closeout 流程（3 缺口 → 修复 → 自检 → 同步）
- **跨阶段基础设施改造**: opc/FamilyShared 注册缺失可能阻塞后续阶段

---

## 附录 A: 关键文件索引

| 主题 | SSOT 路径 |
|------|----------|
| 当前目标 | `.omo/goals/current.yaml` |
| 当前状态 | `.omo/state/system.yaml` |
| 任务 SSOT | `.omo/tasks/{planned,active,in_progress,review,done}/` |
| 债务 SSOT | `.omo/debt/items/` + `debt/registry.yaml` |
| 治理标准 | `.omo/standards/` |
| OPC 路线图 | `docs/OPC-ROADMAP.md` |
| OPC 执行合同 | `docs/OPC-MASTER-EXECUTION-PLAYBOOK.md` |
| OPC 阶段文档 | `docs/OPC-PHASE{0,1,1.5,2,3,4,5,6,7}-*.md` |
| 全景图 | `docs/PANORAMA.md` |
| 治理体系分析 | `docs/GOVERNANCE-ANALYSIS-REPORT.md`（与本报告互补） |
| 用户旅程探针 | `docs/JOURNEY-PROBES.md` |
| 跨仓库发布模板 | `docs/cross-repo-rollout-template-2026-06-11.md` |
| 入口收敛 | `docs/ENTRY-CONVERGENCE.md` |
| 治理承运商 | `docs/OPC-GOVERNANCE-CARRIERS-INDEX.md` |

## 附录 B: 关联 commits（2026-06-11 ~ 12）

- `b6fd4672` — docs: 项目架构与治理体系分析报告（既有）
- `9c9e1e3b` — docs: 治理快速入门指南
- `9dd7059e` — feat: 治理度量 API + Makefile target
- `c977ef24` — ci: 债务审计 GitHub Actions
- `35128597` — docs: 治理 SLA 标准
- `cba4c11d` — feat: 债务排行榜 + Makefile target
- `0a2daa2f` — chore(opc): register P3-P7 plans + sync state docs
- `db797da2` — feat: 治理数据 JSON 暴露
- `3d1acb2d` — feat: 债务审计脚本 + Makefile target
- `c6ca84ff` — feat: 治理仪表板可视化
- `2f89cf6f` — chore: bump agora/cockpit/ecos/omo/metaos — .githooks/ 治理统一
- `53772d72` — chore(opc): OPC P2 closeout — YAML hygiene + docs sync
- `2fc2282f` — feat: 添加治理检查 Makefile targets
- `f324fed0` — docs: 治理流程标准化文档
- `7a92f384` — chore: bump omo-debt — register 简化命令
- `0a6711f0` — feat: 添加健康度趋势追踪
- `3f909120` — chore: bump kairon — hooks 迁移到 .githooks/
- `e9fe18b3` — chore(opc): P3 Gate D2 passed
- `284462c2` — chore(opc): P3 Gate D1 passed
- `1c0ca6ce` — OPC-P7 T1-T5 + 路线图 8 阶段收官报告

---

**报告状态**: 已生成。**下次刷新触发**: P3 D3 收口 / P4 启动 / 重大架构调整。
**SSOT 维护**: 本报告为"导读索引"，所有事实以 `path:line` 反向引用至 SSOT。
