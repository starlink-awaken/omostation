---
bet_id: BET-Y2Q1-T6-01
status: completed
completed_at: 2026-09-07
run_id: 20260907T03-memory-decay-engine
pr: "https://github.com/starlink-awaken/omostation/pull/3361"
---

# Retro: BET-Y2Q1-T6-01 — 跨生命周期记忆衰减与冲突消除引擎

## What went well

- DecayManager 设计清晰：score → deprecate → detect conflicts → report 四阶段
- 17 个 pytest 测试一次性绿（修复 API 不匹配后）
- CLI `--check-decay` 优雅处理缺失图谱文件 (graceful no-op)
- spec frontmatter 完整, accepted_specifications 绑定成功

## What was learned

- KnowledgeGraph 使用私有属性 (`_edges`, `_entities`), 没有公开迭代器 — 下一版应暴露 `list_edges()` / `entities` 属性
- `A supersedes B` 中 B 是被废弃的一方（target）, 不是 superseder
- Network flakiness (SSL_ERROR_SYSCALL) 导致多次 push 重试 — pre-push submodule-reachability hook 串行检查 16 个子模块
- spec frontmatter 需要 `schema_version: specification/v1` 但 bet-ledger help 未明示

## What to improve

- 暴露 KnowledgeGraph 公开访问 API
- pre-push hook 应并行 fetch + 每个子模块独立 timeout
- bet-ledger help 加 frontmatter schema 说明

## Metrics

- Files changed: 4 (decay_manager.py, test_decay_manager.py, m0_feedback.py, 3y-bet-ledger.yaml)
- Tests: 17 new, all passing
- Appetite: ~2 hours (within 2-day budget)
- LOC: ~430 (含 tests)
