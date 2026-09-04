---
schema: value-evidence/engineering-rollback/v1
bet: BET-Y1Q3-T4-01
axis: engineering
evidence_key: rollback
rollback_strategy: git_revert
revertible_commits: 
rollback_verification: git revert --no-commit <sha> 可干净回退(无冲突)
verified_at: 2026-08-22
lifecycle: history
owner: governance-team
last_updated: 2026-08-26
---

last-reviewed: 2026-08-26
---
回滚能力:
- 所有实现 commit 均为独立合并 commit, 可逐个 `git revert`
- north_star 恢复(#1845)是纯 rename, revert 无风险
- attestation verifier(#1849)是独立新增函数 + 测试, revert 不触碰既有逻辑
- 验证: git revert --no-commit 对每个 commit 无冲突(手动验证)
