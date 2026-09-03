---
status: accepted
lifecycle: spec
owner: resident
created: 2026-08-25
last-reviewed: 2026-08-25
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-12
type: ssot
last_updated: 2026-09-03
---

# Resident 事件源接入 workflow 生命周期 (消费端补全 + 重放)

> 日期：2026-08-25
> 状态：accepted
> BET：BET-Y1Q3-T10-12
> 上游：BET-Y1Q3-T6-14 复盘 §8（docs/reports/2026-08-24-resident-system-deep-review.md）

## 背景与问题

T6-14 复盘实测确认 resident 体系「接线完整、价值未兑现」，idle 空转 9.25h。根因是**消费端事件覆盖不足 + 事件源未自动化**：

- **74% 事件落 placeholder**：`workflow-mesh/events.jsonl` 现有 2208 条事件、11 种 event_type，而
  `resident-routes.yaml` 只路由 8 种（WorkflowClosed/WorkflowSucceeded/PersonalSignal/WorkflowFailed/
  StepFailed/StepTimeout/ExecutionRequested/WorkPacketDispatched）。未路由的 1635 条（74%）：
  WorkflowRequested(730) / WorkflowAdmitted(295) / StepStarted(295) / StepDispatched(295) /
  EvidenceRecorded(20) 全部落入 `_handler_placeholder`（仅记日志），daemon 每 2min 空转。
- **事件源未自动化**：`omo.resident.ingest`（event-ingest-adapter，把 events.jsonl 发布到
  bus_foundation + 灌入 event ledger）未接 cron，只能手动触发；`install-resident-cron.sh` 无 ingest 行。
- **角色分片与路由表不一致**：`roles.py` 中 monitor/heartbeat 角色的 topic_filter
  （system.health/governance:gate_failed/alert/heartbeat/system.alive）在 workflow-mesh 中不存在，
  这两个角色 cron 每 2min 跑但可消费事件为 0，是纯空转。

复盘 §8 原文：「事件源接入自动 workflow 生命周期（解决 idle 空转）」是本轮 follow-up。

## 目标

让 workflow 生命周期事件被 resident 消费端真正消化（不再 placeholder），并让事件源自动化接入：

1. **路由补全**：把 5 种未路由事件映射到知识沉淀 handler（safe），消除 74% 事件 placeholder。
2. **sediment 事件集合扩展**：按事件语义分拣（生命周期/证据类 → 知识草稿），按 run_id 聚合去重，
   避免模板草稿爆炸（现有唯一 run_id=730，聚合后草稿量受控）。
3. **角色分片同步**：sediment 角色 topic_filter 补全 5 种事件，使 `daemon --role sediment` 真正消费。
4. **事件源接 cron**：`install-resident-cron.sh` 增加 ingest 定时行，事件源自动接入
   （bus 发布 + ledger 灌入）。
5. **重放验证**：回退水位重放全部 2208 条历史事件，验证全链路路由（无 placeholder）与草稿产出符合预期。

## 非目标

- 不引入 LLM 调用（保持确定性事件驱动，草稿仍为模板占位 + 元数据，五问提炼留运营 agent/人工）。
- 不改五类角色运行时框架（daemon tick/byte-offset 水位机制不动）。
- 不接 monitor/heartbeat 角色的 workflow-mesh 事件（其渠道事件源未接入，属另一输入渠道，
  不在本 BET 范围）。
- 不解决 sediment 草稿「模板化」本身（那是知识提炼问题，另开 BET）。

## 设计

### 1. resident-routes.yaml 路由补全

追加 5 条规则（全部 safe: true，只写知识草稿，非破坏性）：

| event_type | topic | action | safe |
|------------|-------|--------|------|
| WorkflowRequested | mesh:workflow:requested | knowledge_sediment | true |
| WorkflowAdmitted | mesh:workflow:started | knowledge_sediment | true |
| StepStarted | mesh:step:started | knowledge_sediment | true |
| StepDispatched | mesh:workflow:started | knowledge_sediment | true |
| EvidenceRecorded | mesh:workflow:evidence | knowledge_sediment | true |

### 2. sediment.py 事件集合扩展

```python
SUCCESS_EVENTS  = frozenset({"WorkflowSucceeded", "WorkflowClosed", "WorkflowAdmitted"})
LIFECYCLE_EVENTS = frozenset({"WorkflowRequested", "StepStarted", "StepDispatched"})
EVIDENCE_EVENTS = frozenset({"EvidenceRecorded"})
```

