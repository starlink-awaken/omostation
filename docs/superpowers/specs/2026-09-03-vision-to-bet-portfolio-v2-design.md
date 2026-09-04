---
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-03
last-reviewed: 2026-09-03
bet_id: BET-Y1Q4-T1-03
risk_level: L2
human_gate: true
value_indicator_policy: false
source_design_sha256: cbdee89004d0156e262daa63a1c38cfd660c0d5efbf0fce1a8eec8a92027c30b
source_proposal_sha256: 26bd1b3df552e693f2ac2684df255436522ff816d7844459523fafe130587100
source_amendment_sha256: 5b1bb03274d8f7383b67f88953cf0c7074a571a9a1d5aebb1ab68bb234042409
source_id_collision_amendment_sha256: 1a6a63d4fc20b6d3f385b27518018fdb633e5cd38ee9c171db1c08773eecd992
implementation_authorized: false
---


# Vision-to-BET Portfolio v2 机制升级设计

## 0. 执行摘要

本设计把现有 `docs/plans/3y-bet-ledger.yaml` 从“扁平任务台账”升级为
“愿景—目标—关键结果—战役—里程碑—BET”的唯一机器可读组合管理 SSOT。

它不创建新的项目管理服务、数据库、dispatcher、workflow engine 或 truth
plane。战略文档继续负责人类可读的长期方向；Ledger 负责机器可读的组合真值；
`.omo/goals/current.yaml` 降为 Ledger 的自动生成投影；OMO / Workflow Mesh
继续拥有唯一执行状态与证据真值；Cockpit 只消费投影并呈现组合状态。

核心判定从：

```text
所有 BET 都是 done
```

升级为：

```text
每个必需 Objective 的 Key Result 都有直接证据并达到阈值
AND 每个 Campaign 的 exit gate 通过
AND 每个 mandatory leaf BET 已 done，或由已完成 replacement BET 完整覆盖
AND 12 周最终价值窗口通过
AND P0 guardrail breach = 0
```

The approved Documents draft originally stopped before repository mutation.
That sentence is retained here as historical provenance, not the current
binding boundary. This accepted repository Spec authorizes only the separately
approved ten-path binding bootstrap; it still authorizes no writing-plans,
implementation, runtime mutation, completion transition, or value evidence.

## 1. 问题定义与直接证据

### 1.1 Fixed-ref audit evidence, not runtime facts

The approved Documents source recorded a point-in-time audit at root
`785b77f7cd3154457a7fd6c934cd7166245ebafa`; its immutable source digest is in
this Spec frontmatter. Mutable BET/status/edge counts are intentionally not
repeated in this active contract and no acceptance gate consumes the historical
numbers.

Every implementation or migration run must measure the current immutable
Ledger directly through `bet-ledger.py portfolio status --json`. Before
Portfolio v2 exists, the compatibility audit derives equivalent inventory and
dependency facts directly from `docs/plans/3y-bet-ledger.yaml`.

The approved finding is structural: dependency mechanics are reusable, while
Objective/KR/Milestone/parent coverage is absent from the legacy contract.

### 1.2 当前 Goals 事实

`.omo/goals/current.yaml` 同时包含历史 Wave、旧 BET、归档项和手工进度，文件
自身已经声明 `entry_gate: deprecated-use-bet-ledger`。它不能继续作为独立目标
真值，否则会与三年 Ledger 形成双写。

### 1.3 当前 chain-bind 能力边界

现有 `bin/plan/chain_bind.py` 能验证：

- workflow start 是否绑定 BET；
- North Star 文件是否存在；
- run 与 BET 是否一致；
- closeout 是否存在 retro。

它不能验证：

- BET 服务哪个 Objective/KR；
- KR 是否被至少一个 mandatory BET 覆盖；
- Campaign 是否还有未关闭的关键路径；
- BET done 是否真正推动了 KR；
- 失败 BET 是否有 replacement；
- Milestone 是否在 outcome 未证明时被提前关闭；
- 最终愿景是否满足持续时间窗口。

### 1.4 根因

现有模型优化的是“单项交付合规”，没有优化“组合结果完整”。因此系统容易出现：

1. 大量任务完成，但最终目标没有同步推进；
2. 治理类 BET 持续增长，因为它们容易产生明确交付物；
3. 产品价值只能从任务状态推测，而不能从 KR 直接读取；
4. 新想法被直接写成 candidate，缺乏组合容量和优先级约束；
5. `done` 成为活动终点，而不是结果证明。

## 2. 架构决策

### 2.1 采用方案 A

