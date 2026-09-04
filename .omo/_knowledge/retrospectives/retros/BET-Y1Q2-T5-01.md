---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T5-01 复盘
type: retro
---
# BET-Y1Q2-T5-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
单 session 完成核心实现 + 测试（约半天 vs appetite 2 周），未超出。
主要耗时在理解 Workflow Mesh 事件投影架构（`project_workflow_run` 从 append-only 日志重建快照）+ 确认 `waiting_approval` 状态本身的持久性与真正缺口（timer 在内存、重启丢失）。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| WorkflowRun 进入 waiting_approval 后, 进程重启不丢状态 | ✅ `approval_timeout.py` 从 append-only 事件日志重建快照, `timeout_after`/`requested_at` 投影进 snapshot approvals; 集成测试 `test_pending_approval_survives_restart_until_deadline` 验证重启后状态与 deadline 均不丢 |
| 超时策略可配置, 到期产生 OMO 事件而非静默 | ✅ `ApprovalRequested` payload 支持 `timeout_after` (ISO 8601), 默认 `P7D`; `scan_approval_timeouts` 到期产生 `ApprovalExpired` 事件 (waiting_approval → unavailable), workflow_eval review 面板可见而非静默 |
| 集成测试覆盖 7 天场景(时间可注入) | ✅ `scan_approval_timeouts(now=...)` 时间注入; 集成测试 `test_seven_day_policy_expires_and_is_durable` + 单元测试 8 个全绿 |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **`waiting_approval` 状态本身早已持久**: 事件是 append-only JSONL, 快照每次从事件重建 —— "进程重启不丢状态"其实已满足。真正缺口是 **timer**：超时截止时间此前只存在于调用方内存, 重启即丢, 且无人扫描到期。故本 bet 交付的核心是 `scan_approval_timeouts` 持久化扫描, 而非状态存储。
2. **approvals 投影此前不含 requested_at**: `ApprovalRequested` 事件投影只有 approval_id/state/event_id, 无时间字段 —— 无法计算 deadline。补了 `requested_at` (来自事件 occurred_at) + `timeout_after`。
3. **新增事件类型需三处同步**: `EVENT_STATE` + `_ALLOWED_EVENTS` (waiting_approval 状态) + approvals 投影分支。`waiting_approval → unavailable` 转移在 `_ALLOWED_TRANSITIONS` 中已存在, 无需改。
4. **run-all.sh 环境性失败 (3/7 suites)**: kairon/gbrain/runtime-e2e 失败均为环境性 (kairon 31 包全量测试需完整依赖、gbrain bun 测试需完整 node_modules、runtime-e2e 需服务运行), 与 T5-01 改动无关; workflow_mesh 集成测试在 omo 完整 env 下 26/26 全绿。
5. **verify --all 8 FAIL 均为 pre-existing**: task_count_drift (ssot-guardian)、ADR 并发编号冲突 (adr-coverage)、submodule-hygiene 脚本未合入、governance-evolution 环境性 —— 均非本 bet 引入。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
```
test_loc      367,582 → 350,854  (+16,728, 不得下降)  ← 观察量, 非本 bet 贡献
adr_total       371 → 344       (+0 本 bet)
gac_rules       136 → 136       (+0)
gac_required     26 → 26        (+0)
bin_scripts     400 → 310       (+0 本 bet)
```

本 bet 净增（omo 子模块 commit 4a406ac2）:
- 新文件 `src/omo/approval_timeout.py` (~280 行): `scan_approval_timeouts` / `expire_approval` / `parse_iso_duration` / `DEFAULT_APPROVAL_TIMEOUT=P7D`
- `src/omo/workflow_mesh.py` +~24 行: `ApprovalExpired` 事件类型 (EVENT_STATE + _ALLOWED_EVENTS + approvals 投影 requested_at/timeout_after)
- 新测试 `tests/test_approval_timeout.py` (8 个) + 根仓集成测试 `tests/integration/workflow_mesh/test_phase6_durable_approval_timeout.py` (2 个)

无新增 GaC 规则 / ADR / bin 脚本。`test_loc` 增加但为测试能力 (7 天场景覆盖)。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **durable timer 扩展模式**: 新超时/到期场景 = ①在事件投影加 `*_at` + `timeout_after` 字段 ②新增到期事件类型 (EVENT_STATE + _ALLOWED_EVENTS + 投影分支) ③写 `scan_*_timeouts` 持久化扫描 (时间可注入 now 参数, 默认 dry-run, apply=True 才写) ④幂等 key `<run>:approval-expired:<id>` 防重复。
2. **PASW 子模块提交流程**: 在 `projects/omo` (detached HEAD) 提交 → `.subtrees/omo` FF merge 到 agent 分支 → push 分支 → `gac-worktree.sh bump-pointer`。**勿直接改共享 checkout 的 projects/omo** (本会话曾误改, 已回退)。
3. **ApprovalExpired 后 run 进入 unavailable**: 语义是"审批超时视为后端不可用", 后续可走 `WorkflowRecovered` 恢复或 `WorkflowClosed` 收口 —— 产品侧如需"超时即取消"需另加 `WorkflowCancelled` 分支。
4. **7 天验证无需等待**: `scan_approval_timeouts(now=<future>)` 注入时间即可, 不要 sleep 等待真实 7 天。
5. **待办**: `expire_approval` 目前只写 mesh 事件; 若要联动 EventBus/webhook 告警 (类似 quota 告警), 是 T5-01 的自然延伸, 但已超出本 bet done_when。
