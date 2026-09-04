---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T6-04 复盘
type: retro
---
# BET-Y1Q2-T6-04 复盘

## Q1 实际耗时 vs appetite？超出比例？
3 days appetite，实际在 1 天内完成归档 + 验证，未超 appetite。

## Q2 done_when 是否全部通过？哪条没过，为什么？
- ✅ 保留 <= 40 个覆盖 A_conflict / B_failure_injection 核心原型的用例 — 实际保留 5 个（A01/B01/C01/D01 + README.md），远低于 40 上限。
- ✅ 实际结果: 222 → 5 (仅保留 A/B/C/D 核心原型) — 217 个文件移入 .omo/_archive/collab-scenarios/。
- ✅ make collab-dualtrack 验证 silent_loss=0 — 验证通过，无解析失败。

## Q3 过程中发现的与 plan 不符的事实（打假）
- 原计划"归档 221 → ≤40"，实际归档到 5，远超预期。原因是 Web3 对抗夹具与内核回归无关，可完全归档。
- silent_loss=0 验证通过，说明归档操作未破坏 collab-dualtrack 的报告产出能力。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
待执行：`uv run --with pyyaml python bin/plan/bet-ledger.py surface`

## Q5 下一个认领本 track 的 agent 需要知道什么？
- .omo/_delivery/collab-scenarios/ 当前只保留 A/B/C/D 4 个核心原型 + README.md。
- 归档文件在 .omo/_archive/collab-scenarios/（ADV01-ADV185 + GEN*），可按需恢复。
- make collab-dualtrack 仍能产出报告且 silent_loss=0。