```text
┌──────────────────────────────────────────────────────────────┐
│ Human-readable Strategy                                      │
│ docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md                     │
│ 愿景叙事、长期方向、人工决策、证伪条件                       │
└──────────────────────────────┬───────────────────────────────┘
                               │ exact pointer + digest
┌──────────────────────────────▼───────────────────────────────┐
│ Portfolio SSOT                                               │
│ docs/plans/3y-bet-ledger.yaml                                │
│ Vision / Objectives / KRs / Campaigns / Milestones / BETs   │
└───────────────┬───────────────────────┬──────────────────────┘
                │                       │
        derived projection       Spec / WorkPacket compile
                │                       │
┌───────────────▼────────────┐  ┌──────▼──────────────────────┐
│ .omo/goals/current.yaml    │  │ OMO / Workflow Mesh        │
│ 只读生成投影，不再手写     │  │ 唯一执行状态与证据真值     │
└───────────────┬────────────┘  └──────┬──────────────────────┘
                │                       │ evidence/outcome
                └──────────────┬────────┘
                               │
                      ┌────────▼────────┐
                      │ Cockpit         │
                      │ 目标/KR/关键路径│
                      └─────────────────┘
```

### 2.2 被拒绝方案

| 方案 | 决定 | 原因 |
|---|---|---|
| Goals 管 Objective，Ledger 管 BET | 拒绝 | 两份手工 SSOT 必然漂移 |
| 新建 Portfolio 数据库/服务 | 拒绝 | 增加第二状态库和第二入口 |
| 继续使用扁平 Ledger | 拒绝 | 无法证明 all-BET→Vision |
| 一次性重写整个历史 Ledger | 拒绝 | diff 不可审、历史证据易损 |
| 以 done 总量推导愿景进度 | 拒绝 | 活动量不是价值量 |

## 3. 战略—战役—战术—战斗模型

| 层级 | 机器实体 | 回答的问题 | 生命周期 | 所有权 |
|---|---|---|---|---|
| 战略 | `vision` / `objective` | 为什么做、最终何时算完成 | 长期、人工关闭 | human-principal |
| 战争/战役 | `campaign` / `milestone` | 哪些阶段必须打赢 | 派生状态 | portfolio compiler |
| 战术 | `workstream` | 哪条能力路径推进 KR | 派生状态 | campaign owner |
| 战斗 | `bet` | 下一项可证伪交付是什么 | 现有 BET 状态机 | OMO + Ledger |

### 3.1 不把所有层级都做成 BET

Vision、Objective 和 KR 是结果合同，不是任务。Campaign 是组合容器，Milestone
是结果门。只有可在 0.5–5 天内独立验证、可失败、可回滚的工作才是 leaf BET。

父 BET 只用于：

- 编排 child BET；
- 冻结组合边界；
- 验证 child 与 KR 覆盖；
- 执行 root-last closeout；
- 不复制 child 状态或价值证据。

## 4. Portfolio v2 数据模型

### 4.1 顶层模型

现有 Ledger 顶层增加下列可选结构，并将 `meta.schema_version` 提升为
`bet-portfolio/v2`：

```yaml
meta:
  schema_version: bet-portfolio/v2
  status_enum:
    - candidate
    - pending
    - in_progress
    - review
    - done
    - blocked
    - failed

vision:
  id: VISION-2029
  statement: >-
    把外部信号变成夏明星愿意署名发出的成果，并记住每次修改。
  owner: human-principal
  horizon_end: 2029-06-30
  strategy_ref: repo://docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
  falsifier:
    metric: accepted_outputs_per_week
    operator: lt
    threshold: 3
    consecutive_weeks: 12
    decision: narrow_or_shutdown
  required_objectives:
    - OBJ-VALUE
    - OBJ-EXPERIENCE
    - OBJ-TRUST
    - OBJ-LEARNING
    - OBJ-HOLDABILITY
    - OBJ-SCALE

objectives: []
campaigns: []
milestones: []
bets: []
```

现有 `meta.total_bets` 字段继续保留为整数以兼容消费者，但不再由人手决定；
生成器每次从 `len(bets)` 派生，在 `--check` 模式拒绝任何漂移。

### 4.2 Objective 与 KR

```yaml
- id: OBJ-VALUE
  statement: 持续产生真实、被采用的业务成果
  owner: human-principal
  required: true
  key_results:
    - id: KR-VALUE-REAL-OUTCOMES
      metric: rolling_7d_real_decision_outcomes
      baseline:
        value: null
        status: unmeasured
      target:
        operator: gte
        value: 20
        consecutive_windows: 4
      evidence_policy:
        require_real_signal: true
        require_human_verdict: true
        reject_partitions:
          - test
          - synthetic
          - user_provided_without_lineage
      status: unmeasured
      evidence_refs: []
```

KR 状态枚举：

```text
unmeasured → baselined → tracking → proven
                         └────────→ failed
```

规则：

- `status=proven` 必须由 validator 从数据和 evidence refs 派生；
- Agent 不得直接把 KR 写成 proven；
- 没有 baseline 的改善类指标不得设置百分比目标；
- 所有时间窗口必须记录起止时间、采样规则和缺失数据语义；
- 任何代理指标必须显式标记 `proxy=true`，且不得关闭价值 KR。

### 4.3 Campaign 与 Milestone

