---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q1-T1-05 阶段复盘 — 独立 writer clone 硬门
type: retro
---
# BET-Y1Q1-T1-05 阶段复盘 — 独立 writer clone 硬门

> 日期：2026-08-13  
> 结论：完成 writer clone gate 切片；BET 仍未完成，D2/D3/D5 暂不退役。

## Q1 实际耗时 vs appetite

本切片约 2 小时，低于 BET 的 2 周 appetite。时间主要花在复现 Orca linked
worktree 的子模块污染、建立真实独立 clone、TDD 与两轮独立审查。

## Q2 done_when 通过情况

| 条目 | 状态 | 证据 |
|---|---|---|
| 主仓对 agent identity 只读 | 部分通过 | tracked pre-commit 对所有 `AGENT_ID` 强制 `--require-clone`；真实 linked worktree 被拒绝 |
| 每 agent 独立 clone | 试点通过 | `/Users/xiamingxing/agents/blueprint-director/ws` 是独立 `.git`，19 个直接子模块冻结 |
| 集成只经 ref/review | 进行中 | clone 已注册到 Orca；本轮走私有分支与 PR，不在主仓集成 |
| manifest 可重放 | 试点通过 | baseline digest `ac1aacdb34a2aa5f83e7581641f63ed1a4b0b96bdd3901c9857c0e6c73eef76f`，root + 19 子仓验证通过 |
| cross-repo changeset | 试点通过 | no-op changeset `5e7c310f...`，明确 `no_change=true` |
| 全部 agent 迁移 | 未通过 | 当前仅 writer clone 试点；存量 agent 尚未逐一迁移 |
| 主仓 72 小时零冲突 | 未通过 | 观察窗尚未完成，不能提前判绿 |
| D2/D3/D5 退役 | 未通过 | 依赖全员迁移与观察窗，当前继续保留 |
| 表面积净减 | 未通过 | 本切片为硬门增量；真正减法在退役阶段发生 |

因此本次不能把 `BET-Y1Q1-T1-05` 标为 done，也不能删除 D2/D3/D5。

## Q3 与计划不符的事实

1. Orca 创建的是 linked worktree，共用主仓 git common dir，不等于独立 clone。
   在该 worktree 初始化子模块时复现了数百个 staged deletion，证明它不能承接
   writer isolation。
2. 现有 `agent-clone.py` 已具备 clone、manifest、verify、changeset，真正缺口是
   `guard` 默认放行无 identity 的 legacy worktree。
3. 首版 hook 用空 Bash 数组拼参数；macOS Bash 3.2 在 `set -u` 下空数组展开报
   unbound variable。真实 hook 回归测试发现并修复。
4. 第二版通过 `$HOME/agents/<id>/ws` 判断迁移状态；独立审查证明改写 `HOME` 可绕过。
   最终改为：任何非空 `AGENT_ID` 都无条件启用严格 clone gate，人类终端不受影响。
5. zsh 的 `path` 是特殊变量。用 `path` 当循环变量会覆盖 `PATH`，导致 `uv` 突然
   不可见；后续脚本和操作指引应避免该变量名。
6. PASW claim 已动态覆盖根 `.gitmodules` 的全部直接子模块；registry 和
   pre-commit 文案仍把它混同为 gbrain/cockpit/agora 三项。现已拆分为动态 claim
   覆盖与三项 gitlink guard 两个事实。

## Q4 净增减与验证

本切片净增是迁移硬门、行为测试和操作合同，尚未发生 D2/D3/D5 删除，因此不宣称
表面积净减。

`bet-ledger.py surface`（2026-08-13，git tracked 口径）：

- `src_loc=876175`，较 2026-08 基线 `+149763`；
- `test_loc=423911`，较基线 `+73057`，保护量未下降；
- `gac_rules=136`，与基线持平；`gac_required=27`，较基线 `+1`；
- `bin_scripts=461`，较基线 `+151`。

这些是全仓累计观测，不归因于本切片；它们进一步说明 T1-05 的最终验收必须包含
旧门禁/脚本的真实退役，不能把“新加一个严格门”包装成表面积收敛。

验证：

- `bin/gac/test_agent_clone.py`: 36 passed；测试使用真实临时 Git 仓、真实
  `git worktree add` 和 tracked pre-commit。
- Ruff、Bash 3.2 `bash -n`、`git diff --check` 全部通过。
- agent-workflow verify：5 项检查通过；`make gac-local-gate` 44 checks ALL GREEN。
- 独立 reviewer 首轮发现 `HOME` 绕过后 BLOCK；修复后复审 CLEAR。
- 真实 `AGENT_ID=blueprint-director` commit 由 clone guard 判定 `verified_clone`。

## Q5 后续 agent 必须知道

1. 写入型 agent 必须进入独立 clone 并设置 `AGENT_ID`；Orca 只做 transport，使用
   `orca repo add` 注册现有 clone，不能把 Orca linked worktree 当 writer clone。
2. 任何 `AGENT_ID` 都会触发严格门；没有 identity 的 legacy worktree 直接拒绝。
3. D2/D3/D5 仍是迁移保护网。只有全员迁移、manifest/changeset 重放和连续 72 小时
   零冲突均成立后，才能启动退役 PR。
4. 下一阶段优先迁移 2–3 个长期 writer clone，并修复/启动 72 小时观测；不要继续
   为每个短任务创建带 19 个 PASW 的 linked worktree。
5. 规格机制不另建第二套 truth。后续 WorkPacket 应绑定 frozen spec hash/revision，
   继续复用 OMO BET/task、ECOS WorkPacket、agent-workflow、VerificationReceipt。
