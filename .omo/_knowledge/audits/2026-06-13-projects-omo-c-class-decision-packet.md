# projects/omo C-Class Decision Packet

**日期**: 2026-06-13  
**范围**: `projects/omo` 子仓 C 类状态文件  
**目标**: 在不破坏 OMO 运行语义的前提下，明确哪些状态文件应纳入版本管理，哪些应转为运行时/忽略项。

## 1. 待决文件

- `.omo/goals/current.yaml`
- `.omo/_delivery/audit-rollout/2026-06-12-5repos.json`
- `.omo/tasks/active/TASK-D1-CHILD1.yaml`
- `.omo/tasks/active/TASK-D1-CHILD2.yaml`
- `.omo/tasks/active/TASK-D2-RETRY.yaml`
- `.omo/tasks/active/TASK-D2-SUCCESS.yaml`
- `.omo/tasks/active/TASK-FEC5E158.yaml`

## 2. 必答问题

对每个文件必须回答：

1. 它是不是运行时生成物？
2. 它是不是某个已完成 phase / demo 的残留？
3. 当前系统还有没有代码路径把它当 SSOT 读取？
4. 如果删除，会不会破坏测试、审计追溯、或运行时恢复？
5. 如果保留，是否应该进入版本库？

## 3. 可接受结论类型

每个文件只能归到以下三类之一：

- `tracked-ssot`: 应保留并纳入版本管理
- `runtime-state`: 运行时状态，不纳入版本管理，应通过 ignore / relocation 处理
- `historical-artifact`: 历史残留，应 archive 或删除

## 4. 红线

- 不得为了追求 clean 直接删文件
- 不得把 `planned/` 任务推入 `active/`
- 不得修改 `gate_status`
- 不得把运行时状态误报成 SSOT
- 不得在没有引用分析前直接加 `.gitignore`

## 5. 建议执行顺序

1. 搜引用：
   - `rg -n "goals/current.yaml|tasks/active/" src tests .omo -S`
2. 建表：
   - 文件
   - 被谁读取
   - 读取场景
   - 建议归类
   - 风险
3. 只在表完整后，再提删除 / ignore / archive 方案

## 6. Reviewer 验收标准

- 7 个文件全部有归类结论
- 每个结论都有代码/测试/文档证据
- 没有发生破坏性清理
- 没有偷换成“workspace clean”

## 7. 当前归类结论（2026-06-13）

| 文件 | 归类 | 证据 | 说明 |
|------|------|------|------|
| `.omo/goals/current.yaml` | `tracked-ssot` | `src/omo/omo_goal.py` 直接读写；`src/omo/omo_worker_dispatch.py` 明确列为 forbidden global state；`tests/README.md` / `tests/test_omo_governance.py` 把它当当前目标事实源 | 这是活的系统状态文件，不应被当作垃圾文件或简单 ignore |
| `.omo/_delivery/audit-rollout/2026-06-12-5repos.json` | `runtime-state` | `src/omo/omo_audit_rollout.py` 明确把 audit-rollout JSON 作为输出落盘；`tests/test_opc_p5_p7_runtime.py` / `tests/test_opc_trigger_regression.py` 都把 `5repos.json` 当作运行产物来写入和消费；本轮已写入 `projects/omo/.gitignore` | 这是 daemon / rollout 的输出物，不是人工维护的事实源；当前已按 ignore 规则治理，不当 tracked SSOT |
| `.omo/tasks/active/TASK-D1-CHILD1.yaml` | `historical-artifact` | 文件自述 `OPC P3 D1 demo child 1`，`phase: 29`；只在 `.omo/state/system.yaml`、worker runs、demo 证据链里出现 | 属于已完成 demo 的具体实例残留，不是泛化的 active queue 规则文件 |
| `.omo/tasks/active/TASK-D1-CHILD2.yaml` | `historical-artifact` | 文件自述 `OPC P3 D1 demo child 2`，`phase: 29`；引用面与 CHILD1 相同 | 同上 |
| `.omo/tasks/active/TASK-D2-RETRY.yaml` | `historical-artifact` | 文件自述 `D2 demo: D2 retry path`，`phase: 29`；`.omo/d2_demo.py` 直接引用该文件名；worker dispatch/envelope/prompt 全链路引用 | 它是 D2 demo 产物，不是当前运行必须存在的稳定 SSOT |
| `.omo/tasks/active/TASK-D2-SUCCESS.yaml` | `historical-artifact` | 文件自述 `D2 demo: D2 success path`，`phase: 29`；`.omo/d2_demo.py` 与 worker runs 多处引用 | 同上 |
| `.omo/tasks/active/TASK-FEC5E158.yaml` | `historical-artifact` | 文件自述 `OPC P3 D1 demo - lifecycle test`，`phase: 29`；关联 `OPC-P3-D1` done 证据与 promotion records | 属于 D1 lifecycle demo 残留 |

## 8. 推理边界

这份归类有一个关键区分，不能混：

- `tasks/active/` 作为**目录语义**，在测试、自动化和状态摘要里仍是有效运行时概念
- 上面这 **5 个具体文件**，根据文件内容与 `phase: 29` / `demo` / `lifecycle test` 字样，可判为历史实例残留

所以结论不是“`tasks/active/` 整体都该删”，而是：

> `tasks/active/` 目录语义保留；这 5 个特定 demo 实例文件应按 historical-artifact 路径治理。

## 9. 后续动作（精确）

1. `goals/current.yaml`
   - 保持纳入版本管理
   - 已核对并统一入口口径到 `.omo/goals/current.yaml`

2. `2026-06-12-5repos.json`
   - 已归类为运行产物，不作为 tracked SSOT
   - 已落入 `projects/omo/.gitignore`，不在本轮 closeout 里偷换成 clean

3. 5 个 demo active task 文件
   - 不直接删除
   - 先补一份“archive / relocate 方案” (见 `2026-06-13-projects-omo-demo-active-archive-plan.md`)
   - 同步更新 `.omo/state/system.yaml` 里 active queue / task index 的残留引用
   - 确认没有测试直接依赖这些具体文件存在后，再执行治理