```yaml
- id: CMP-W0-PORTFOLIO-TRUTH
  title: Portfolio/BET v2 机制升级
  objective_refs:
    - OBJ-TRUST
    - OBJ-HOLDABILITY
  owner: portfolio-governance
  target_window: Y1Q4
  required_milestones:
    - MS-W0-CONTRACT
    - MS-W0-MIGRATION
    - MS-W0-PRODUCT
    - MS-W0-CANARY
  max_parallel_writers: 2
  status: derived

- id: MS-W0-CANARY
  campaign_ref: CMP-W0-PORTFOLIO-TRUTH
  required_bets:
    - BET-Y1Q4-T1-09
  required_krs:
    - KR-TRUST-CHAIN-COVERAGE
    - KR-HOLDABILITY-ORPHAN-BETS
  exit_gate:
    all_required_bets_terminal: true
    all_required_krs_proven: true
    p0_guardrail_breaches: 0
  status: derived
```

Campaign 和 Milestone 状态完全派生，禁止手工设置 `done`。

### 4.4 BET v2 扩展字段

```yaml
- id: BET-Y1Q4-T1-04
  track: T1-TRUTH
  window: Y1Q4
  campaign_ref: CMP-W0-PORTFOLIO-TRUTH
  milestone_refs:
    - MS-W0-CONTRACT
  objective_refs:
    - OBJ-TRUST
    - OBJ-HOLDABILITY
  kr_refs:
    - KR-TRUST-CHAIN-COVERAGE
  parent_bet: BET-Y1Q4-T1-03
  bet_type: mechanism
  title: Portfolio v2 schema and compatibility validator
  hypothesis: >-
    如果 Ledger 能表达并校验 Objective/KR/Campaign/Milestone/BET 关系，
    就能在执行前发现战略覆盖缺口，而不是在大量 BET done 后才发现愿景未推进。
  baseline:
    objective_ref_coverage:
      source: implementation_time_ledger
    orphan_nonterminal_bets:
      source: implementation_time_ledger
  target:
    new_or_modified_nonterminal_portfolio_coverage: 1.0
    missing_dependency_ids: 0
    dependency_cycles: 0
  leading_indicators:
    - v2_schema_parse_pass
    - legacy_fixture_compatibility_pass
  lagging_indicators:
    - orphan_nonterminal_bets
    - milestone_false_close_count
  guardrails:
    - no_terminal_evidence_rewrite
    - no_new_truth_plane
    - no_status_transition_during_migration
  entry_gate:
    accepted_spec_binding: required
    exact_write_surfaces_claimed: true
    parent_bet_status: pending_or_in_progress
  kill_criteria:
    - requires_new_database
    - requires_second_dispatcher
    - cannot_preserve_legacy_ledger_reads
  replacement_policy:
    on_failed: require_replacement_bet_or_campaign_replan
  value_indicator_policy: false
```

### 4.5 状态语义保持兼容

现有 BET 状态枚举不扩张：

| 状态 | Portfolio v2 语义 |
|---|---|
| candidate | 已登记假设，未获得执行准入；可无 accepted Spec |
| pending | Spec/WorkPacket/依赖/授权全部就绪，可启动 |
| in_progress | 存在唯一 active governed run |
| review | 实现完成，等待验收或人类门 |
| done | BET 合同完成，不代表 KR 自动 proven |
| blocked | 可恢复阻断；必须记录 blocker 和 re-entry gate |
| failed | 假设或执行失败；必须绑定 replacement 或关闭相应覆盖 |

候选 BET 不因为“未来可能有用”就进入 pending。只有进入近期 Milestone、依赖
满足、accepted Spec 存在、WorkPacket 可编译时，才能 candidate→pending。

## 5. 唯一真值与投影边界

| 数据 | 权威来源 | 其他位置的性质 |
|---|---|---|
| 愿景叙事 | 三年战略文档 | Ledger 存 pointer + digest |
| Objective/KR/Campaign/Milestone/BET | `3y-bet-ledger.yaml` | 唯一机器 SSOT |
| 当前目标视图 | `.omo/goals/current.yaml` | 自动生成投影 |
| Run/claim/lock/lease | OMO Workflow Mesh | 运行真值 |
| Spec/WorkPacket identity | accepted Spec + compiler | 不复制到新库 |
| 工程/运行/价值证据 | completion matrix + receipts | 轴向隔离 |
| 用户工作台 | Cockpit | 只读 projection；动作委托 OMO |
| 长期学习 | MOS/KOS | 消费 outcome，不改组合真值 |

禁止：

- Cockpit 直接写 Ledger；
- `.omo/goals/current.yaml` 被 Agent 手工编辑；
- OMO 自行把 KR 标成 proven；
- MOS/KOS 的推断覆盖 human-principal 的 Objective；
- 另建 Portfolio SQLite、service、scheduler 或 event ledger；
- Orca/Codex worker 状态成为组合真值。

所有 `.omo` 投影更新必须通过已登记的 OMO state/projection broker；生成器只
负责计算 canonical bytes 和 digest，不得直接覆写 `.omo/goals/current.yaml` 或
`.omo/_control/portfolio-status.json`。

## 6. 完成判定

### 6.1 BET 完成

