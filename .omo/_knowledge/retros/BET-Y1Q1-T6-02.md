---
status: active
lifecycle: history
owner: governance-team
bet: BET-Y1Q1-T6-02
last-reviewed: 2026-08-15
---

# BET-Y1Q1-T6-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
Appetite 1 week。本轮在隔离 worktree `work/bet-y1q1-t6-02` 一次落地 grill Q1=A / Q2=A+ / Q3=A，未超一周。

## Q2 done_when 是否全部通过？哪条没过，为什么？
- Wave/Gate ↔ BET 映射覆盖 W0–W6 与 T1–T8 / T6-SUBTRACT：是（`docs/architecture/wave-gate-bet-map.md`）
- 无法一对一的项有差异清单：是（Episode/Mandate、G-CONV、T6-EVOLUTION、T9-OBSERV、Phase 编号）
- `start` 无 `--bet` halt、`--bet` 写入 run.`bet_id`：是（`chain-bind-check` + wrapper；pytest 7/7）
- ok closeout / `bet-ledger complete` 缺 binding / 北极星 / retro halt：是（同一 `evaluate_bind`）
- bootstrap/status 打印北极星与 bet/retro：是（两次 CLI 均含 `chain: north_star=` 与 `bound_bet`）
- `redlines.yaml::vision-to-retro-chain` executor 为 `bin/plan/chain-bind-check.py`：是
- 未新增 GaC required 规则、未造第四套 ID

## Q3 过程中发现的与 plan 不符的事实（打假）？
- T6-01 在 origin/main 已合并（#1545）但台账仍 `in_progress`，独占轨 T6-SUBTRACT 让 T6-02 的 `depends_on` 过不去。按事实置 T6-01 done，不是另开 T6-03。
- `start --bet` 原先只改 objective 字符串，run YAML 没有 `bet_id` 字段。硬门必须写回 run 文件，不能只靠字符串。
- `gen-agent-redlines` 只扫 GaC `governance-checks.yaml`，扫不到 `redlines.yaml`。本轮按目标计划把红线登记在 `redlines.yaml`，不新加 GaC required 规则。
- 既有 `tests/test_agent_workflow.py` 大量无 `--bet` 的 runner 单测；它们走已有 waiver `AGCP_REQUIREMENT_ITERATION_GATE=0`，硬门由 `tests/test_chain_bind.py` 覆盖。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？
- 新文件：`bin/plan/chain_bind.py`、`bin/plan/chain-bind-check.py`、`docs/architecture/wave-gate-bet-map.md`、`tests/test_chain_bind.py`、本 retro
- 改接线：`bin/agent-workflow.py`、`bin/plan/bet-ledger.py`
- GaC required 规则：+0
- ADR：+0
- 脚本：+2（链检查，不是第四套台账）

## Q5 下一个认领本 track 的 agent 需要知道什么？
- 不要把 T6-02 标 done 却删掉 `chain-bind-check.py self-check`；`test -f` 映射表不算链门。
- D3/D5 仍未授权。不要发明 Wave/Gate 的第四套 ID。
- 生产路径 `start` 必须 `--bet`；豁免只有 `observer-audit` 与书面 waiver。
