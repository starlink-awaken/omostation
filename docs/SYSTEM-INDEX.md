# SYSTEM-INDEX.md — Workspace 全景导航

> **维护规则**
> - owner: governance-team
> - trigger: 重大架构变更、新项目加入、工具链变更
> - method: 人工维护框架结构，具体内容指向各索引
> - validation: 所有指针路径必须存在（doc-ssot-lint 扩展检测）
> - status: active
> - created_at: 2026-07-14

---

## 快速开始

1. 读本文 → 了解全局结构
2. 读目标项目 `AGENTS.md` → 了解操作规则
3. 查 `INDEX-TOOLS.md` → 找可用工具
4. 查 `INDEX-KNOWLEDGE.md` → 查历史决策

---

## 层模型

见 `ARCHITECTURE.md` §2 和 `docs/project-registry.yaml::layers`。

当前架构为 **5+4+1+1 分层**：
- L0: 协议层
- L1: 运行时层
- L2: 引擎层
- L3: 入口层
- L4: 自我层
- I0: 织层
- M0: 横切框架
- X: 横切扩展

---

## SSOT 导航

| 需要什么 | 去哪里读 | 维度 |
|----------|---------|------|
| 项目元数据 | `docs/project-registry.yaml` | 事实层 |
| 运行时状态 | `.omo/state/system.yaml` | 事实层 |
| 架构契约 | `ARCHITECTURE.md` | 架构层 |
| 端口分配 | `protocols/port-registry.yaml` | 边界层 |
| 治理规则 | `.omo/_truth/registry/governance-checks.yaml` | 事实层 |
| 文档治理 | `.omo/_truth/registry/document-governance.yaml` | 事实层 |
| 文档模板 | [`templates/`](templates/) (ssot/derived/ephemeral 三类) | 架构层 |
| ADR 决策 | `.omo/_knowledge/decisions/INDEX.md` | 知识层 |
| BOS 服务 | `projects/agora/etc/bos-services.yaml` | 边界层 |
| L0 约束 | `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` | 协议层 |
| MOF 能力 | `.omo/_truth/registry/mof-capabilities.yaml` | 事实层 |
| LECP 统一生命事件契约 | `protocols/lecp-schema.yaml` | 协议层 |
| 能力联合关系与状态边界 | [`architecture/capability-federation-contract-v1.md`](architecture/capability-federation-contract-v1.md) | 架构层 |
| 运维脚本入口 | [`bin/README.md`](../bin/README.md) | 运行时工具 |
| 空间配置入口 | `spaces/AGENTS.md` · `spaces/registry.yaml` | 空间策略 |

---

## 分类索引

→ [项目索引](INDEX-PROJECTS.md) — 项目按层/栈/状态分类（见 `docs/project-registry.yaml`）

→ [跨包 API 地图](overview/cross-package-api-map.md) — Kairon BOS 路由与跨包接口（生成物）

→ [工具索引](INDEX-TOOLS.md) — bin/ + .agents/skills 统一目录

→ [知识索引](INDEX-KNOWLEDGE.md) — ADR + 审计 + 模式 + 总结交叉索引
→ [计划与决策台账](plans/) — 3Y-BET-LEDGER 等计划/台账文档

### 场景执行架构 (四面一脊)

→ [脊面运行模式 SFOP/v1](architecture/os-operating-pattern-v1.md) — 把分层 / 四面 / 8D / AGE-v2 / resident / BCOS 收成一套槽位语法
→ [道法术器 DFSQ/v1](architecture/dao-fa-shu-qi.md) — MOF 嵌套的理论体系；器自报槽位；dispatcher 唯一性硬检查 (`sfop-slots`)
→ [Scene Cards](scene-cards/) — 9 个场景卡 (external + internal_pipeline, 双轨准入)
→ [Journey Specs](journey-specs/) — 3 个 journey 状态机 (inbox-to-decision, meeting-to-delivery, research-to-insight)
→ [External Connection Fabric](../.omo/standards/external-connection-fabric.md) — §7: dual-track admission standard
→ [Permission Scope Vocabulary](../.omo/standards/permission-scope-vocabulary.yaml) — RBAC scope 受控词表
→ [Signal Sources](../.omo/_truth/registry/signal-sources.yaml) — 感知面信号源注册表