```python
def bet_done(bet, evidence, run, retro):
    return (
        all_done_when_verified(bet, evidence)
        and verify_commands_passed(bet, evidence)
        and run.is_closed_ok
        and retro.matches_bet
        and no_scope_violation(run)
        and no_p0_guardrail_breach(bet, evidence)
        and completion_axes_derive_declared_state(bet, evidence)
    )
```

### 6.2 Milestone 完成

```python
def milestone_met(milestone, portfolio):
    return (
        every_required_bet_done_or_replaced(milestone, portfolio)
        and every_required_kr_proven(milestone, portfolio)
        and unresolved_blocker_count(milestone, portfolio) == 0
        and p0_guardrail_breach_count(milestone, portfolio) == 0
    )
```

### 6.3 Vision 完成

```python
def vision_complete(vision, portfolio, evidence_window):
    return (
        all_required_objectives_proven(vision, portfolio)
        and all_required_campaigns_met(portfolio)
        and evidence_window.consecutive_weeks >= 12
        and evidence_window.weekly_accepted_outputs >= 5
        and evidence_window.acceptance_rate >= 0.40
        and evidence_window.edit_burden_drop >= 0.40
        and evidence_window.real_signal_only
        and evidence_window.p0_guardrail_breaches == 0
        and human_principal_final_verdict() == "accepted"
    )
```

## 7. 覆盖图与依赖规则

### 7.1 两类边

仅保留两类机器边，避免过度建模：

1. `depends_on`：执行前置，必须 DAG；
2. `covers`：BET→KR、Milestone→KR 的结果覆盖。

父子关系通过 `parent_bet` 表达组合所有权，不作为执行依赖；若 child 确实需要
父 BET 先完成某项能力，仍须显式写入 `depends_on`。

### 7.2 覆盖守恒

每个 required KR 必须满足：

```text
至少一个 mandatory BET 覆盖
OR 一个已 proven 的既有 evidence source 直接覆盖
```

每个非终态 BET 必须满足：

```text
属于一个 Campaign
AND 引用至少一个 Objective
AND 引用至少一个 KR
```

失败、删除或 supersede 一个 BET 时，compiler 必须重新计算 KR coverage；若变成
零覆盖，变更立即 fail-closed。

### 7.3 关键路径

Critical path 由 `depends_on` 和 Milestone target window 派生。系统只显示：

- 当前关键路径 BET；
- 被阻断的下游 BET 数；
- 下一项最小可执行 BET；
- 组合 WIP 和 writer 冲突；
- 不显示以任务总数推导的虚假完成百分比。

## 8. 迁移策略

### 8.1 兼容原则

1. 不重写任何历史 terminal BET 的 status、completion/value evidence 或 retro；
2. terminal legacy BET 缺 v2 字段时作为 grandfathered history，只产生信息提示；
3. 所有新 BET 和被修改的非终态 BET 必须满足 v2；
4. 执行时测得的所有 non-terminal BET 逐条分类，不批量自动决定业务去留；
5. `meta.total_bets` 漂移单独修复，不借机修改任何 BET；
6. 迁移先生成 manifest，再由人类批准分批应用；
7. 每批最多修改 8 个非终态 BET；
8. 每批必须结构比较所有未授权 BET 对象 byte/semantic 等价。

### 8.2 五类处置

| 分类 | 含义 | 动作 |
|---|---|---|
| reuse | 已完成能力可作为新 Campaign 前置 | 只引用，不改历史证据 |
| continue | 非终态 BET 与 W1–W6 明确重合 | 增加 v2 组合字段 |
| merge | 多个候选覆盖同一 KR | 选一个 canonical，其他绑定 replacement |
| defer | 有长期价值但不在当前 Milestone | 保持 candidate，不进入 pending |
| stop | 不再服务最终愿景 | 单独审议失败/终止，不伪装 done |

### 8.3 迁移步骤

```text
M1 read-only inventory
  → 生成 implementation-time 全量 BET 分类与覆盖报告，不写 Ledger
M2 schema compatibility
  → v1 Ledger 在 v2 validator 下保持可读
M3 nonterminal classification
  → implementation-time 全部非终态 BET 分批补充组合引用
M4 derived projections
  → 生成 goals/current 与 Markdown view
M5 enforcement
  → 只对 new/modified nonterminal BET fail-closed
```

## 9. 接口与产品入口

### 9.1 CLI

复用 `bin/plan/bet-ledger.py`，不新增顶级 CLI：

```text
bet-ledger.py portfolio lint
bet-ledger.py portfolio status
bet-ledger.py portfolio coverage
bet-ledger.py portfolio critical-path
bet-ledger.py portfolio milestone <ID>
bet-ledger.py portfolio migrate --dry-run
bet-ledger.py portfolio project-goals --check
bet-ledger.py portfolio project-goals --apply
```

默认命令必须只读；只有显式 `--apply` 允许生成投影，且不得改变 BET status、
completion 或 value evidence。

### 9.2 Cockpit

只增加现有 `cockpit portfolio` 域下的只读视图：

```text
cockpit portfolio status
cockpit portfolio objectives
cockpit portfolio critical-path
cockpit portfolio blockers
```

