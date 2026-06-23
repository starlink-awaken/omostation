---
plane: knowledge
type: governance
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
freshness: 2026-05-31
maintainer: auto
note: "P55 R2: 历史 Phase 6 pre-gate governance (2026-05-31), 当前已进入 Phase 55+, governance 100 A+ 持续"
---

# Phase 6 pre-gate governance

## Scope

本文件不是 Phase 6 实施计划，而是 **进入 Phase 6 之前的治理决策包**。  
目标是把上一轮复盘里已经确认的两条主线收敛成一个不会失焦的执行结构：

1. **Implementation track**
   - Durable execution
   - Governance runtime
   - Auto-discovery
   - Templates
   - Skill federation
2. **Hardening track**
   - 安全 P0/P1
   - 可靠性 P0/P1
   - `orphaned_tasks` / dangling-reference 等机制债务

## Executive decision

**Decision**: 采用 **hardening-first pre-gate + gated implementation program**，而不是直接把两个 track 并行拉成一个 Phase 6 执行面。

原因很简单：

1. **治理成熟度已经领先于运行成熟度**
   - Phase 5 完成了治理边界冻结，但没有交付完整 Task Center runtime。
2. **review blockers 仍具备 entry-blocking 性质**
   - 安全评审和可靠性评审中的 P0/P1，不适合降级成“实现后再补”。
3. **`.omo` 自身还有机制债务未清**
   - `orphaned_tasks:31` 说明当前系统虽然可观察，但还不够可治理。

所以正确顺序不是：

- 先实现，再慢慢修；

而是：

- **先完成进入实现所需的最小硬化治理，再让 implementation track 启动。**

## Approach options

### Option A — 双轨同相并行

Implementation 与 Hardening 同属一个 live Phase 6，同时 seed 两条 active queue。

**优点**

- 看起来推进最快
- 文档上只有一个 phase

**缺点**

- 最容易把 P0/P1 blocker 稀释成普通 backlog
- active queue 会再次混合“实现项”和“护栏项”
- Phase 5 刚冻结的边界会立刻承受执行压力

### Option B — Recommended: hardening-first pre-gate + gated implementation

先定义一个 **Phase 6 pre-gate hardening tranche**，只处理“必须先收紧才能进入 runtime 实现”的事项；  
pre-gate 通过后，再启动正式的 implementation waves。

**优点**

- 与本仓库当前成熟度最匹配
- 能把 blocker 和 feature work 区分清楚
- 便于把 review 结论转成 entry criteria，而不是事后补丁

**缺点**

- 前期看起来“没有直接做功能”
- 对 gate discipline 要求更高

### Option C — implementation-first with guardrails

先做 runtime 最小闭环，同时只保留少量护栏。

**优点**

- 最快看到 runtime 形态
- 容易形成 demo

**缺点**

- 高概率复制 Phase 5 之前的老问题：设计先跑、机制后补、证据再追
- 会把安全/可靠性 review 重新降级成 advisory

## Chosen governance model

### 1. 不立刻开启 live Phase 6

当前 `state/system.yaml` 保持 `Phase 5 completed / Phase 6 planning gate` 是对的。  
在以下条件满足前，**不得** seed Phase 6 active tasks：

1. 安全 P0/P1 被明确映射到可执行任务和验证策略
2. 可靠性 P0/P1 被明确映射到可执行任务和验证策略
3. `orphaned_tasks` / dangling-reference 被拆成结构化治理对象，而不是继续保留大 blob
4. Implementation track 的 owner plane / runtime landing / verification packet 被重新确认

### 2. 进入 Phase 6 前先做一个 pre-gate tranche

这个 tranche 的目标不是“交付 Task Center”，而是**交付进入 Task Center implementation 所需的治理条件**。

建议命名口径：

- **Pre-Phase 6 governance tranche**
- 或 **Phase 6 entry hardening packet**

它只负责三类输出：

1. **blocking backlog**
   - 把 review blockers 和机制债务拆成明确任务簇
2. **entry criteria**
   - 定义什么条件下 implementation track 才能启动
3. **verification contract**
   - 每类 blocker 要用什么测试/演练/证据来关闭

### 3. 真正的 Phase 6 只承载 implementation program

pre-gate 通过后，再把 Phase 6 作为 runtime implementation phase 启动。  
此时 Hardening 不消失，但角色变化：

- **pre-gate hardening** = entry-blocking
- **in-phase hardening** = slice guardrail

也就是说：

1. 先关掉“不能带着它进入 runtime”的问题
2. 再允许实现期继续伴随式补强

