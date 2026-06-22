---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
---

# Post-Phase1 治理收敛规范与 Phase 2 入场方案

> 状态: historical
> 说明: 这是 Phase 1 关闭 / Phase 2 入场时的历史 gate snapshot。
> 当前执行请以 `.omo/goals/current.yaml`、`.omo/state/system.yaml` 与 `.omo/standards/phase2-full-execution-go-no-go.md` 为准。

> 日期: 2026-05-30  
> 状态: active  
> 适用范围: `.omo` 治理体系、Phase 1 关闭、Phase 2 启动门禁  
> 输入文档: `../_knowledge/design/MASTER-BLUEPRINT.md`, `_archive/CONSISTENCY-CHECK.md`, `plans/README.md`, `plans/archive/phase1-verification-report.md`, `summaries/phase1-retrospective.md`, `plans/archive/phase2-task-specs-v2.md`, `plans/archive/phase3-task-specs-v2.md`, `plans/archive/phase4-task-specs-v2.md`, `plans/deep-architecture-agent-analysis.md`, `plans/agent-architecture-audit-redteam.md`, `plans/comprehensive-architecture-audit.md`, `goals/current.yaml`, `state/system.yaml`, `tasks/README.md`, `_archive/TASK_POOL.md`, `PROJECTS.yaml`, `convergence.yaml`, `LAYER-INDEX.md`

---

## 1. 结论摘要

Phase 1 可以判定为 **工程交付基本完成**，但不能直接判定为 **治理关闭完成**。

当前证据呈现三层状态：

| 层级 | 当前判断 | 依据 |
|------|----------|------|
| 工程交付 | 基本完成 | `phase1-retrospective.md` 记录 21/21 核心任务完成，E2E、故障注入、性能、memU 均通过 |
| 运行时验证 | 证据冲突，需统一 | `phase1-retrospective.md` 记录 Docker 4/4 Healthy；`phase1-verification-report.md` 记录代码 7/7 PASS，但 Docker/smoke runtime PENDING |
| 治理状态 | 未关闭 | `goals/current.yaml`, `state/system.yaml`, `convergence.yaml`, `LAYER-INDEX.md`, `_archive/TASK_POOL.md` 仍显示 Phase 1 进行中、旧任务池或过期状态 |

因此后续不能直接从 Phase 2 的 47 项任务全量并发启动。正确路径是先执行 **M2.0 治理收敛与 Phase 1 正式关闭**，再进入 Phase 2 的 P0 入场包。

---

## 2. 最新 `.omo` 更新纳入后的权威判断

### 2.1 最新规划主线

当前应以以下文档为规划主线：

| 优先级 | 文件 | 角色 |
|--------|------|------|
| P0 | `../_knowledge/design/MASTER-BLUEPRINT.md` | 全景蓝图，定义长期架构、阶段、能力增长、SSOT 7 域 |
| P0 | `plans/README.md` | 计划文档注册表，定义 EXECUTION / ACTIVE / REFERENCE / ARCHIVED |
| P0 | `plans/archive/phase2-task-specs-v2.md` | Phase 2 当前执行候选规格，47 任务 |
| P1 | `plans/deep-architecture-agent-analysis.md` | ACP、Agent-as-Kernel、控制面、安全机制设计来源 |
| P1 | `plans/agent-architecture-audit-redteam.md` | 安全红队约束来源 |
| P1 | `plans/comprehensive-architecture-audit.md` | SSOT 7 域、KOS 退化、连接器与长期缺口来源 |
| P2 | `plans/archive/phase3-task-specs-v2.md` / `phase4-task-specs-v2.md` | 只作为后续依赖图，不作为当前执行入口 |

旧的 `_archive/GOVERNANCE_PLAN.md`, `_archive/TASK_POOL.md` Phase 6X, 更早 Phase 9/13 计划只能作为历史参考，不能继续作为执行源。

### 2.2 Phase 1 证据冲突

`phase1-retrospective.md` 与 `phase1-verification-report.md` 对运行时验收的结论不同：

- 复盘报告显示：烟雾测试 5/5 PASS、E2E 11/11 PASS、故障注入 5/5 PASS、Docker 4/4 Healthy。
- 验证报告显示：代码产出 7/7 PASS，Docker compose 与 smoke test 因 Docker 网络原因 PENDING。

