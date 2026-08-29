# BET-Y1Q3-T4-08 Retrospective — WP6 Physical Backup Restore Integrity Drill

- date: 2026-08-29
- status: 真实 isolated drill 执行成功, evidence 齐

## 演练实录 (drill_id: physical-recovery-1788007018)

- source: docs/scene-cards (非生产只读, principal 批准)
- 三 digest 完全一致: source = backup = restored (sha256:def06ad0...)
- replay: 20 文件 byte-identical, rc=0
- executed=true / integrity_ok=true / human_confirmed=true (principal:xiamingxing 2026-08-29 会话批准)
- cleanup: removed (证据捕获后, 符合契约); backup 与 immutable receipt 保留
- dry-run 语义验证: 永不假绿 (meets_physical_gate=false) ✓

## 过程记录

- b1 轮: replay 命令缺参数 rc=2 (executed=false 诚实拒绝)
- b2 轮: glob 路径错 rc=1 (诚实拒绝)
- b3 轮: 修复后 rc=0 → executed=true
- 教训: fail-closed 语义在 replay 环节真实生效——坏 replay 永远不通过 gate
