# .omo/tasks/ — 任务跟踪系统

> 多 Agent 协同任务管理。每个任务一个 YAML 文件，是当前唯一任务 SSOT。

---

## 目录结构

```
tasks/
├── README.md          ← 本文件
├── active/            ← 当前可执行队列（Agent 正在执行或待执行）
│   └── {task-id}.yaml ← 每个任务一个文件
├── planned/           ← 未来 backlog / 尚未晋升到 active 的任务包
├── done/              ← 已完成任务（自动归档）
└── blocked/           ← 阻塞任务（缺少依赖或等待人类）
```

## 任务文件格式

```yaml
# active/M2.2-operation-levels.yaml
id: M2.2-OPERATION-LEVELS
phase: 2
milestone: M2.2
priority: P0
title: "Define and enforce L0-L3 operation levels"
status: pending                 # candidate | pending | in_progress | review | done | blocked | failed
assigned_to: null               # agent:name | human | null
dispatch_id: null
run_ref: null
approval_ref: null
review_ref: null
knowledge_refs: []
handoff_refs: []
source_docs:
  - ".omo/plans/phase2-task-specs-v2.md"
depends_on:
  - M2.0-TASK-SYSTEM-SEED
risk_level: L2
allowed_operation_level: L2
human_approval_required: true
entry_gate:
  - "M2.0 governance close accepted or waived"
evidence_required:
  - "L2 action denied without confirmation"
test_plan:
  - ".omo/tests/README.md#operation-level-tests"
started_at: null
completed_at: null
blocked_by: null
retry_count: 0
```

## 状态流转

```
candidate ──→ pending ──→ in_progress ──→ review ──→ done
                            │               ↑
                            └──→ blocked ───┘ (解除阻塞后)
                │
                └──→ failed (重试后可回到 in_progress)
```

## Canonical task status vs gate facts

- task.status is the canonical truth-plane field.
- `task.status` is the canonical truth-plane field.
- Wave 2 keeps the status enum stable: `candidate | pending | in_progress | review | done | blocked | failed`
- Gate facts are derived from task/run evidence and must not be written back as new `task.status` values.
- `dispatched` / `reclaimed` / `review_ready` / `accepted` are gate facts, not canonical statuses.
- `active/ -> done/` promotion only happens after review evidence, required evidence, no blocking divergence, and a completion summary are all present.

## Agent 使用约定

1. 只从 `active/` 认领任务；不要从旧 `TASK_POOL.md` 或历史计划中直接开工。
2. `tasks/planned/` 只存放 future backlog / not-yet-promoted packet surface，不是执行队列。
3. `active/` 是 current executable queue；planned packet 只有在正式晋升后才进入 `active/`。
4. coordinator 如需评估 planned packet 是否可晋升，先运行 `python3 scripts/omo_worker.py task promote-eval <TASK_ID> --omo-dir .omo`。
5. 真正晋升时运行 `python3 scripts/omo_worker.py task promote-apply <TASK_ID> --promoted-by <ACTOR> --now <ISO8601> --omo-dir .omo`。
6. 如需查看整个 planned queue 的 readiness，而不是单看一个 task，运行 `python3 scripts/omo_worker.py task promotion-readiness --omo-dir .omo`。
7. 如需为 `human_approval_required: true` 的 planned packet 发起 task-specific promotion approval request，运行 `python3 scripts/omo_worker.py task promotion-request-approval <TASK_ID> --requested-by <ACTOR> --now <ISO8601> --omo-dir .omo`。
8. 如需看 request / proposal / granted 的 closure lifecycle，运行 `python3 scripts/omo_worker.py task promotion-approval-status --omo-dir .omo [--task-id <TASK_ID>] [--now <ISO8601>]`。
9. promotion approval 的 mutation 继续走 generic governance：先 `python3 scripts/omo_governance.py approve <PROPOSAL_ID> --approver <ACTOR> --now <ISO8601>`，再 `python3 scripts/omo_governance.py apply <PROPOSAL_ID> --now <ISO8601>`。
10. 如需看所有 task-specific promotion approval artifacts 的 canonical history/index，运行 `python3 scripts/omo_worker.py task promotion-approval-history --omo-dir .omo [--now <ISO8601>]`。
11. 被晋升的 pending packet 必须把 promotion envelope ref 写入 `handoff_refs`；没有该 evidence 的 future-phase pending packet 仍视为非法 backlog 回流。
12. 接任务前：检查同名任务是否已 `in_progress`，避免重复。
13. 开始执行：由 **coordinator 预占 lease**，先更新 `status: in_progress`、`assigned_to`、`started_at`、`dispatch_id`、`run_ref`。
14. 完成实现后：先进入 `review`，补充 `evidence`。
15. 验收通过：更新 `status: done`、`completed_at`，移到 `done/`。
16. 遇到阻塞：更新 `status: blocked`、`blocked_by`、`next_check_at`，移到 `blocked/`。
17. 写入方式：只写自己的任务文件，不修改其他 Agent 的文件。

