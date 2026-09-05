# BET-Y1Q4-T9-02 复盘

## Q1 实际耗时 vs appetite？超出比例？

约 0.3 day vs appetite 0.5 day。未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？

1. resident daemon/heartbeat 路径调用 check_and_recover — **通过**（`daemon.tick_once` + `heartbeat.publish_heartbeat` 显式调用；单测 monkeypatch 覆盖）
2. make resident-status 仍 health=recovered|ok — **通过**（`health=recovered`）

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. `heartbeat.publish_heartbeat` 已通过 `status.snapshot()` → `_ledger_snapshot` 间接调用 recover（T9-01）；本 bet 仍需显式 tick 调用点以满足 done_when #1。
2. claim-check 提示 `governance-agent`，用户指令为 `engineering-agent`；`project-code-change` 两者均可，按用户指令用 engineering-agent 成功 start。
3. `gac-worktree.sh bump-pointer` 一度落到旧 SHA（dad7c21）；以 `projects/omo` HEAD=`origin/main`（1c1d348）手工 `update-index` 纠正。
4. `pasw_required: false`，交付面是 `projects/omo`（非 `.subtrees/omo`），与 T9-01 复盘一致。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？

- 新增：Spec、retro、closeout report、2 个单测
- 修改：`daemon.py`、`heartbeat.py`、ledger write_surfaces / Spec 绑定
- GaC 规则 / ADR / 脚本：0
- 净增必要：tick 接线是 T9-01 的最小后续；无新 bin（circuit_breaker 遵守）

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. 锁监控现已挂在 daemon tick + heartbeat publish；人工 `resident status` 不再是唯一入口。
2. 阈值 / zombie kill 仍属 T9-01 `ledger_check.py`；勿在接线 bet 里改策略。
3. omo 合并 SHA：`1c1d348`（PR #143）；根仓指针需指向该 commit。
