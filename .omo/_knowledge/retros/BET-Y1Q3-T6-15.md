---
schema: bet-retro/v1
bet_id: BET-Y1Q3-T6-15
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-28
---

# BET-Y1Q3-T6-15 retro — R1 through R2a

## What changed

The recovery was executed from authoritative GitHub main in isolated clones.
The sequence completed R1 baseline recovery, H1a blocking GaC, H1c required
context promotion, and R2a immutable runtime hygiene. R2b was intentionally
held at the host boundary.

## Evidence and outcome

- R1: PR `#2438`, merged main recovery and ADR-0432 candidate disposition.
- H1a: PR `#2441`; strict `gac-gate` became blocking and passed in CI.
- H1c: PR `#2455`; live required contexts are
  `phase-gate`, `bet-done-transition`, and `gac-gate`, with non-context
  protection settings preserved.
- R2a: PR `#2457`; immutable treeish checks pass on PR tree, merged main and
  fresh clone, with zero forbidden runtime paths.
- R2b: owner, permission, digest and SQLite integrity were observed read-only;
  producer control and host migration were not performed.
- Value: `NOT_PROVEN` by contract.

## What went wrong

The initial canary was falsely green because the strict gate used
`continue-on-error`. Subsequent execution also exposed stale workflow packets,
missing waiver metadata, stale architecture links, missing workflow command
pointers, a GitHub API conditional-header limitation, and a blanket tracked
runtime allow. Each was resolved through a narrow PR or recorded as an
unresolved host boundary; no evidence or value budget was raised to hide it.

## What to preserve

Keep repository evidence, live host evidence and principal-bound value as
separate verdicts. Keep the immutable treeish policy and required `gac-gate`
context in the normal delivery path. Treat the shared dirty checkout and all
producer declarations as a stop-and-inspect signal before R2b.

## Next admissible action

Choose a clean live checkout or explicitly authorize a controlled operation on
the current shared checkout. Then produce the R2b backup, producer lifecycle,
ignored-restore, digest, SQLite integrity and rollback receipts before any
Product P0 Wave A unlock or BET completion.


## R2b 收账补记 (2026-08-30, #2666 后被并发合并回滚, 本次重新落账)

第二次精确人工授权已获得（owner 授权链）。R2b 七步全部执行完毕（备份/完整性/
producer stop-start/回执），event-ingest plist 修复经 ADR-0435 + wrapper 方案
永久化并已在 canonical checkout 验证 exit 0。retention/operational
UNPROVABLE → PROVEN；Product P0 Wave A 前置解锁。

## R2b 收账重落账 (2026-08-30)

#2666 的收账被并发 ledger 合并回滚（status 与报告节丢失）。本次基于最新 main
重新落账：R2b 七步回执内容不变（备份 928 文件/113MB、SQLite 四重完整性 ok、
producer 修复经 ADR-0435 wrapper 方案、event-ingest canonical 验证 exit 0）。
retention/operational PROVEN 维持。