- `_sediment_dispatch()` 扩展：SUCCESS → runs 草稿；FAILURE → failures 草稿；
  SIGNAL → signals 草稿；**LIFECYCLE → runs 草稿（按 run_id 聚合，幂等：文件已存在则跳过，
  避免同 run 多事件重复写盘）**；**EVIDENCE → evidence 草稿（`sediment/evidence/{slug}.md`，
  带 event_id 溯源）**。
- 草稿 title 区分 kind（success=运行复盘 / lifecycle=生命周期 / evidence=证据），frontmatter
  统一保留 event_type / run_id / event_id / occurred_at / producer。
- 聚合策略依赖既有 `_safe_slug(run_id)`（同一 run 多事件 → 同文件），加 `exists → skip` 幂等。

### 3. roles.py 角色分片同步

sediment 角色 topic_filter 由 `[WorkflowClosed, WorkflowSucceeded, PersonalSignal]` 扩展为：
```
["WorkflowClosed", "WorkflowSucceeded", "PersonalSignal",
 "WorkflowRequested", "WorkflowAdmitted", "StepStarted", "StepDispatched", "EvidenceRecorded"]
```
（decision/execute 角色不变；monitor/heartbeat 不变。）

### 4. install-resident-cron.sh 增加 ingest 行

```bash
CRON_INGEST="*/5 * * * * cd ${WORKSPACE} && PYTHONPATH=${PYTHONPATH} ${PYTHON_BIN} -m omo.cli resident ingest --ledger ${WORKSPACE}/runtime/omo/event-ledger.sqlite3 >> ${WORKSPACE}/.omo/_delivery/event-ingest/cron.log 2>&1"
```
沿用既有 python3.11+ 探测（规避 crond PATH python3=3.9 无 datetime.UTC 陷阱）。幂等：ingest
用 `workflow_mesh_last_event_id` 水位，重复执行不重发。

### 5. 数据流

```
workflow-mesh/events.jsonl (2208, 11 种)
   ├─ ingest (cron, 5min) ──> bus_foundation 主题发布 + event-ledger 灌入
   └─ daemon --role sediment (cron, 2min)  byte-offset 增量读
        ├─ SUCCESS/LIFECYCLE  → sediment/runs/*.md  (按 run_id 聚合)
        ├─ FAILURE           → sediment/failures/*.md
        ├─ SIGNAL            → sediment/signals/*.md
        └─ EVIDENCE          → sediment/evidence/*.md
```

## 接口

- `resident-routes.yaml`（追加 5 条规则）
- `omo.resident.sediment`（SUCCESS/LIFECYCLE/EVIDENCE 事件集合 + dispatch 分支 + 幂等写盘）
- `omo.resident.roles`（sediment topic_filter 扩展）
- `install-resident-cron.sh`（新增 CRON_INGEST 行）

## 测试

- sediment 单元测试：给定 fixture 事件（LIFECYCLE 同 run 多事件 / EVIDENCE / 幂等跳过），
  断言草稿生成路径、run 聚合、exists 跳过、evidence frontmatter。
- roles 单元测试：sediment topic_filter 含 8 种事件。
- 集成验证（重放）：回退 `resident-sediment.json` byte_offset → 0，`daemon --once --role sediment`
  重放 2208 条，断言路由后无 placeholder 落盘（草稿全部写对应 kind 目录）、processed=2208、
  runs/failures/evidence 计数符合预期。

## 验收 (done_when)

1. `resident-routes.yaml` 含 5 条新规则且语法校验通过（fail-closed 加载）。
2. `sediment.py` 含 LIFECYCLE_EVENTS / EVIDENCE_EVENTS，dispatch 覆盖 5 类事件且按 run 幂等。
3. `roles.py` sediment topic_filter 含 8 种事件。
4. `install-resident-cron.sh` 含 ingest 行且语法校验通过。
5. 新增单元测试全绿 + 重放验证：回退水位重放 2208 条，processed=2208，无 placeholder 落盘。

## 关联

- BET-Y1Q3-T6-14（复盘，已 done）· ADR-0396（DigitalAgent）· `resident-routes.yaml`
- 演进候选（不在本 BET）：sediment 草稿知识提炼（LLM 路径）、monitor/heartbeat 渠道事件源接入、
  alert webhook 外发（Task #77/#78）。