Cockpit 不直接完成 BET、KR 或 Milestone。所有状态动作仍委托 Ledger/OMO 的
canonical command。

### 9.3 生成物

建议生成：

- `docs/plans/3Y-BET-PORTFOLIO.md`：人类组合视图；
- `.omo/goals/current.yaml`：当前 Objective/KR/Milestone 投影；
- `.omo/_control/portfolio-status.json`：Cockpit 只读 projection。

三者必须带 source digest，生成器 `--check` 对 drift 返回非零；三者均不得成为
反向 writer。涉及 `.omo` 的两份投影只能由已登记 broker 原子写入，不能由
`portfolio_projection.py` 直接 `write_text`。

## 10. W0 父子 BET 设计

以下 ID 为提议 ID。进入绑定前必须用 current-main next-ID/collision check 再确认；
发现占用时只调整 ID，不改变语义。

### 10.1 Parent — `BET-Y1Q4-T1-03`

**标题**：Vision-to-BET Portfolio v2 组合真值收敛

**类型**：milestone / parent，`value_indicator_policy=false`

**目标**：编排七个 child BET，证明 Ledger 可表达并验证 Vision→KR→BET→Run→
Outcome→Retro 全链，且没有第二真值面。

**非目标**：不实施 W1–W6；不把其全部 BET 写入 Ledger；不修改个人价值；不重写
历史 terminal evidence；不创建服务或数据库。

**完成条件**：

1. child T1-04/T1-05/T1-06/T1-07/T1-08/T8-05/T1-09 全部 done；
2. W0 四个 Milestone 全部 derived=met；
3. implementation-time 全部非终态 BET 都有建议分类，但只有另行批准的批次落盘；
4. v1 read compatibility、v2 fail-closed、projection drift 和 negative fixtures 全绿；
5. Cockpit 只读视图与 CLI 同 digest；
6. 一个真实但 value-exempt 的 dogfood BET 完整走通；
7. 独立审查、required checks、post-merge exact-SHA check 和 clone cleanup 完成。

### 10.2 Child — `BET-Y1Q4-T1-04`

**标题**：Portfolio v2 schema 与兼容 validator

**负责**：顶层 v2 数据模型、解析、字段/引用/枚举验证、v1 兼容。

**前置**：Parent accepted binding。

**预计写面**：

- `bin/plan/portfolio_contract.py`
- `bin/plan/bet-ledger.py`
- `tests/test_bet_portfolio_contract.py`
- 本 child Spec、plan、retro；
- Ledger 仅写本 child binding/状态，不迁移其他 BET。

**验证**：

- v1 full Ledger 解析通过；
- v2 valid fixture 通过；
- missing Objective/KR/Campaign、重复 ID、错误枚举、错误 metric shape 全部拒绝；
- 任何现有 BET semantic object 不因 parser 发生改变。

**熔断**：需要数据库、新服务或破坏现有 `bet-ledger.py` 命令时停止。

### 10.3 Child — `BET-Y1Q4-T1-05`

**标题**：Objective/KR/BET coverage graph 与 critical path

**负责**：`depends_on` DAG、`covers` graph、orphan、duplicate coverage、关键路径。

**前置**：T1-04。

**预计写面**：

- `bin/plan/portfolio_graph.py`
- `bin/plan/bet-ledger.py`
- `tests/test_bet_portfolio_graph.py`
- 本 child Spec、plan、retro。

**验证**：

- implementation-time immutable dependency baseline 保持无 missing ID、无 cycle；
- required KR 零覆盖失败；
- failed BET 无 replacement 导致覆盖归零时失败；
- critical path 对 fixed fixture 输出确定顺序；
- 不用 BET 数量计算进度。

### 10.4 Child — `BET-Y1Q4-T1-06`

**标题**：Milestone/Vision 派生完成门与 chain-bind v2

**负责**：BET、Milestone、Campaign、Objective、Vision 五级完成谓词。

**前置**：T1-04、T1-05。

**预计写面**：

- `bin/plan/chain_bind.py`
- `bin/plan/chain-bind-check.py`
- `bin/plan/bet-ledger.py`
- `tests/test_chain_bind.py`
- `tests/test_bet_portfolio_completion.py`
- 本 child Spec、plan、retro。

**验证**：

- all BET done + KR unproven 必须失败；
- infrastructure `delivery_accepted` 不得推进 value KR；
- replacement coverage 可以替代 failed leaf；
- 12 周窗口少一周即 Vision close 失败；
- human final verdict 缺失即 Vision close 失败。

### 10.5 Child — `BET-Y1Q4-T1-07`

**标题**：现有 Ledger 全量 BET 只读组合分类与分批迁移合同

**负责**：生成分类 manifest；定义每批迁移边界；不自动改变业务状态。

**前置**：T1-04。

**预计写面**：

- `bin/plan/portfolio_migration.py`
- `tests/test_bet_portfolio_migration.py`
- `docs/generated/bet-portfolio-migration-manifest.yaml`
- 本 child Spec、plan、retro。

**验证**：