→ [Agent 能力索引](INDEX-AGENTS.md) — 当前 agent 配置 + 技能清单

→ [Closeout 记录](closeout/) — 各轮关闭记录和复盘（详见 `docs/closeout/`）

→ [交付笔记](notes/) — 快速 closeout 模板与交付闭环笔记（详见 `docs/notes/`）

→ [操作 SOP](operations/) — 运维手册、清单、模板（详见 `docs/operations/`；含 [codebase-memory](operations/codebase-memory.md) 结构图用法；Memory OS： [memory-os-neo4j-local](operations/memory-os-neo4j-local.md) · [memory-os-epic-retro](operations/memory-os-epic-retro.md)）

→ [架构设计](architecture/) — 方案设计文档（详见 `docs/architecture/`；含 [Memory OS](architecture/memory-os.md) 控制面导航与 [Capability Federation](architecture/capability-federation-contract-v1.md) 跨注册表合同）

→ [ISA 分析](isa/) — 接口/服务/架构图（详见 `docs/isa/`）

→ [设计方案](proposals/) — 设计提案和历史方案（详见 `docs/proposals/`）

→ [本地计算集群](local-compute/) — omlx 集群架构（详见 `docs/local-compute/`）

→ [战略体检报告](reports/) — c2g.strategy 周期产出的战略/治理健康周报（详见 `docs/reports/`）

→ [织星架构战略深度复盘](reports/2026-08-20-blueprint-strategy-retrospective.md) — 三轴完成语义、机制收敛、Golden Slice 准入与停线边界

→ [共享运行时协调缺口](downloads/2026-08-14-shared-runtime-coordination-gap.md) — 运行时共享边界与待治理缺口
→ [运营基础设施治理简报](downloads/AGENT-BRIEF-OPS-INFRA-GOVERNANCE.md) — 运营治理执行摘要
→ [战略收敛剩余项简报](downloads/AGENT-BRIEF-STRATEGY-CONVERGENCE-REMAINDER.md) — 战略收敛剩余工作
→ [架构战略展望 2026-08](downloads/ARCHITECTURE-STRATEGY-OUTLOOK-2026-08.md) — 架构战略展望
→ [决策场景推导确认](downloads/DECISION-SCENARIO-DERIVATION-CONFIRMATION-2026-08.md) — 决策与场景推导确认

→ [BET-Y1Q2-T1-19 权威复盘](../.omo/_knowledge/retros/BET-Y1Q2-T1-19.md) — Codex ACP 切割的当前事实与未证边界

→ [CR08 卫健委三医态势安装态审计复盘](reports/2026-08-14-weijian-sanyi-status-audit-retrospective.md) — 临时隔离源码的只读审计边界与可复核证据

→ [执行计划](plans/) — 三年规划执行台账与 agent 执行指令（详见 `docs/plans/`）