## Track decomposition

### Track H — hardening

#### H1. Security baseline

必须先处理这些 entry blockers：

1. subprocess 调用安全边界
   - `shell=False`
   - 参数白名单/显式构造
2. secret ownership
   - 全面收敛到 `secret_ref`
   - 不允许 registry/proposal/runtime metadata 混入 secret value
3. HMAC / compare / token validation
   - 采用 safe compare
4. child execution isolation posture
   - 至少明确高风险执行的隔离策略，不允许默认裸奔
5. log redaction
   - delivery evidence 不得把 secret/token 直接写进运行记录

#### H2. Reliability baseline

这些也应视为 entry blockers：

1. checkpoint / run record 原子写入
2. watchdog + heartbeat
3. queue cap / backpressure
4. crash / restart recovery 的明确状态机
5. retention / archival / cleanup 策略

#### H3. Mechanism debt convergence

这部分属于 `.omo` 自身治理债务：

1. 把 `orphaned_tasks` 从 blob 拆成结构化 artifact
2. 增加 dangling-reference 检测与分级
3. 让 divergence 从“可见”升级为“可逐项认领、可逐项关闭”
4. 防止索引/总结文档重新复制 live facts

### Track I — implementation

Phase 6 正式启动后，implementation 仍按冻结好的 seam 推进，但顺序要更硬：

#### I1. Durable + governance core

第一个 implementation slice 必须先做：

1. step checkpoint schema
2. resume / recovery policy
3. proposal / approval / apply / verify runtime path
4. audit + delivery trace continuity

**原因**：没有这层，后面的 auto-discovery / templates / skills 都只会堆在不稳定地基上。

#### I2. Discovery + templates

在 runtime core 稳定后再推进：

1. script frontmatter schema
2. directory scan + registry reconciliation
3. blueprint/template model
4. template instantiation flow

#### I3. Skill federation

最后再把 AI-native skill 接到同一治理链上：

1. skill declaration schema
2. skill-to-task mapping
3. governed execution bridge
4. skill delivery evidence

## Entry criteria for Phase 6

建议把以下条件视为 **Phase 6 GO** 的最小门槛：

1. **Security GO**
   - secret model 已统一到 `secret_ref`
   - 高风险 subprocess posture 已定
   - 日志脱敏规则可验证
2. **Reliability GO**
   - 原子写入、watchdog、backpressure 的 baseline 已定义并有验证路径
   - crash/restart 状态转移规则已冻结
3. **Mechanism GO**
   - `orphaned_tasks` 有结构化治理模型
   - dangling-reference 有检测入口
   - indexes 未重新复制 live counters
4. **Implementation GO**
   - implementation track 只从 I1 开始，不允许直接跳到 templates/skills
   - owner plane 与 landing rule 已确认

## Suggested milestone model

### Milestone P6-G0 — pre-gate hardening closeout

关闭所有 entry-blocking 项，产出：

1. blocker backlog packet
2. verification packet
3. closeout retrospective
4. GO/NO-GO judgment

### Milestone P6-G1 — runtime core

只做 I1：

1. durable execution
2. governance runtime
3. recovery / trace / audit baseline

### Milestone P6-G2 — definition compression

只做 I2：

1. discovery
2. templates

### Milestone P6-G3 — governed skill execution

只做 I3：

1. skill federation
2. AI execution evidence

## Anti-corruption rules

进入下一阶段前，继续坚持这四条铁律：

1. **blocker 不能伪装成 feature**
   - review P0/P1 不能与普通 feature task 混排
2. **dynamic fact 只能存在于 live source**
   - INDEX / summary 不复制动态计数
3. **one owner plane per runtime entity**
   - registry / proposals / runs / evidence 不能跨平面双写
4. **every implementation slice closes with evidence**
   - design packet / delivery packet / verification packet / retrospective packet 缺一不可

## Governance recommendation

如果只保留一句治理结论，那就是：

> **Phase 6 不应该被定义成“马上开做 runtime 的下一期”，而应该被定义成“先通过 pre-gate hardening，再进入 runtime implementation 的受控阶段”。**

这能同时满足两件事：

1. 不浪费 Phase 5 冻结出来的边界
2. 不让 review blockers 和机制债务继续滚到真正 runtime 里

## Immediate next step

下一步不是 seed implementation tasks，而是先产出一个 **Phase 6 entry hardening packet**，把下面三类内容显式任务化：

1. security P0/P1
2. reliability P0/P1
3. divergence / dangling-reference debt

在这个 packet 完成前，Phase 6 只应停留在 **planning gate**。