- manifest 覆盖 implementation-time Ledger 的全部 BET，且每项恰好一次；
- 所有历史 terminal BET 只引用、不重写；
- 所有 non-terminal BET 均分类为 continue/merge/defer/stop；
- implementation-time immutable Ledger 中所有 blocked BET 均保留 blocker，不自动解阻；
- `--dry-run` 工作树零变更；
- `--apply` 缺明确批次授权时拒绝。

### 10.6 Child — `BET-Y1Q4-T1-08`

**标题**：Goals/Markdown/control projection 生成与漂移门

**负责**：Ledger→goals/current、Markdown、control JSON 单向投影。

**前置**：T1-04、T1-07。

**预计写面**：

- `bin/plan/portfolio_projection.py`
- `bin/plan/bet-ledger.py`
- `tests/test_bet_portfolio_projection.py`
- `.omo/goals/current.yaml`
- `docs/plans/3Y-BET-PORTFOLIO.md`
- `.omo/_control/portfolio-status.json`
- 本 child Spec、plan、retro。

其中两份 `.omo` 路径是 broker-owned output；child 实现只提交 broker request
和验证结果，不直接写受治理状态文件。

**验证**：

- 三份投影 source digest 相同；
- `--check` 检出任意一字节 drift；
- 投影中不出现独立可写状态；
- 生成两次 byte-identical；
- projection 不读取 runtime dirty worktree 推测完成状态。

### 10.7 Child — `BET-Y1Q4-T8-05`

**标题**：Cockpit Portfolio 只读组合视图

**负责**：Objective、KR、Milestone、critical path、blocker 的单入口展示。

**前置**：T1-05、T1-08。

**子仓优先预计写面**：

- `projects/cockpit/src/cockpit/commands/portfolio.py`
- Cockpit 对应测试和接口声明；
- root 只在 child merge/CI/main 后更新 `projects/cockpit` gitlink；
- 本 child Spec、plan、retro。

**验证**：

- CLI 与 control projection digest 一致；
- 无 projection 时明确显示 unavailable，不回退到猜测；
- 无写 Ledger/OMO/Goals 能力；
- root pointer child-main reachable；
- 关键路径和 blocker 可由普通用户理解。

### 10.8 Child — `BET-Y1Q4-T1-09`

**标题**：Portfolio v2 dogfood canary 与 W0 收口

**负责**：选择一个 value-exempt 机制 BET，完整验证新链；关闭 W0，而不是启动
W1–W6。

**前置**：T1-04、T1-05、T1-06、T1-07、T1-08、T8-05。

**预计写面**：

- 一个专用 canary fixture/report；
- Parent/child retros；
- Ledger 仅允许 W0 parent/child completion transitions；
- 不新增 W1–W6 BET。

**验证链**：

```text
Vision pointer
→ Objective/KR
→ Campaign/Milestone
→ Child BET
→ accepted Spec
→ WorkPacket
→ WorkflowRun
→ verify/closeout
→ completion matrix
→ retro
→ KR evidence
→ Milestone derived=met
→ Cockpit/CLI digest parity
```

**负例**：删除任一 binding、KR evidence、retro、run identity 或 projection digest，
closeout/portfolio gate 必须失败。

## 11. W0 依赖与波次

```text
Bootstrap（只绑定，不实施）
  Parent T1-03 + seven child Specs/WorkPackets
                 │
Wave A1          T1-04 schema/validator
                 │
Wave A2     ┌────┴─────────┐
            T1-05 graph    T1-07 migration manifest
               │                  │
Wave B     T1-06 gates       T1-08 projections
               └──────────┬───────┘
Wave C                    T8-05 Cockpit view
                              │
Wave D                    T1-09 dogfood
                              │
                         Parent closeout
```

并发规则：

- Wave A2 最多两个 writer，写面必须不重叠；
- Wave B 最多两个 writer；`bin/plan/bet-ledger.py` 的 merge 由 coordinator 串行；
- Cockpit child-first，root gitlink last；
- Ledger、completion、retro 和 root pointer 由 coordinator 串行；
- observer/reviewer 严格只读，不持 writer lock；
- 任一 writer 出现 scope drift，停止整波，不自动扩大授权。

## 12. W0 里程碑

| Milestone | 包含 | 出口门 | 目标周期 |
|---|---|---|---:|
| MS-W0-CONTRACT | T1-04/T1-05/T1-06 | v1兼容、v2验证、覆盖和完成门全绿 | 4–6工作日 |
| MS-W0-MIGRATION | T1-07/T1-08 | 全量 current-Ledger manifest、三投影确定性、零状态误改 | 3–5工作日 |
| MS-W0-PRODUCT | T8-05 | Cockpit只读单入口、child/root交付完整 | 2–4工作日 |
| MS-W0-CANARY | T1-09 | 完整链路和全部负例通过 | 2–3工作日 |

总 appetite：11–18 个有效工作日，不包含外部 CI 等待窗口。若超过 20 个工作日仍
无法完成，触发 scope review，只保留 Contract + Gate，Cockpit 视图延后，但不得
牺牲唯一 SSOT 和 Vision completion predicate。

## 13. 验证策略

