# projects/omo Untracked Inventory (2026-06-13)

**日期**: 2026-06-13  
**范围**: `projects/omo` 子仓 `git status --short --untracked-files=all`  
**用途**: 给 reviewer 和后续 agent 一份精确清单，避免再用模糊口径描述 untracked 脏面。

## 1. 摘要

- untracked 总数: **51**
- tracked modification: `tests/test_opc_p7_cadence_fixes.py`（本轮新增 isolated tests）

分类计数：

| 类别 | 数量 |
|------|------|
| A. 治理证据 / worker runs | 39 |
| B. 历史 demo / probe / 临时 delivery | 6 |
| C. 状态文件 / 活动任务 | 6 |

## 2. A 类 — 治理证据 / worker runs（保留追溯，不做伪 clean）

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
- 不得为了“看起来干净”直接删除
- 后续若归档，必须保留引用链

## 3. B 类 — 历史 demo / probe / 临时 delivery（待 relocate 或 archive）

- `.omo/_delivery/audit-rollout/2026-06-12-5repos.json`
- `.omo/_delivery/gbrain-probe-2026-06-11.md`
- `.omo/_delivery/kairon-probe-2026-06-11.md`
- `.omo/_delivery/metaos-probe-2026-06-11.md`
- `.omo/d2_demo.py`
- `tests/test_opc_p3_thin_binding_demo.py`

治理结论：

- 这 6 个文件不应继续混在 “当前收口成果” 里
- 后续动作是 relocate / archive / remove 三选一
- 未决前统一标记为 historical artifacts

## 4. C 类 — 状态文件 / 活动任务（先定 SSOT，再决定版本管理）

- `.omo/goals/current.yaml`
- `.omo/tasks/active/TASK-D1-CHILD1.yaml`
- `.omo/tasks/active/TASK-D1-CHILD2.yaml`
- `.omo/tasks/active/TASK-D2-RETRY.yaml`
- `.omo/tasks/active/TASK-D2-SUCCESS.yaml`
- `.omo/tasks/active/TASK-FEC5E158.yaml`

治理结论：

- 这 6 个文件影响系统行为，不是普通垃圾文件
- 不得直接靠 `.gitignore` 掩掉
- 必须先回答：它们是不是该由运行时生成、是不是该进版本库、谁是 SSOT
- 当前归类结论见 `2026-06-13-projects-omo-c-class-decision-packet.md`
- 其中 5 个 demo active task 的迁移方案见 `2026-06-13-projects-omo-demo-active-archive-plan.md`

## 5. 后续执行顺序

1. 先处理 C 类：明确 `goals/current.yaml` 与 `tasks/active/*.yaml` 的版本管理规则  
2. 再处理 B 类：把 demo / probe / 临时 delivery 移出主叙事面  
3. A 类最后做 archive 策略，不做破坏性清理
