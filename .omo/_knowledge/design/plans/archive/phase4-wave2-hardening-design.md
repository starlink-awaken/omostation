# Phase 4 Wave 2 hardening design

> 日期: 2026-05-31  
> 范围: `.omo` 在 Wave 1 worker ops baseline 之后的治理固化  
> 基线: `dispatch/status/reclaim/auto-gate` 已落地，Wave 1 已收口

## Goal

Wave 2 的目标不是继续堆更多 worker 功能，而是把 Wave 1 的操作能力固化成更稳定的治理 operating model：

1. 让 task / dispatch / reclaim / review / done 的流转进入正式 gate 约束。
2. 让 worker 协作从“能看到当前状态”升级为“能沉淀周期性运行指标”。
3. 让 handoff / review / approval / acceptance 形成统一证据链。
4. 让 divergence flags 从“发现异常”升级为“可分级、可归属、可处置”。

## Why requirements and tasks must be separated

Wave 2 是治理固化，不是单纯功能扩展。  
如果不区分 **需求（what must be true）** 和 **任务（what we do next）**，就会出现三类漂移：

1. 把临时实现方案误当长期规则；
2. 把任务完成误当机制完成；
3. 把四平面里的事实、快照、知识、运行记录混写成多个影子 SSOT。

因此本设计强制分成五层：

1. **Requirements**：必须成立的治理结果
2. **Policies**：约束这些结果的规则
3. **Mechanisms**：落地这些规则的实现载体
4. **Tasks**：Wave 2 要执行的工作项
5. **Milestone exit**：什么条件下 Wave 2 才算完成

## Problem statement

Wave 1 解决了可执行性问题，但仍有四个明显缺口：

1. **生命周期缺口**：当前任务归档仍偏人工，没有正式 promotion gate 去判定何时允许 `active -> done`。
2. **观测缺口**：`scripts/omo worker status` 是即时视图，但没有历史指标与趋势基线。
3. **交接链缺口**：checkpoint / reclaim / review / acceptance 已存在，但仍分散在多个文件里，复盘时需要人工串联。
4. **差异治理缺口**：`divergence_flags` 里已有真实问题信号，但还缺 severity、owner、disposition，长期会稀释可用性。

## Approaches considered

### Approach A — Metrics first

先把 `worker status` 做成 utilization ledger，再回头补生命周期和 divergence 治理。

**优点**：最快看到协作效率数据。  
**缺点**：如果生命周期和差异治理没先固化，指标会建立在不稳定的状态模型上。

### Approach B — Gate first

先固化 lifecycle gate + divergence triage，再做观测和 handoff index。

**优点**：最能控制 `.omo` 漂移。  
**缺点**：短期内使用者感知提升不如 metrics 直接。

### Approach C — Balanced package（推荐）

分成 4 个互相支撑的工作项，在同一 wave 内完成最小闭环：

1. lifecycle gate hardening
2. divergence triage
3. worker utilization baseline
4. handoff index

**为什么推荐**：Wave 2 的本质不是单点优化，而是把 Wave 1 变成长期可经营的默认底座。先做 gate + triage 保证不漂移，再用 utilization + handoff index 让机制进入可量化、可审计状态。

## Scope

### In scope

- 定义正式的 worker/task gate 与 promotion 条件
- 为 divergence flags 增加分级、归属、处置策略
- 为 worker 协作生成周期性 utilization baseline
- 为 task/dispatch 证据链生成统一 handoff index
- 把以上内容接入 `.omo` 的 control / truth / knowledge / delivery 四平面

### Out of scope

- 新增更多外部 worker 类型
- 扩大 worker 写权限范围
- 引入新的治理顶层目录
- 改写 Phase 3 acceptance runner 的职责边界
- 在 Wave 2 内重写整个 task schema

## Requirements

### R1. Canonical task status remains stable

Wave 2 **不引入新的 `task.status` 枚举**。  
truth 层继续沿用现有 task status 模型；`dispatched / reclaimed / review_ready / accepted` 在 Wave 2 中都视为 **gate facts**，不是新的 task status。

### R2. Promotion to done must be gate-driven

任务能否从 `active/` 归档到 `done/`，必须由显式 gate 判定，而不是纯人工口头判断。

### R3. Divergence must be triaged, not only observed

系统不仅要能算出当前 divergence，还要能给 divergence 指定：

- severity
- owner
- disposition

### R4. Handoff evidence must have a single chase path

任一 task 的 dispatch → checkpoint → reclaim → review → acceptance 证据链，必须可以通过单入口追踪。

### R5. Worker operations need a periodic baseline

Wave 2 结束前，必须能输出一版周期性 worker utilization baseline，用于观察 dispatch/reclaim/completion 趋势。

## Policies

### P1. Status vs gate separation

- `task.status` 是 truth SSOT
- `dispatched / reclaimed / review_ready / accepted` 是 derived gate facts
- Wave 2 不允许把 gate facts 直接写成新的 status enum

### P2. Promotion policy

只有同时满足以下条件，task 才允许被 promoted：

1. truth 里 task 字段完整
2. delivery 里 review/evidence 链完整
3. gate 检查无阻断级 divergence
4. completion summary 已写入

### P3. Divergence policy

- control 层保留**当前观测到的 divergence snapshot**
- truth 层保留**triage policy / registry**
- triage metadata 不直接写回 `state/system.yaml` 的观测列表

### P4. Plane ownership policy

- **Truth**：task fields、gate facts、triage registry
- **Delivery**：dispatch/reclaim/review artifacts、handoff index、utilization reports
- **Control**：聚合状态、gate summary、当前 divergence snapshot
- **Knowledge**：设计、SOP、复盘；只引用 truth/delivery，不镜像它们

## Artifact ownership matrix

