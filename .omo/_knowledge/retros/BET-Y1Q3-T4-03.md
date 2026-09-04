---
title: BET-Y1Q3-T4-03 回顾 — Honest Scene Card Gate
type: retro
lifecycle: history
owner: laowang-agent
last_updated: 2026-08-28
created: 2026-08-28
related: []
---
# BET-Y1Q3-T4-03 Retrospective — Honest Scene Card Gate

- date: 2026-08-28
- bet: BET-Y1Q3-T4-03 (Product P0 WP1, T4-OUTCOME)
- status: engineering IN_PROGRESS (worktree 实现+测试完成, 等 merge 回填 merged_reachable_commit)

## 做了什么

`make scene-card-check` 修复 false-green：原 recipe 末尾 `echo` 帮助文本吞掉退出码，
20 张全 blocked 的真实仓仍 exit 0。修正后 `test "$$blocked" -eq 0` 作为 recipe 最终权威命令。

实现细节（超出 spec 最小修改的一处，记录决策理由）：

- recipe 显式 `--root .`：`scene-card-lifecycle.py` 默认 root 由**脚本位置**推导
  (`parents[2]`)，受控测试环境 (tmp cwd) 无法自建 trial log 让 ready 卡就绪。
  `--root .` 在真实仓 (cwd==ROOT) 行为不变，测试环境获得确定性。行为等价性由
  `test_all_ready_exit_zero` / `test_no_cards_exit_zero` 双向锁定。

## 验证证据

- RED: `test_mixed_cards_exit_nonzero` 旧实现失败 (exit 0 false-green 实锤)
- GREEN: 9/9 passed (`tests/test_scene_card_lifecycle_check.py`)
- 真实仓: `make scene-card-check` → `ready=0 with-blockers=20` + exit 1 (honest-block)
- diff 恰好两个授权写面: Makefile + tests/test_scene_card_lifecycle_check.py (+ledger/retro 台账面)

## 避坑

- worktree 里 `.omo/_knowledge/workflow-mesh/external-scene-trials.jsonl` 不存在
  (runtime 数据不进 git) → 真实仓 20 张全 blocked 的主因含 trial_log 缺失,
  不全是 activation_blockers。后续 T4-02 父编排分析时注意区分这两种 blocker 来源。

## 剩余闭环 (人到场)

1. PR merge 后: engineering → VERIFIED (merged_reachable_commit + tests/diff/rollback receipts)
2. 人工 attestation: `docs/operations/human-attestations/BET-Y1Q3-T4-03-accept.yaml`
   → value → ACCEPTED → `bet-ledger.py complete BET-Y1Q3-T4-03`