- [`plans/3Y-BET-LEDGER.md`](plans/3Y-BET-LEDGER.md) — 三年规划执行台账（人类视图）。SSOT 为 `plans/3y-bet-ledger.yaml`，CLI `bin/plan/bet-ledger.py`
- [`plans/AGENT-BRIEF.md`](plans/AGENT-BRIEF.md) — 多 agent 认领与执行指令（首次执行前通读）
- [`plans/AGENT-TEMPLATES.md`](plans/AGENT-TEMPLATES.md) — 按轨道分工的 agent 指令模板（8 轨道 + 协调者 + 观察者）
- [`plans/AGENT-GOALS-4X.md`](plans/AGENT-GOALS-4X.md) — goal 模式：4 agent 并行持续推进的零冲突组合与 LOOP 协议
- [`plans/2026-08-06-agora-p2-deepening-plan.md`](plans/2026-08-06-agora-p2-deepening-plan.md) — agora P2 深化计划
- [`superpowers/specs/2026-08-13-orchestration-contract-mvp-design.md`](superpowers/specs/2026-08-13-orchestration-contract-mvp-design.md) — 编排器无关的 WorkPacket/CompletionManifest/独立验证合同
- [`superpowers/plans/2026-08-13-orchestration-contract-mvp.md`](superpowers/plans/2026-08-13-orchestration-contract-mvp.md) — 上述合同的 TDD 实施与验收计划
- [`superpowers/specs/2026-08-13-personal-capability-mainline-restore.md`](superpowers/specs/2026-08-13-personal-capability-mainline-restore.md) — Personal 能力主线恢复与子模块防回退合同
- [`superpowers/specs/2026-08-13-codex-exec-worker-design.md`](superpowers/specs/2026-08-13-codex-exec-worker-design.md) — Codex 无人值守 bounded worker、执行副本与事务回写合同
- [`superpowers/plans/2026-08-13-codex-exec-worker.md`](superpowers/plans/2026-08-13-codex-exec-worker.md) — Codex worker 的 TDD、Orca 运输与独立复核计划
- [`superpowers/specs/2026-08-14-supervised-blueprint-control-loop-design.md`](superpowers/specs/2026-08-14-supervised-blueprint-control-loop-design.md) — 人工确认 Codex TUI、证据收集与补偿回滚合同
- [`superpowers/specs/2026-08-14-codex-acp-stdio-cutover-design.md`](superpowers/specs/2026-08-14-codex-acp-stdio-cutover-design.md) — Codex ACP stdio 权限代理、真实 canary 与 cli_prompt 退役合同
- [`superpowers/specs/2026-08-14-weijian-sanyi-status-consistency-design.md`](superpowers/specs/2026-08-14-weijian-sanyi-status-consistency-design.md) — 卫健委 CR08 三医态势只读一致性审计合同
- [`superpowers/plans/2026-08-14-weijian-sanyi-status-consistency.md`](superpowers/plans/2026-08-14-weijian-sanyi-status-consistency.md) — 卫健委 CR08 三医态势一致性审计实施与安装态验收计划
- [`superpowers/plans/2026-08-14-supervised-blueprint-control-loop.md`](superpowers/plans/2026-08-14-supervised-blueprint-control-loop.md) — 受监督 Blueprint 控制闭环实施与真实 dogfood 计划

---

## 文档维护生命周期

### 索引维护责任矩阵

| 事件 | 影响的索引 | 更新方式 | 优先级 |
|------|-----------|---------|--------|
| 新项目加入 | INDEX-PROJECTS | 脚本重新生成 | P1 |
| 项目归档 | INDEX-PROJECTS | 脚本重新生成 | P1 |
| 新增 bin/ 工具 | INDEX-TOOLS | 脚本重新生成 | P2 |
| 新增 ADR | INDEX-KNOWLEDGE | 脚本重新生成 | P2 |
| 新增审计 | INDEX-KNOWLEDGE | 脚本重新生成 | P2 |
| 新增 skill | INDEX-AGENTS | 脚本重新生成 | P2 |
| Agent CLI 升级 | INDEX-AGENTS | 脚本重新生成 | P3 |
| 架构层变更 | SYSTEM-INDEX | 人工更新 | P1 |

### 阅读指南

#### 新 Agent 进入 Workspace

```
第 1 步: 读 SYSTEM-INDEX.md（了解全局）
第 2 步: 读目标项目 AGENTS.md（了解操作规则）
第 3 步: 按需查 INDEX-TOOLS.md（找工具）
第 4 步: 按需查 INDEX-KNOWLEDGE.md（查历史决策）
```

#### 查找特定信息

| 我想找什么 | 去哪里 |
|-----------|--------|
| 某个项目在哪个层 | INDEX-PROJECTS.md → 按层分类 |
| 某个工具怎么用 | INDEX-TOOLS.md → 按用途分类 |
| 某个主题有哪些决策 | INDEX-KNOWLEDGE.md → 按主题索引 |
| 当前 agent 有哪些技能 | INDEX-AGENTS.md → 技能分布 |
| 端口号是多少 | protocols/port-registry.yaml（不经过索引） |
| 当前 Phase 是多少 | .omo/state/system.yaml（不经过索引） |

---

## 项目文档矩阵

