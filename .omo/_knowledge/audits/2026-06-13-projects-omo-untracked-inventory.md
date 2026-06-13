# projects/omo Untracked Inventory (2026-06-13)

**日期**: 2026-06-13  
**范围**: `projects/omo` 子仓 `git status --short --untracked-files=all`  
**用途**: 给 reviewer 和后续 agent 一份精确清单，避免再用模糊口径描述 untracked 脏面。

## 1. 摘要

- untracked 总数: **1**
- tracked modification:
  - `.gitignore`（新增 runtime-state / local archive ignore 规则）
  - `.omo/state/system.yaml`（sync 后 active queue 已清空）
  - `tests/test_opc_p7_cadence_fixes.py`（本轮新增 isolated tests）

分类计数：

| 类别 | 数量 |
|------|------|
| C. 状态文件 / 当前 SSOT | 1 |

## 2. A 类 — 治理证据 / worker runs（已转本地 ignore）

### A1. promotion records

- `.omo/workers/runs/TASK-D1-CHILD1-promotion-2026-06-11T09-36-30Z.yaml`
- `.omo/workers/runs/TASK-D1-CHILD2-promotion-2026-06-11T09-36-30Z.yaml`
- `.omo/workers/runs/TASK-D2-RETRY-promotion-2026-06-11T09-40-00Z.yaml`
- `.omo/workers/runs/TASK-D2-SUCCESS-promotion-2026-06-11T09-40-00Z.yaml`
- `.omo/workers/runs/TASK-FEC5E158-promotion-2026-06-11T09-35-00Z.yaml`

### A2. task-d2 retry / success worker packets

- `.omo/workers/runs/task-d2-retry-coder-001-20260611-095358-checkpoint.md`
- `.omo/workers/runs/task-d2-retry-coder-001-20260611-095358-dispatch.yaml`
- `.omo/workers/runs/task-d2-retry-coder-001-20260611-095358-envelope.yaml`
- `.omo/workers/runs/task-d2-retry-coder-001-20260611-095358-prompt.md`
- `.omo/workers/runs/task-d2-retry-coder-001-20260611-095358-reclaim.md`
- `.omo/workers/runs/task-d2-retry-coder-001-20260611-095358-review.md`
- `.omo/workers/runs/task-d2-retry-coder-002-20260611-095358-checkpoint.md`
- `.omo/workers/runs/task-d2-retry-coder-002-20260611-095358-dispatch.yaml`
- `.omo/workers/runs/task-d2-retry-coder-002-20260611-095358-envelope.yaml`
- `.omo/workers/runs/task-d2-retry-coder-002-20260611-095358-prompt.md`
- `.omo/workers/runs/task-d2-retry-coder-002-20260611-095358-reclaim.md`
- `.omo/workers/runs/task-d2-retry-coder-002-20260611-095358-review.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-094953-checkpoint.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-094953-envelope.yaml`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-094953-prompt.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-094953-reclaim.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-094953-review.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095117-checkpoint.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095117-envelope.yaml`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095117-prompt.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095117-reclaim.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095117-review.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095307-checkpoint.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095307-dispatch.yaml`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095307-envelope.yaml`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095307-prompt.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095307-reclaim.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095307-review.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095358-checkpoint.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095358-dispatch.yaml`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095358-envelope.yaml`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095358-prompt.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095358-reclaim.md`
- `.omo/workers/runs/task-d2-success-coder-001-20260611-095358-review.md`

治理结论：

- 这 39 个文件属于运行/审批/追溯证据
- 当前通过 `projects/omo/.gitignore` 作为本地运行证据处理，不再污染子仓 untracked 面
- 不得为了“看起来干净”直接删除

## 3. B 类 — 历史 demo / probe / 临时 delivery（已转本地 ignore）

- `.omo/_delivery/audit-rollout/2026-06-12-5repos.json`
- `.omo/_archive/probes/2026-06-11/gbrain-probe-2026-06-11.md`
- `.omo/_archive/probes/2026-06-11/kairon-probe-2026-06-11.md`
- `.omo/_archive/probes/2026-06-11/metaos-probe-2026-06-11.md`
- `.omo/_archive/demo-phase29/d2_demo.py`
- `tests/archive/test_opc_p3_thin_binding_demo.py`

治理结论：

- 这 6 个文件已从主叙事面移走
- 当前通过 `projects/omo/.gitignore` 作为本地保留物处理，不再污染子仓 untracked 面
- 后续是否纳入版本库，另做仓库治理决策

## 4. C 类 — 状态文件 / 当前 SSOT

- `.omo/goals/current.yaml`

治理结论：

- 该文件影响系统行为，不是普通垃圾文件
- 不得直接靠 `.gitignore` 掩掉
- 必须先回答：它是不是该由运行时生成、是不是该进版本库、谁是 SSOT
- 当前归类结论见 `2026-06-13-projects-omo-c-class-decision-packet.md`
- 5 个 demo active task 已不再属于当前 active 面

## 5. D 类 — 已归档的历史 task / script（已转本地 ignore）

- `.omo/tasks/archive/demo-phase29/TASK-D1-CHILD1.yaml`
- `.omo/tasks/archive/demo-phase29/TASK-D1-CHILD2.yaml`
- `.omo/tasks/archive/demo-phase29/TASK-D2-RETRY.yaml`
- `.omo/tasks/archive/demo-phase29/TASK-D2-SUCCESS.yaml`
- `.omo/tasks/archive/demo-phase29/TASK-FEC5E158.yaml`

治理结论：

- 它们已从 active 面退出
- 当前应被视为 historical artifact，而不是 live state
- 当前通过 `projects/omo/.gitignore` 作为本地保留物处理，不再污染子仓 untracked 面

## 6. 后续执行顺序

1. 先处理 C 类：明确 `goals/current.yaml` 的版本管理规则  
2. A 类是否转持久归档目录，后续再定；本轮不做破坏性清理
