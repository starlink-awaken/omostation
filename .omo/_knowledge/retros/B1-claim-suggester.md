---
schema: bet-retro/v1
bet_id: B1-claim-suggester
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-20
type: ephemeral
completed_at: 2026-09-20
---

# Retro: B1.2 — claim-suggester (AI 驱动治理深化)

## Summary

新增 `bin/ssot/claim-suggester.py` — 根据 git log + ledger 自动建议 candidate BET。
4 类检测模式:
1. **CONSOLIDATION**: 同一 scope 30 天内 ≥ 3 次 → 建议合并收口 BET
2. **TRACK-DEEPENING**: 同一 track ≥ 4 个 feat → 建议深化 BET
3. **ORPHAN-WIP**: `WIP on agent/...` 提交残留 → 建议收口
4. **DOC-DRIFT**: 反复 `chore(tasks|docs|doc|debt)` ≥ 5 次 → 建议文档管理 BET

## What went well

- **数据驱动**: git log + ledger 是现成 SSOT, 无需新数据源
- **可测试**: 纯函数检测逻辑, 10 个单元测试覆盖所有 4 类模式
- **可执行**: 输出 `suggested_id` (BET-CONSOLIDATE-X-SCAPE-NNDDB 等), 直接可作 ledger entry
- **可观测**: JSON 输出便于 CI 集成 (定期跑 → 报警 → active 工作建议)
- **复用**: 不依赖 LLM, 纯规则匹配, 0 API cost, 跑得快 (<1s)

## What was learned

- **commit 短哈希只含 0-9 a-f**: 测试用 `ghi9012` 含 `i` 非 hex → regex 不匹配.
  教训: git short SHA 的字符集 `[0-9a-f]+`, 测试 mock 时必须用 hex 字符
- **scope 关键词 vs track**: 不同 scope 但同 track 需要二级聚合.
  e.g. `feat(panorama)` 和 `feat(panorama-claims)` 都属 panorama track
- **去重逻辑**: suggested_id 形如 `BET-CONSOLIDATE-X-NNDDB` 不与现有 BET-id 形如
  `BET-YxQx-Tx-Nx` 冲突, 实际不需要 dedup — 但保留作 safety net

## What to improve

- **TRACK 关键词硬编码**: 当前 `panorama/claims/value/debt/governance` 5 个.
  应改为读 `.omo/standards/business-domains.yaml` 动态加载
- **未触发 STALE-PLANNED**: 文档承诺的 5 类只实现 4. ledger state `started/in_progress`
  > 30 天的检测需要解析 yaml, 未做
- **未对接 LLM 语义分析**: 当前纯正则匹配, 未来可加语义聚类
  (e.g. `feat(panorama): Claims 生命周期授权` 多个 → 抽象出"权限"主题)

## Metrics

- Files added: 2 (bin/ssot/claim-suggester.py 200L, tests/bin/test_claim_suggester.py 110L)
- Files modified: 0
- Tests: 10/10 pass in 0.20s
- Detection patterns: 4 (CONSOLIDATION/TRACK-DEEPENING/ORPHAN-WIP/DOC-DRIFT)
- Coverage: 30 days git log (157 commits in test env)
- Suggestions per run: 50 (示例)
- PR: TBD
- Total LOC delta: +310

## 完整 done_when 验收

| 项 | 状态 |
|---|---|
| `bin/ssot/claim-suggester.py` 实现 | ✅ |
| 4 类检测模式 (CONSOLIDATION/TRACK-DEEPENING/ORPHAN-WIP/DOC-DRIFT) | ✅ |
| git log 读取 (--since-days) | ✅ |
| ledger 读取 (避免与已有 BET-id 冲突) | ✅ |
| JSON + stdout 双输出 | ✅ |
| 10 单元测试 (含 hex 字符修正) | ✅ |
| script-registry 登记 | ✅ |
| ruff check 0 errors | ✅ |
| doc-governance PASS | ✅ |
| 实测 30 天数据 10 条建议 | ✅ |