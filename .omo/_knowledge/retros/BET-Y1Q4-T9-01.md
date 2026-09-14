---
type: ephemeral
status: archived
---

# BET-Y1Q4-T9-01 复盘

## Q1 实际耗时 vs appetite？超出比例？

约 0.3 day vs appetite 1 day。未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？

1. ledger 锁超时（>5min）自动检测并触发 checkpoint — **通过**（`ledger_check.check_and_recover` + 单测）
2. 连续 3 次 checkpoint 失败则 kill 持有锁的僵死进程 — **通过**（circuit_breaker：`_checkpoint_failures >= 3` 且 CPU <1%）
3. resident-status 增加 ledger 锁年龄指标 — **通过**（`components.ledger.lock_age_seconds`；`make resident-status` health=recovered）

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. 台账初始 `write_surfaces` 只有 `ledger_check.py`，但 Spec done_when 要求 status 接线 — 已扩面到 `status.py` + 测试。
2. `pasw_required: false`，但误写入 `.subtrees/omo`；实际交付面是 `projects/omo`（make 入口）。
3. 缺 ledger / daemon never-ticked 原先会把 health 打成 degraded，与 Spec「冷启动非致命」冲突 — 已改为 ok + cold_start/missing 标记。
4. claim 强制 affected-graph receipt；write_surfaces 变更后旧 run 触发 `WORK_PACKET_SOURCE_DRIFT`，需 close blocked 再 start。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？

- 新增：`ledger_check.py`、`test_ledger_check.py`、Spec、retro
- 修改：`status.py`、`test_resident_status.py`、ledger write_surfaces
- GaC 规则 / ADR / 脚本：0
- 净增必要：锁监控是新能力；无对应可删脚本（circuit_breaker 内嵌模块而非新 bin/）

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. `make resident-status` 冷启动（无 watermark / 无 ledger）现为 recovered，不再是 degraded。
2. 僵死 kill 默认不触发；只有 checkpoint 连续失败 3 次才会评估 CPU。
3. 若要把 lock monitor 挂到 cron/hook，另开 bet（本 bet non_goals 外延）。
4. pre-commit / portfolio broker 等非强依赖跟进拆独立 bet，勿塞进本 PR。