规范上应采用更严格表述：

> Phase 1 = Code Complete + Evidence Reconciliation Required。

只有当运行时证据被统一归档，并更新到治理状态源后，Phase 1 才能标记为 Closed。

### 2.3 治理状态漂移

当前存在以下状态漂移：

| 文件 | 当前问题 | 应收敛到 |
|------|----------|----------|
| `goals/current.yaml` | 仍是 Phase 1 active，G1.2/G1.3 pending | Phase 1 迁入 history，current 切到 Phase 2 gated |
| `state/system.yaml` | current_phase=1，completed_tasks=7/24，health=66.80 | 显示 Phase 1 code_complete / Phase 2 ready_pending_gates |
| `.omo/tasks/` | 只有 README，无 active/done/blocked 任务文件 | 成为机器可读任务 SSOT |
| `_archive/TASK_POOL.md` | 仍是旧 Phase 6X done | 降级为任务镜像或历史索引 |
| `convergence.yaml` | notes 仍写 Phase 1 进行中 | 更新为 Phase 1 code_complete，runtime evidence reconciled/pending |
| `LAYER-INDEX.md` | 仍写 Phase 1 进行中，LiteLLM 适配器待创建 | 与复盘/验证报告统一 |

---

## 3. `.omo` 治理 SSOT 规范

### 3.1 文档权威分层

| 层级 | 文件/目录 | 权威范围 | 禁止事项 |
|------|-----------|----------|----------|
| Strategy | `.omo/MASTER-BLUEPRINT.md` | 长期架构、路线图、阶段目标 | 不记录实时任务状态 |
| Plan Registry | `.omo/plans/README.md` | 规划文档状态、执行规格入口 | 不承载任务进度 |
| Execution Specs | `.omo/plans/phase{N}-task-specs*.md` | 阶段候选任务和验收清单 | 不直接代表已开工 |
| Goals SSOT | `.omo/goals/current.yaml` + history | 当前 Phase 目标与 Go/No-Go 状态 | 不由普通 agent 随意改写 |
| Runtime State | `.omo/state/system.yaml` | 聚合后的系统状态 | 只能由 aggregator 或人工校准更新 |
| Task SSOT | `.omo/tasks/{active,done,blocked}/*.yaml` | 任务执行状态 | 不再由 `_archive/TASK_POOL.md` 作为真实源 |
| Evidence | `.omo/summaries/*.md`, reports | 验收证据、复盘、审计结果 | 不作为调度入口 |
| Standards | `.omo/standards/*.md` | 跨阶段规范、边界、法则 | 不记录一次性任务 |

### 3.2 任务状态规范

每个可执行任务必须有独立 YAML 文件：

```yaml
id: P2-M2.1-KOS-REPAIR
phase: 2
milestone: M2.1
priority: P0
title: "Restore KOS baseline"
status: pending
owner: null
source_docs:
  - ".omo/plans/archive/phase2-task-specs-v2.md"
  - ".omo/plans/comprehensive-architecture-audit.md"
depends_on:
  - "M2.0-PHASE1-CLOSE"
entry_gate:
  - "Phase 1 governance closed"
  - "KOS source inventory available"
evidence_required:
  - "before/after document count"
  - "10 known docs search: 10/10 found"
  - "health monitor threshold configured"
risk_level: L1
operation_level: L1
human_approval_required: false
```

任务状态流转：

```text
candidate -> pending -> in_progress -> review -> done
                         |              |
                         v              v
                      blocked         failed
```

规则：

1. `candidate` 表示来自计划但尚未通过入场门禁。
2. `pending` 表示已通过入场门禁，可被 agent 认领。
3. `review` 表示实现完成但证据待验收。
4. `done` 必须包含 evidence。
5. `blocked` 必须包含 blocker、owner、下一次检查时间。
6. 普通 agent 只能修改自己认领的任务文件，不能批量重写其他任务。

### 3.3 规划文档状态规范

`plans/README.md` 已提出 EXECUTION / ACTIVE / REFERENCE / ARCHIVED；补充如下约束：