## 必须遵循的标准

- `.omo/standards/planning-blueprint-delivery-test-standard.md`：任务必须能追溯到 blueprint / phase specs / evidence。
- `.omo/standards/agent-cli-worker-collaboration.md`：外部 worker 的 dispatch / review / reclaim / knowledge handoff 规则。
- `.omo/standards/operation-levels.md`：任务允许的 L0-L3 操作级别与门禁边界。
- `.omo/standards/task-gate-model.md`：Wave 2 canonical status 与 gate facts 的分层边界。
- `.omo/standards/divergence-triage.yaml`：Wave 2 divergence 的 severity / owner / disposition 规则。

## Schema 校验

在 dispatch 或人工修改 active task 之前，先运行：

```bash
scripts/omo task validate --all-active
```

如需只检查 future backlog / planned packet surface，可额外运行：

```bash
python3 scripts/omo_worker.py task validate --all-planned
```

当前 schema gate 会校验：

- active task 必须具备 `source_docs / entry_gate / evidence_required / test_plan`
- 如声明 `deliverables`，必须是明确可写的输出列表
- L2/L3 或需要人工批准的任务必须具备 `approval_ref`
- `in_progress` / `review` 状态下的 `dispatch_id / run_ref / review_ref / started_at` 等链路字段必须完整

planned -> active promotion 补充约定：

- `promote-eval` 只做 eligibility 检查，不移动任务。
- `promote-apply` 会写 promotion envelope、把该 envelope ref 追加到 task 的 `handoff_refs`，然后再执行 queue move。
- `promotion-request-approval` 会把 planned task 的 `approval_ref` 从 shared backlog note 切到 task-specific requested approval YAML，并同时写 governance proposal。
- `promotion-approval-status` 是 promotion approval 的 canonical read-side lifecycle surface，用来查看 request / proposal / granted 当前走到哪一步。
- `promotion-approval-history` 是 promotion approval artifacts 的 canonical history/index surface，用来查看所有 task-specific approval records，而不是只看当前 closure state。
- future-phase pending packet 只有带 promotion envelope ref 时，才允许出现在 `tasks/active/`。
- 对 `human_approval_required: true` 的 planned packet，`approval_ref` 必须指向 task-specific promotion approval YAML。
- 像 `future-active-l2l3-pending-approval-*.md` 这样的 shared backlog-presence note 不授权 promotion；非 YAML、错 scope、错 task、或仍处于 `approval_status: requested` 的 ref 一律按 `approval_invalid` fail closed。

### 外部 Agent CLI Worker 补充规则

- `codebuddy`、`reasonix` 等外部 CLI worker 必须先在 `.omo/workers/registry.yaml` 注册。
- 外部 worker 只能在 coordinator 准备好的 task envelope / prompt contract 下执行。
- 外部 worker 执行前，由 **coordinator 预占 lease** 并写入 `dispatch_id` / `run_ref`。
- 外部 worker 默认最高只执行到 **L1**；L2/L3 只能准备，不可自行放行。
- 外部 worker 可将任务推进到 `review`，但 **不得自行标记 `done`**。
- `.omo/state/system.yaml`、`.omo/goals/current.yaml`、`convergence.yaml` 仅由 coordinator 收口。
- 详细规范见 `.omo/standards/agent-cli-worker-collaboration.md`。

## 当前执行口径

Phase 9 已完成。Phase 10 已完成。Phase 11 已完成。Phase 12 已完成。Phase 13 已完成。Phase 14 已完成。Phase 15 仍处于 pre-planning gate，不得自动创建 active task。

当前规则：

1. `spaces/` 必须先变成真实 workspace 对象，再继续做 identity / authorization / rollout
2. Phase 9 Wave 3 只能在 Wave 2 的 registry + manifest 基线通过并形成 closeout 后启动；该包已完成并归档
3. Phase 9 Wave 4 只能在 identity/admission contract 落地后启动；该包也已完成并归档
4. `.omo/tasks/active/` 仍是唯一 active queue；`.omo/tasks/planned/` 是未来 backlog / not-yet-promoted packet surface
5. 当前 `tasks/active/` 只保留已获授权的执行包；future backlog 已迁入 `tasks/planned/`，Phase 11-14 执行包均已归档到 `tasks/done/`，包括 `P11-W4-EVOLUTION-BRIDGE`、`P12-W4-AUDIT-HANDOFF`、`P13-W4-SELF-HEALING-REHEARSAL`，最新为 `P14-W4-ECOSYSTEM-PREVIEW`
