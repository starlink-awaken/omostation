# projects/omo Demo Active Cleanup Execution Packet

**日期**: 2026-06-13  
**用途**: 交给其他 agent 执行的精确任务包  
**当前状态**: 主要动作已执行，本文保留 reviewer 可复盘的执行边界。
**前置输入**:

- `2026-06-13-projects-omo-c-class-decision-packet.md`
- `2026-06-13-projects-omo-demo-active-archive-plan.md`
- `2026-06-13-projects-omo-untracked-inventory.md`

## 1. 本轮只允许做的事

只处理这 5 个 demo active task：

- `TASK-D1-CHILD1`
- `TASK-D1-CHILD2`
- `TASK-D2-RETRY`
- `TASK-D2-SUCCESS`
- `TASK-FEC5E158`

目标：

- 把它们从 `tasks/active/` 当前活跃面移出
- 不破坏追溯
- 不篡改 `goals/current.yaml`
- 不修改任何 OPC P5/P6/P7 gate 结论

## 2. 已执行文件面

### A. 任务文件迁移

已把这 5 个文件从：

- `.omo/tasks/active/`

迁到：

- `.omo/tasks/archive/demo-phase29/`

### B. 状态面同步

已同步处理：

- `.omo/state/system.yaml`

已收口的字段：

- `task_gate_summary`
- `promotion_blockers`
- `next_active_tasks`

执行前残留证据：

- `Current active queue from .omo/tasks/active/ (5 tasks)`
- 后面紧跟这 5 个 task id

### C. demo 脚本定位

已处理：

- `.omo/d2_demo.py`

实际落地做法：

1. 一并归档
2. 明确不再作为主线入口

### D. 测试面

至少检查：

- `tests/test_omo_automation.py`

当前 reviewer 仍需关注的断言点：

- `Current active queue from .omo/tasks/active/ (5 tasks)`  
  位置：`tests/test_omo_automation.py:1164`

## 3. 禁止做的事

- 禁止删除 `.omo/workers/runs/*`
- 禁止修改 `goals/current.yaml`
- 禁止把 historical artifact 说成 runtime-state
- 禁止只改文档不改状态面
- 禁止只改状态面不处理测试

## 4. 最小验证结果

已完成并可复核：

1. `.omo/tasks/active/` 不再包含这 5 个 demo task
2. `.omo/state/system.yaml` 不再列出 active count=5 和这 5 个 task
3. `tests/test_omo_automation.py` 相关断言需要继续做定向验证
4. `goals/current.yaml` 未被修改

## 5. Reviewer 红线

- 不把“目录语义保留”偷换成“具体 demo task 也必须留 active”
- 不把“追溯要保留”偷换成“所有残留都不能动”
- 不把 untracked 降少说成系统 clean
- 不得顺手清理无关 artifacts

## 6. 完成定义

当前执行面已经满足以下条件，reviewer 复验按此核对：

- 5 个 demo active task 已迁移或归档
- `.omo/state/system.yaml` 已同步收口
- `.omo/d2_demo.py` 已定性并落地处理
- 相关测试已做定向验证或存在明确剩余项
- closeout 文档链保持一致
