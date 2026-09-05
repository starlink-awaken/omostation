---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-30
type: ephemeral
status: archived
---
# BET-Y1Q3-T4-08 Retrospective — WP6 Physical Backup Restore Integrity Drill

- date: 2026-08-29
- status: 真实 isolated drill 成功 (executed=true / integrity_ok=true / human_confirmed=true)

## 演练实录 (drill_id: physical-recovery-1788007018)

- source: docs/scene-cards (非生产只读, principal:xiamingxing 2026-08-29 会话批准)
- 三 digest 完全一致: source = backup = restored (sha256:def06ad0...)
- replay: 20 文件 byte-identical, rc=0; cleanup: removed (证据捕获后, 契约语义)
- dry-run 语义: 永不假绿 (b1/b2 轮坏 replay 被 fail-closed 诚实拒绝)
- run 绑定: 20260829T124727Z-bet-execution-76619022

## 教训

- fail-closed 在 replay 环节真实生效——坏 replay 永不通过 physical gate
- bump 子模块指针必须用 squash 后的 main 头 (今日指针污染根因)
