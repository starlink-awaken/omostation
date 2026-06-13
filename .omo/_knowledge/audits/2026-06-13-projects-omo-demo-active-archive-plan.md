# projects/omo Demo Active Tasks Archive Plan

**日期**: 2026-06-13  
**范围**: `projects/omo/.omo/tasks/active/` 下 5 个 Phase 29 demo 实例文件  
**目标**: 在不破坏运行语义与追溯链的前提下，把 demo active task 从当前 active 面移出。  
**当前状态**: 已执行，本文保留为方案与执行结果的对照记录。

## 1. 目标文件

- `.omo/tasks/active/TASK-D1-CHILD1.yaml`
- `.omo/tasks/active/TASK-D1-CHILD2.yaml`
- `.omo/tasks/active/TASK-D2-RETRY.yaml`
- `.omo/tasks/active/TASK-D2-SUCCESS.yaml`
- `.omo/tasks/active/TASK-FEC5E158.yaml`

## 2. 现状判断

这 5 个文件已经在 `2026-06-13-projects-omo-c-class-decision-packet.md` 中被归为 `historical-artifact`，依据包括：

- 文件内容明确写 `demo` / `lifecycle test`
- 全部带 `phase: 29`
- 强引用主要来自：
  - `.omo/d2_demo.py`
  - `.omo/workers/runs/*`
  - `.omo/state/system.yaml` 中的 active queue / task_gate_summary

结论：

> 它们不是当前系统必须保留在 `tasks/active/` 的活任务，而是已完成 demo 的实例残留。

## 3. 不可直接做的事

- 不可直接删除 5 个文件
- 不可先删文件、后补文档
- 不可只加 `.gitignore`
- 不可不处理 `.omo/state/system.yaml` 的残留引用

## 4. 迁移目标

已迁移到历史归档位，而不是继续留在 active 面：

- `.omo/tasks/archive/demo-phase29/`

目标文件名保持原名，保留 traceability：

- `.omo/tasks/archive/demo-phase29/TASK-D1-CHILD1.yaml`
- `.omo/tasks/archive/demo-phase29/TASK-D1-CHILD2.yaml`
- `.omo/tasks/archive/demo-phase29/TASK-D2-RETRY.yaml`
- `.omo/tasks/archive/demo-phase29/TASK-D2-SUCCESS.yaml`
- `.omo/tasks/archive/demo-phase29/TASK-FEC5E158.yaml`

## 5. 同步收口点

### A. `.omo/state/system.yaml`

必须同步修正这些区域：

- `task_gate_summary`
- `promotion_blockers`
- `next_active_tasks`

执行前它明确把这 5 个 demo 文件仍当作 active queue：

- `Current active queue from .omo/tasks/active/ (5 tasks)`
- `TASK-D1-CHILD1`
- `TASK-D1-CHILD2`
- `TASK-D2-RETRY`
- `TASK-D2-SUCCESS`
- `TASK-FEC5E158`

执行结果：

- `task_gate_summary: {}`
- `promotion_blockers: {}`
- `next_active_tasks: ['(No active tasks)']`

当前状态面已不再把这 5 个 demo task 说成 active。

### B. `.omo/d2_demo.py`

它仍直接引用：

- `TASK-D2-SUCCESS`
- `TASK-D2-RETRY`
- `.omo/tasks/active/TASK-D2-RETRY.yaml`

执行前需要明确它是：

- 保留为 historical demo script，并把路径切到 archive；或
- 一并归档，不再作为主线脚本入口

执行结果：

- `.omo/d2_demo.py` 已迁移到 `.omo/_archive/demo-phase29/d2_demo.py`
- 不再作为主线脚本入口

### C. `.omo/workers/runs/*`

这里不是收口目标，不做删除；但若 archive 后要保证 review 仍能追溯：

- `task_ref_after` / `task_yaml` 若继续指向原 active 路径，需要决定是否保留原路径 stub
- 或在 archive 方案里显式说明“worker runs 保留原始事实，不做 rewrite”

推荐：

> worker runs 不做历史重写，保留原始事实；archive 方案只迁移 task 文件与当前状态面。

## 6. 执行结果

1. 已新建 archive 目录  
2. 已迁移 5 个 demo task YAML  
3. 已更新 `.omo/state/system.yaml` 中 active queue / summary 残留  
4. 已处理 `.omo/d2_demo.py` 的定位并归档  
5. 定向测试 / 状态生成逻辑继续在 execution packet 中记录  
6. reviewer 现在只需复核 archive 后的语义边界是否一致

## 7. 验收结果

- 已满足: 5 个 demo task 不再出现在当前 active queue
- 已满足: `.omo/state/system.yaml` 不再声明 active count=5 且列出这 5 个 task
- 已满足: worker runs 历史追溯不被破坏
- 已满足: `goals/current.yaml` 保持不动
- 已满足: 没有发生 `planned -> active` 误操作

## 8. 执行入口

给执行 agent 的精确任务包见：

- `2026-06-13-projects-omo-demo-active-execution-packet.md`