| 状态 | 是否可执行 | 规则 |
|------|------------|------|
| EXECUTION | 是 | 只能有当前 phase 和已批准的下一 phase |
| ACTIVE | 否，除非被 EXECUTION 引用 | 可持续更新，但不得直接派发任务 |
| REFERENCE | 否 | 只能提供上下文，不得覆盖新规格 |
| ARCHIVED | 否 | 不参与 agent 搜索式执行 |

Phase 2 当前可以保持 `phase2-task-specs-v2.md` 为 EXECUTION 候选，但必须增加 M2.0 入场门禁后才允许启动实际任务。

---

## 4. Phase 1 正式关闭门禁

Phase 1 关闭必须满足以下 8 项：

| Gate | 要求 | 验收证据 |
|------|------|----------|
| G1 | 代码交付完成 | `phase1-verification-report.md` 代码 7/7 PASS |
| G2 | 运行时证据统一 | 选择并归档 Docker/smoke/E2E 的最终可信证据 |
| G3 | Phase 1 目标归档 | `goals/current.yaml` 迁移为 `goals/history/phase1.yaml` |
| G4 | 当前目标切换 | `goals/current.yaml` 改为 Phase 2 gated |
| G5 | 系统状态刷新 | `state/system.yaml` 不再显示 completed 7/24 的旧状态 |
| G6 | 任务系统初始化 | `.omo/tasks/` 下生成 Phase 2 M2.0/M2.1/M2.2 任务文件 |
| G7 | 索引文档同步 | `convergence.yaml`, `LAYER-INDEX.md`, `PROJECTS.yaml` 与 Phase 1 结论一致 |
| G8 | 旧任务池降级 | `_archive/TASK_POOL.md` 明确标记为历史镜像或迁移入口 |

关闭输出：

```text
Phase 1 status = closed | code_complete_with_runtime_evidence | phase2_gated_ready
```

如果 G2 仍无法验证，则允许状态为：

```text
Phase 1 status = code_complete | runtime_verification_pending | phase2_limited_entry_allowed
```

但此时 Phase 2 只能启动治理、安全、KOS 诊断类任务，不得启动敏感连接器。

---

## 5. Phase 2 入场方案

### 5.1 Phase 2 不应全量并发启动

`phase2-task-specs-v2.md` 已扩展为 47 项，覆盖 KOS、SSOT、连接器、模型花园、KEMS、ACP、控制器、安全框架、死锁检测等。直接全量启动会带来三个风险：

1. KOS 退化未修复，后续知识任务都建立在不可靠索引上。
2. RBAC/操作分级/审计尚未就绪，Apple/Obsidian/模型/Agent 沙箱等能力会扩大攻击面。
3. `.omo` 任务 SSOT 未收敛，多 agent 会从冲突文档中领取不一致任务。

### 5.2 Phase 2 M2.0-M2.5 优化里程碑

| Milestone | 名称 | 目标 | 禁止提前启动 |
|-----------|------|------|--------------|
| M2.0 | 治理收敛与 Phase 1 关闭 | 解决状态漂移，建立任务 SSOT | 所有业务连接器 |
| M2.1 | KOS baseline restore | 诊断并修复 10165 -> 700 退化，建立健康基线 | 跨域研究、KEMS runtime |
| M2.2 | Safe Mesh | RBAC、L0-L3 操作分级、审计、HITL、死锁检测最小闭环 | Apple/WeChat/家庭 OS |
| M2.3 | SSOT 7 域最小注册 | 7 域 schema 注册、验证、追溯闭环 | 全量数据摄取 |
| M2.4 | 真实知识闭环 | 用户问题 -> KOS/Obsidian -> minerva -> 保存 -> 审计可见 | 高自主自愈 |
| M2.5 | 扩展能力评审 | 再决定模型花园、KEMS、Apple 连接器进入顺序 | WeChat/Family OS/SMB |

### 5.3 Phase 2 P0 入场包

建议首批只开启以下任务：