| Item | Type | Plane | SSOT/Derived | Writer | Verification |
|---|---|---|---|---|---|
| `task.status` | canonical fact | truth | SSOT | coordinator / task tooling | schema + task tests |
| gate facts (`dispatched`, `reclaimed`, `review_ready`, `accepted`) | lifecycle facts | truth | derived facts | sync / worker tooling | automation tests |
| divergence snapshot | state snapshot | control | derived | sync script | state consistency tests |
| divergence triage registry | policy registry | truth | SSOT | coordinator | consistency tests |
| handoff index | evidence index | delivery | derived | generator script | delivery tests |
| utilization baseline | operating report | delivery | derived | aggregator script | regression/report tests |

## Mechanisms

### M1. Lifecycle gate hardening

Wave 2 引入的是 **gate model**，不是新 status model。

推荐映射：

- `task.status=pending|in_progress|review|done|blocked|failed` 继续存在
- gate facts 通过已有字段和派生规则生成：
  - `dispatched`: `dispatch_id + run_ref + assigned_to`
  - `reclaimed`: reclaim reason + successor linkage
  - `review_ready`: review artifact ready
  - `accepted`: evidence_required satisfied and no blocking divergence

实施上优先复用现有 YAML 字段与 `scripts/sync_omo_state.py`，避免在 Wave 2 扩大 schema 变更面。

### M2. Divergence triage registry

新增 truth-owned triage registry，对高频 divergence pattern 建立处置语义：

- `severity`: `critical | high | medium | low`
- `owner`: `control | truth | delivery | knowledge`
- `disposition`: `must_fix | accepted_legacy | monitor`

Wave 2 首批覆盖：

- `orphaned_tasks:*`
- `active_task_missing_run_ref:*`
- `active_task_missing_review_ref:*`

### M3. Worker utilization baseline

基于 `workers/runs/` 与 task YAML 生成 delivery-owned 周期性 summary：

- 周期 dispatch 数
- 周期 reclaim 数 / reclaim 率
- 每个 worker 的 completion / review completion 数
- 平均 handoff 数

Wave 2 不引入数据库；先用 summary artifact 固化经营视图。

### M4. Handoff index

为每个 active/done task 生成 delivery-owned handoff index，单入口链接：

- dispatch envelope / prompt
- checkpoint refs
- reclaim note
- review note
- acceptance / completion summary refs

这个 index 只做“索引和追踪”，不复制原文内容，不变成新的 SSOT。

## Data flow

1. task 进入 `tasks/active/`
2. dispatch/reclaim/review 持续写 `workers/runs/`
3. sync 脚本生成 gate facts 与 divergence snapshot
4. triage registry 对 divergence pattern 提供解释层
5. handoff index 汇总 task 当前证据链
6. utilization baseline 聚合 delivery 运行指标
7. gate 满足后 task 归档到 `tasks/done/`
8. control 面刷新 `goals/current.yaml` 与 `state/system.yaml`

## Error handling

- 缺 `run_ref` / `review_ref`：进入 divergence snapshot，不允许 promotion
- reclaim 无 successor linkage：视为高优先级 gate failure
- handoff index 发现断链：保留已有 evidence，但阻止任务被标记为 accepted/done
- utilization 聚合失败：不影响执行流，但必须生成 delivery warning summary

## Wave 2 tasks

### T1. `P4-W2-LIFECYCLE-GATE-HARDENING`

交付内容：

- 定义 gate facts 与 canonical status 的映射
- 把 promotion rules 接入 sync / consistency 检查
- 明确 active -> done 的归档前置条件

对应需求：R1, R2  
对应策略：P1, P2  
对应机制：M1

### T2. `P4-W2-DIVERGENCE-TRIAGE`

交付内容：

- 建立 truth-owned triage registry
- 对核心 divergence patterns 给出 severity / owner / disposition
- 形成 snapshot + triage 的 join 视图

对应需求：R3  
对应策略：P3, P4  
对应机制：M2

### T3. `P4-W2-WORKER-UTILIZATION-BASELINE`

交付内容：

- 输出第一版 delivery-owned utilization summary
- 固定最小指标集与周期
- 把指标纳入 phase review / retrospective 输入

对应需求：R5  
对应策略：P4  
对应机制：M3

### T4. `P4-W2-HANDOFF-INDEX`

交付内容：

- 为 task/dispatch 链生成 handoff index
- 让 review / reclaim / acceptance 证据单入口可追
- 保持索引引用式，不复制原文

对应需求：R4  
对应策略：P4  
对应机制：M4

## Traceability table

| Requirement | Policies | Mechanisms | Tasks | Verification |
|---|---|---|---|---|
| R1 | P1 | M1 | T1 | automation + schema consistency |
| R2 | P2 | M1 | T1 | docs/state + promotion tests |
| R3 | P3, P4 | M2 | T2 | consistency + state alignment tests |
| R4 | P4 | M4 | T4 | handoff index tests |
| R5 | P4 | M3 | T3 | summary/report tests |

## Testing and verification

Wave 2 的验证分三层：

1. **机制测试**
   - `.omo/tests/test_omo_automation.py`
   - `.omo/tests/test_worker_mechanism_consistency.py`
2. **文档/状态测试**
   - 新增或扩展 phase4 wave2 docs/state consistency tests
3. **回归基线**
   - `python3 scripts/phase3_acceptance.py --write-report`

## Wave 2 milestone exit

Wave 2 只有在以下条件全部满足时才算完成：

1. canonical task status 与 gate facts 的边界写清并被自动校验
2. 核心 divergence patterns 已完成 triage，并有稳定 owner/disposition
3. 第一版周期性 worker utilization baseline 已输出
4. handoff index 已覆盖 Wave 2 范围内 task
5. 四平面入口与底层 SSOT/运行记录保持一致