### 13.1 单元测试

- v1/v2 parsing；
- ID、枚举、引用、metric shape；
- dependency cycle/missing ref；
- KR coverage；
- replacement coverage；
- derived state；
- projection determinism；
- fail-closed negative fixtures。

### 13.2 集成测试

- current Ledger 全量只读 parse；
- WorkPacket 编译兼容；
- agent-workflow start/verify/closeout；
- chain-bind complete；
- Ledger→Goals→Control projection；
- Cockpit CLI digest parity；
- child/root gitlink reachability。

### 13.3 迁移不变量

迁移前后必须证明：

```text
all existing BET ids preserved
all existing status preserved
all existing completion/value evidence preserved
all existing accepted_specifications preserved
all existing depends_on preserved unless separately approved
all existing retro refs preserved
```

### 13.4 Gate 顺序

```text
schema lint
→ compatibility tests
→ coverage graph
→ completion negative tests
→ projection drift
→ focused integration
→ full GaC
→ independent review
→ required PR checks
→ merge
→ exact-SHA post-merge replay
```

## 14. 错误处理矩阵

| 错误码 | 场景 | 判定 | 恢复 |
|---|---|---|---|
| `PORTFOLIO_SCHEMA_INVALID` | v2 shape错误 | halt | 修正当前BET/Spec，不自动降级 |
| `OBJECTIVE_REF_MISSING` | BET引用不存在Objective | halt | 创建合法目标或撤回BET |
| `KR_REF_MISSING` | BET引用不存在KR | halt | 修正引用 |
| `REQUIRED_KR_UNCOVERED` | 必需KR零覆盖 | halt | 增加BET/replacement或重审KR |
| `DEPENDENCY_CYCLE` | depends_on成环 | halt | 拆除错误前置 |
| `MILESTONE_FALSE_CLOSE` | BET done但KR未证明 | halt | 保持Milestone未完成 |
| `VISION_WINDOW_INCOMPLETE` | 少于12周 | halt | 继续观察，不补合成样本 |
| `LEGACY_TERMINAL_INCOMPLETE` | 历史done缺matrix | warn | grandfather，不批量伪造证据 |
| `MIGRATION_SCOPE_DRIFT` | 非授权BET发生变化 | halt | 回滚当前批次 |
| `PROJECTION_DRIFT` | 生成物与Ledger不一致 | halt | 从Ledger重新生成 |
| `PORTFOLIO_CONCURRENT_UPDATE` | base digest改变 | retryable halt | 重新读取、重算、重审diff |
| `VALUE_PROXY_REJECTED` | 代理量关闭价值KR | halt | 使用真实outcome证据 |
| `WIP_LIMIT_EXCEEDED` | 超过两个writer | halt | 等待/关闭现有writer |

任何错误都不得自动修改 BET status、completion evidence 或 KR evidence。

## 15. 回滚策略

### 15.1 代码回滚

每个 child 独立 PR。失败只 revert 当前 child，不回滚已有历史 BET 或 outcome。

### 15.2 Schema 回滚

v2 采用 additive schema。关闭 v2 enforcement 后，现有 v1 命令仍可读取 `bets`；
不得通过删除 v2 字段回滚历史证据。

### 15.3 投影回滚

Goals/Markdown/control projection 全部可从 Ledger 重建。回滚只删除/恢复生成物，
不反向写 Ledger。

### 15.4 迁移回滚

每个最多 8 BET 的迁移批次拥有 base digest、before objects 和 semantic diff；只允许
恢复该批次新增的组合字段，不修改 status、binding、completion 或 evidence。

## 16. 十项红队审查

| 攻击 | 风险 | 设计响应 |
|---|---|---|
| 又造一套治理系统 | 高 | 只扩展Ledger/现有CLI，无服务/DB/dispatcher |
| 全量 BET 一次性重写 | 高 | terminal grandfather，nonterminal分批≤8；总量从 implementation-time immutable Ledger 派生 |
| BET done冒充愿景完成 | 高 | KR/Milestone/Vision全部派生且需直接证据 |
| 用PR/CI冒充价值 | 高 | value KR只接受真实signal+human verdict |
| 目标和Ledger双写 | 高 | goals/current变成单向投影 |
| 指标被有害优化 | 高 | baseline、guardrail、cheapest-path review必填 |
| Agent自行完成KR | 高 | proven由validator派生，人类最终裁决 |
| failed BET造成目标暗缺口 | 高 | coverage守恒和replacement强制 |
| Cockpit成为第二writer | 中 | Cockpit严格只读，动作委托canonical CLI/OMO |
| 机制升级挤压产品工作 | 中 | W0有20工作日熔断，完成后治理预算≤30% |

## 17. 明确不做

W0 不做：

- W1–W6 实现；
- W1–W6 全量 BET 批量写入 Ledger；
- 新 Portfolio 服务、数据库、消息总线或 dashboard 项目；
- 新 workflow engine 或 task envelope；
- 全量重写历史 terminal BET；
- 修改任何既有 completion/value evidence；
- 自动改变 candidate/blocked/done 状态；
- 自动给 KR 写 proven；
- 自动合并、重跑、审批或修改现有 PR；
- 运行态、定时器、plist、crontab、服务或用户配置变更；
- 用治理分数、提交数或 BET 数作为最终价值。