| 编号 | 任务 | 来源 | 验收标准 |
|------|------|------|----------|
| P0-1 | M2.0 Phase1 governance close | 本规范 | 8 个关闭门禁完成或明确豁免 |
| P0-2 | KOS index degradation diagnosis | `phase2-task-specs-v2.md` C1a | 找到 10165 -> 700 根因 |
| P0-3 | KOS repair plan + no-loss guard | `phase2-task-specs-v2.md` C1b/C4 | 修复计划含回滚、暂停写入、健康监控 |
| P0-4 | Operation Levels skeleton | `phase2-task-specs-v2.md` SAFE_1 | MCP tool 至少能标记 L0-L3 并拒绝未确认 L2 |
| P0-5 | Agent Registry heartbeat/cache design | `phase2-task-specs-v2.md` ACP_1 | registry 不成为单点故障 |
| P0-6 | Task YAML migration seed | `tasks/README.md` | M2.0-M2.2 任务进入 `.omo/tasks/active` |

---

## 6. 架构边界规范

### 6.1 系统职责边界

| 模块 | 应负责 | 不应负责 |
|------|--------|----------|
| Agora / I0 | MCP transport、service registry、routing、circuit breaker、observability entry、operation-level enforcement hook | 业务推理、知识处理、免疫判断 |
| agentmesh | Agent runtime、task dispatch、LLM routing、tool gateway、agent capability abstraction | 领域知识权威、合规最终裁决 |
| SharedBrain | policy authority、immune decision、compliance、self-healing、EU/安全控制面 | 个人知识摄取、KOS 索引、研究推导 |
| kairon | knowledge pipeline、KOS、minerva、kronos、ssot、eidos、methodology runtime | 运行时合规最终控制权 |
| gbrain | 记忆与知识脑后端、长期上下文存储 | Agent 编排中枢 |
| ops | audit persistence、health dashboard、backup、incident evidence | 业务任务编排 |
| ACP / layer controllers | advisory control plane、状态感知、推荐调度、冲突检测 | 绕过 Agora/agentmesh 形成第二套隐藏编排 |

### 6.2 Agent-as-Kernel 安全约束

`deep-architecture-agent-analysis.md` 与红队审计已经给出必要安全机制，纳入硬规范：

1. 破坏性操作永远不能由 LLM Agent 自主执行。
2. L0 读操作可自主；L1 低风险写必须审计；L2 高风险写必须人工确认；L3 破坏性操作必须人工确认 + 冷静期。
3. 新 Agent 必须先进入 sandbox，默认只读、无外网、有限资源。
4. Dispatcher 必须支持 P0/P1/P2/P3 优先级和 QoS。
5. Registry 必须有 heartbeat、本地缓存和身份校验。
6. 控制器必须有滞回、冷却期和冲突仲裁，避免振荡。
7. Agent 死锁必须可检测、可告警、可从 checkpoint 恢复。

---

## 7. Milestone 验收规范

每个 milestone 必须同时满足五类验收：

| 类型 | 必填问题 |
|------|----------|
| 用户可见结果 | 用户能看到什么新能力或风险下降？ |
| 系统证据 | 哪些测试、日志、健康指标、审计记录证明它完成？ |
| 失败注入 | 至少模拟一个失败场景，系统如何降级或拒绝？ |
| 回滚/延期条件 | 什么情况下不能继续下一个 milestone？ |
| 最终验收者 | human / aggregator / CI / audit 哪个是最终确认源？ |

禁止只用以下内容作为完成标准：

- 文件已创建。
- MCP tool 已注册但没有调用证据。
- 文档已更新但状态源未同步。
- 单元测试通过但没有集成路径。
- Agent 自称完成但没有 evidence。

---

## 8. Phase 3/4 更新规划的处理原则

Phase 3 v2 和 Phase 4 v2 已经吸收了跨域研究、家庭 OS、WeChat、设备协同、SMB、媒体索引、隐私隔离、备份策略等规划。它们方向正确，但必须受 Phase 2 门禁约束：

1. **WeChat / Apple / Family / SMB / Media** 属于高敏感连接器，必须等 Safe Mesh、RBAC、数据隔离、审计可用后再启动。
2. **KOS self / 高自主 / 自愈** 必须等 KOS baseline 与操作分级稳定后再启动。
3. **跨域研究** 必须等 SSOT 7 域最小注册和 KOS 检索质量达标后启动。
4. **设备协同** 必须等 agent identity、registry heartbeat、operation levels 完成后启动。
5. **备份策略** 应前置为安全基础能力的一部分，但不能在没有 dry-run、hash 校验和人工确认时执行真实覆盖性操作。