| 文档 | 事实层 | 架构层 | 操作层 | 边界层 | 入口层 |
|------|:------:|:------:|:------:|:------:|:------:|
| project-registry.yaml | **OWN** | — | — | — | — |
| system.yaml | **OWN** | — | — | — | — |
| ARCHITECTURE.md | ref | **OWN** | — | — | — |
| AGENTS.md | ref | ref | **OWN** | — | — |
| CLAUDE.md | ref | ref | **OWN** | — | — |
| BOUNDARY.md | ref | ref | — | **OWN** | — |
| CALLCHAIN.md | ref | ref | — | ref | — |
| README.md | ref | ref | ref | — | **OWN** |
| LAYER-INDEX.md | ref | **OWN** | — | — | — |
| PANORAMA.md | ref | **OWN** | — | ref | — |

---

## 工具分类导航

| 域 | 主要工具 | 位置 |
|----|---------|------|
| GaC 治理即代码 | gac-validate, gac-drift, gac-local-gate | bin/gac/ |
| ADR 治理 | adr-coverage, adr-drift-check | bin/adr/ |
| SSOT 守护 | doc-ssot-lint, ssot-guardian | bin/ssot/ |
| 能力联合审计 | capability-sync federation-audit | bin/capability-sync.py |
| MOF 工具 | mof-enforce, mof-reason | bin/mof/ |
| Agent 工作流 | agent-workflow.py | bin/ |
| 场景执行 | journey-runner, signal-poller, scene-reflection, scene-outcome-recorder, capability-token | bin/ssot/ |
| 场景准入 | internal/external-scene-trial, internal/external-activation-preflight, scene-card-lifecycle | bin/ssot/ |
| 场景验证 | scene-chain-validator, journey-validator, adr-number-check | bin/ssot/ |
| Resident 常驻 Agent | resident-status resident-roles resident-daemon | Makefile (`omo resident`) |
| BCOS 业务域 | bcos-evolve bcos-signals bcos-north-star | Makefile (`bin/bc-os/`) |

详见 `INDEX-TOOLS.md` 获取完整工具目录。

---

## 知识资产分类

| 类型 | 位置 |
|------|------|
| ADR 决策 | `.omo/_knowledge/decisions/`（见 `INDEX.md` 索引） |
| 审计报告 | `.omo/_knowledge/audits/` |
| 模式总结 | `.omo/_knowledge/patterns/` |
| 管理文档 | `.omo/_knowledge/management/` |

详见 `INDEX-KNOWLEDGE.md` 获取完整知识索引。

---

## 关联文档

→ [ARCHITECTURE.md](../ARCHITECTURE.md) — 架构契约
→ [AGENTS.md](../AGENTS.md) — Agent 操作指南
→ [CLAUDE.md](../CLAUDE.md) — 会话上下文加载
→ [README.md](../README.md) — 项目快速开始
→ [doc-ssot-contract.md](../.omo/standards/doc-ssot-contract.md) — 文档正交契约
→ [document-governance-standard.md](../.omo/standards/document-governance-standard.md) — ownership/lifecycle/freshness 契约
→ [layer-contract.yaml](layer-contract.yaml) — 分层依赖规则
→ [生成的索引](generated/) — `project-layer-index.md`, `agent-gac-rules.md` 等自动生成的文档
→ [近期报告](closeout/) — 2026-07-15 各轮 closeout 记录

- [closeout-template-5min](notes/closeout-template-5min.md)
- [closeout-template-5min-dev](notes/closeout-template-5min-dev.md)
- [governance-runtime-convergence-closeout-20260814](notes/governance-runtime-convergence-closeout-20260814.md)
- [governance-runtime-convergence-rca-20260814](notes/governance-runtime-convergence-rca-20260814.md)
- [mechanism-convergence-retrospective-20260815](notes/mechanism-convergence-retrospective-20260815.md)
→ [运行验证证据](evidence/) — 可重放、脱敏的交付验证回执
→ [T1-18 Codex 人工确认 canary](evidence/t1-18-codex-dogfood-canary.md) — Orca 交互式 Codex 手动批准验证工件
→ [操作 SOP](operations/) — 运维手册、模板、清单
→ [BET-Y1Q3-T4-01 交付证据](operations/value-evidence/BET-Y1Q3-T4-01/) — value-evidence/: [ACCEPTANCE](operations/value-evidence/BET-Y1Q3-T4-01/ACCEPTANCE.md) · [human_verdict](operations/value-evidence/BET-Y1Q3-T4-01/human_verdict.md) · [real_signal](operations/value-evidence/BET-Y1Q3-T4-01/real_signal.md) · [revision](operations/value-evidence/BET-Y1Q3-T4-01/revision.md) · [time_burden](operations/value-evidence/BET-Y1Q3-T4-01/time_burden.md) · [engineering/](operations/value-evidence/BET-Y1Q3-T4-01/engineering/) · [operational/](operations/value-evidence/BET-Y1Q3-T4-01/operational/)