## 18. 验收标准

| ID | assertion | evidence_type | verifier |
|---|---|---|---|
| AC-W0-01 | Legacy Ledger remains readable and every existing BET object is semantically unchanged by bootstrap | structured_report | immutable base/current object comparison |
| AC-W0-02 | Every required KR has conserved coverage and the dependency graph has no missing ID or cycle | structured_report | `bet-ledger.py portfolio coverage --json` |
| AC-W0-03 | BET done cannot close a Milestone or Vision without proven KR evidence | negative_test | portfolio completion fixture suite |
| AC-W0-04 | Goals, Markdown and control projections are deterministic, one-way and digest-identical | replay_receipt | projection `--check` plus broker receipt |
| AC-W0-05 | Cockpit exposes the same digest-bound portfolio state without write authority | integration_test | child CLI test plus root pointer canary |
| AC-W0-06 | A value-exempt dogfood run traverses the full chain and every required negative mutation fails closed | canary_report | W0 dogfood immutable-tree report |
| AC-W0-07 | W1-W6 remain absent and no personal-value evidence is created | structural_report | Ledger/object/evidence partition comparison |
| AC-W0-08 | All four W0 Milestones are derived as met before Parent closeout | derived_gate | milestone and chain-bind report |

## 19. 反指标

The following do not measure W0 success:

- raw BET, file, line, rule, command, test, PR, commit or generated-document counts;
- a green CI job without the corresponding contract assertion;
- worker self-report, transport acknowledgement or a clean Git status;
- synthetic, test or unbound `decision_outcome` samples;
- projection freshness presented as source-truth correctness;
- governance score or activity volume without a user-visible product path;
- reducing surface by deleting tests, history or evidence.

## 20. Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|---|---|---|
| 1 | 新 Portfolio service/database/dispatcher vs 扩展 Ledger | 扩展现有 Ledger | 保持唯一机器 SSOT，避免第二状态库或调度面 |
| 2 | Goals 与 Ledger 双写 vs 单向投影 | Ledger 唯一写，Goals 生成 | 消除目标状态漂移 |
| 3 | all-BET-done vs KR/Milestone 派生完成 | 使用派生完成门 | 活动完成不能证明愿景结果 |
| 4 | 一次性历史迁移 vs terminal grandfather | grandfather + 小批次 | 保护历史 evidence 和可审查性 |
| 5 | 三个 vs 四个 W0 Milestone | 四个，包含 Product | T8-05 必须进入 Campaign 完成门 |
| 6 | 任意新 KR 名称 vs 已批准 vocabulary | bootstrap 只用两个既有 KR | 禁止未审议语义扩张 |
| 7 | binding 自动授权 planning vs 分阶段授权 | binding 后停止 | accepted identity 不等于执行权限 |
| 8 | strict total check 立即开启 vs staged | compatibility→单字段修复→strict | 既有 metadata 漂移不能让 T1-04 永久红 |
| 9 | 缺失/冲突证据时推断成功 vs typed halt/unavailable | fail closed | 证据不足不能被归零或补推为通过 |

## 21. Accepted review record

The human principal approved the Documents source at SHA-256
`cbdee89004d0156e262daa63a1c38cfd660c0d5efbf0fce1a8eec8a92027c30b`
and approved the W0 accepted-binding proposal at SHA-256
`26bd1b3df552e693f2ac2684df255436522ff816d7844459523fafe130587100`.

The accepted decision covers Scheme A, the W0 parent plus seven child BET
topology, v1-compatible bootstrap binding, later Portfolio v2 self-binding,
migration invariants, error handling, rollback, and the explicit W1-W6
deferment.

This acceptance authorizes only the repository Spec/BET binding bootstrap.
It does not authorize writing-plans, implementation code, tests, projections,
runtime mutation, W1-W6 materialization, completion transitions, or value
evidence.

This accepted Spec establishes binding identity only. It does not authorize
writing-plans or implementation. Writing-plans requires a separate
post-binding authorization.

## 22. Binding boundary

- Parent BET: `BET-Y1Q4-T1-03`.
- Seven child BETs: `BET-Y1Q4-T1-04`, `BET-Y1Q4-T1-05`,
  `BET-Y1Q4-T1-06`, `BET-Y1Q4-T1-07`, `BET-Y1Q4-T1-08`,
  `BET-Y1Q4-T8-05`, and `BET-Y1Q4-T1-09`.
- All eight BETs start as candidate/evaluating with engineering
  `NOT_STARTED`, operational/value `NOT_PROVEN`,
  `value_indicator_policy=false`, and `human_gate=true`.
- The initial `portfolio_binding.schema_state=bootstrap_unenforced` is
  declaration-only until T1-04 implements and verifies the v2 contract.
- No W1-W6 BET is created by this bootstrap.
- Every later phase requires its own fresh workflow and accepted plan.
