---
lifecycle: entry
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
# BET-Y1Q2-T1-09 Orca + Crush 脱敏 E2E 回执

验证时间：2026-08-12（Asia/Shanghai）

## 验证边界

- 真实 Orca runtime 与真实 Crush `v0.88.1`。
- 任务仅要求报告 ready，不允许修改文件。
- 不记录 prompt 正文之外的终端 transcript，不记录密钥、模型配置或私有内容。

## 可重放查询

```bash
orca orchestration task-list --run run_515c4598d7a0 --json
orca orchestration dispatch-show --task task_566a871b757b --json
```

## 脱敏运行标识与结果

| 字段 | 值 |
|---|---|
| run_id | `run_515c4598d7a0` |
| task_id | `task_566a871b757b` |
| dispatch_id | `ctx_421ad1113fd0` |
| dispatch status | `completed` |
| dispatch failure_count | `0` |
| task status | `completed` |
| worker outcome | `succeeded` |
| files modified | `none` |

任务在 `2026-08-12 14:48:48` 注入，在 `2026-08-12 14:49:10` 完成。worker
回执确认收到 adapter preamble、CLI 命令与 terminal identity，并明确报告没有文件改动。

## 诚实边界

适配器在 dispatch 时只返回 `state=dispatch_injected`、`input_accepted=unproven`；上表中的
`completed` 来自之后独立查询 Orca task/dispatch 状态和 worker 的 `worker_done`，不是在注入时预判。

当前 coordinator 缺少 stable pane identity，跨上下文 ack delivery 返回
`stable_pane_required`；非绑定上下文也不能安全执行 `worker-release`。因此本轮不强制关闭 terminal，
由适配器继续把它列为 `residual_resources`，避免用资源删除冒充生命周期闭环。