---

## 9. 推荐执行顺序

```text
Step 0: Freeze execution source
  - 宣布 plans/README + goals/current + tasks/*.yaml 为新执行源
  - TASK_POOL.md 降级为历史镜像

Step 1: Close Phase 1 governance
  - 统一 Phase 1 runtime 证据
  - 迁移 current goal 到 history
  - 刷新 state/system/convergence/LAYER-INDEX

Step 2: Seed Phase 2 task YAML
  - 只生成 M2.0-M2.2 P0/P1 任务
  - 其他 47 项先保留 candidate

Step 3: KOS + Safe Mesh first
  - KOS 诊断/修复/健康监控
  - Operation Levels、RBAC、audit、Agent registry heartbeat

Step 4: SSOT 7 domains minimal registration
  - 先注册 schema 和 authority，不做全量摄取

Step 5: Run one real knowledge loop
  - Obsidian/KOS/minerva/gbrain/audit 形成闭环

Step 6: Re-plan Phase 2 remaining work
  - 决定模型花园、KEMS、Apple connector 的真实优先级
```

---

## 10. 立即行动清单

| 优先级 | 动作 | 输出 |
|--------|------|------|
| P0 | 选择 Phase 1 runtime 可信证据 | `phase1-verification-report.md` 或新 evidence append |
| P0 | 建立 `.omo/goals/history/phase1.yaml` | Phase 1 目标归档 |
| P0 | 将 `goals/current.yaml` 改为 Phase 2 gated | Phase 2 进入受控状态 |
| P0 | 初始化 M2.0-M2.2 task YAML | `.omo/tasks/active/*.yaml` |
| P0 | 更新 `state/system.yaml` | current_phase=2 或 phase2_ready_pending_gates |
| P1 | 更新 `convergence.yaml` / `LAYER-INDEX.md` | 消除 Phase 1 进行中漂移 |
| P1 | 将 `_archive/TASK_POOL.md` 标记为历史镜像 | 防止 agent 误执行旧 Phase 6X |
| P1 | 给 Phase 2 v2 增加 M2.0 作为前置 | 防止 47 项任务直接并发 |

---

## 11. Go/No-Go 判定

### 允许进入 Phase 2 limited entry 的条件

- Phase 1 code evidence 已归档。
- `.omo` 执行源已冻结。
- M2.0-M2.2 任务 YAML 已创建。
- KOS 修复任务和 Safe Mesh 任务处于 P0。

### 禁止进入 Phase 2 full execution 的条件

任何一项存在即禁止全量启动：

- KOS 10165 -> 700 根因未知。
- Operation Levels 未能拒绝未确认 L2 操作。
- RBAC/Audit 没有最小闭环。
- `.omo/tasks/` 仍为空。
- `goals/current.yaml` 与 `state/system.yaml` 仍停留 Phase 1。
- Phase 1 runtime 证据冲突未说明。

### 禁止进入 Phase 3/4 的条件

- Safe Mesh 未通过失败注入。
- SSOT 7 域没有最小 authority/schema。
- 高敏感连接器没有数据隔离策略。
- Agent-as-Kernel 没有 sandbox、deadlock detection、checkpoint。

---

## 12. 规范化后的 Phase 2 核心目标

Phase 2 不再定义为“知识深化 + 连接器扩张”，而应定义为：

> 在 Phase 1 基础设施之上，先恢复知识基线和安全控制面，再以最小 SSOT 7 域闭环证明 Personal AI OS 可以可靠地读、想、写、审计。

成功标志：

1. KOS 恢复可信检索。
2. `.omo` 不再出现执行状态漂移。
3. MCP/Agent 操作有 L0-L3 分级和审计。
4. SSOT 7 域至少可注册、校验、追溯。
5. 有一个真实用户知识闭环可端到端运行。
6. Phase 3/4 的敏感能力被明确 gate，而不是提前扩张。