## docs/ 专题子目录

-→ [ADR 镜像](adr/) — `docs/adr/` ADR 决策镜像 (同 .omo/_knowledge/decisions)
-→ [交付证据](evidence/) — `docs/evidence/` bet 级验证回执
-→ [治理文档](governance/) — `docs/governance/` 治理架构与 bin/scripts 规划
-→ [命令审计](command-audit/) — `docs/command-audit/` 15 维命令体系评估与审计报告
-→ [superpowers 计划](superpowers/plans/) — `docs/superpowers/plans/` 增强工作流计划
-→ [superpowers 规格](superpowers/specs/) — `docs/superpowers/specs/` 增强工作流设计规格
## docs/ 根目录平铺文档

历史专题与顶层参考 (架构/战略/治理/G-DEL 系列等) 平铺于 docs/ 目录下,
按文件名检索: ARCHITECTURE-*.md, STRATEGY-*.md, GOVERNANCE-*.md,
G-DEL-*.md, INDEX-MCP.md, CLI-REFERENCE.md, M4-*.md, KEMS-*.md,
KOS-*.md, SOP-*.md, VISION-ROADMAP.md 等。


## 治理自进化工具集 (2026-08-22)

| 工具 | 职责 | 入口 |
|------|------|------|
| meta-doctor | M1+M2 活性巡检 | `python3 bin/gac/meta-doctor.py --workspace . --json` |
| scheduler-compile | 调度编译器 ADR-A | `python3 bin/scheduler-compile.py --check` |
| session-handoff | 会话交接协议 R6 | `python3 bin/gac/session-handoff.py --session <id> ...` |
| heartbeat-wrapper | cron 心跳包装器 ADR-D | `bash bin/gac/heartbeat-wrapper.sh <job> <cmd>` |
| vocabulary.yaml | 词汇契约 SSOT | `.omo/_truth/vocabulary.yaml` |

## Resident 常驻 Agent 体系 (2026-08-23, WP-A~I / ADR-0396)

| 面 | 入口 |
|----|------|
| 功能规格 | [`docs/architecture/resident-agent-system-v1.md`](architecture/resident-agent-system-v1.md) |
| 状态/角色 | `make resident-status` / `make resident-roles`（`omo resident status/roles`） |
| 路由表 SSOT | `projects/omo/src/omo/resident/resident-routes.yaml`（schema `resident-routes/v1`） |
| MOF 元模型 | `projects/ecos/src/ecos/ssot/mof/m2/digital_agent.yaml`（DigitalAgent, tier=resident） |
| BOS URI | `bos://resident/core/status|roles`、`bos://resident/daemon/once`、`bos://resident/decision/run` |

## BCOS 业务域系统 (2026-08-23, W1~W4)

| 面 | 入口 |
|----|------|
| 功能规格 | [`docs/architecture/bcos-system-v1.md`](architecture/bcos-system-v1.md) |
| 进化引擎 | `make bcos-evolve`（`bin/bc-os/evolution_engine.py`, 四阶段） |
| 信号路由 | `make bcos-signals`（`bin/bc-os/signal_router.py`, W1-D2） |
| 北极星度量 | `make bcos-north-star`（`bin/bc-os/north_star_meter_v2.py`, 排除 self-data） |
| MOF 元模型 | `projects/ecos/src/ecos/ssot/mof/m2/bcos_system.yaml`（BCOSystem） |
| BOS URI | `bos://bcos/evolution/*`、`bos://bcos/signals/*`、`bos://bcos/north-star/*` |
