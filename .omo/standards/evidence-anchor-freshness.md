---
schema_version: standard/v1
standard: evidence-anchor-freshness
created: 2026-08-30
last-reviewed: 2026-08-30
owner: governance-team
origin_bets: BET-Y1Q3-T4-07 (三轮 DIGEST_MISMATCH 事故)
review_before: 2026-11-28
type: ssot
---

# completion_evidence 锚新鲜度契约

## 背景

T4-07 收口时连环 DIGEST_MISMATCH：engineering/operational 轴锚定文件的 sha256
在文件被后续 commit 更新后失配（retro 增补/receipt 重生成均触发）。

## 契约

1. **锚即快照**: evidence 的 sha256 是写入时刻的快照。锚定文件此后**只增不改**
  （retro 用追加、receipt 用新文件），否则锚必失配。
2. **complete 前刷新**: 填 evidence 前对全部锚文件重算 sha256（脚本化：
   `sha256sum <files>` 对照），不信任上次算的值。
3. **fail 的语义**: DIGEST_MISMATCH 不是错误是**信号**——说明锚文件在锚定后
   被改过，应先核实改动合法性再刷新锚，禁止无脑重算掩盖未审计变更。
4. **merged_reachable_commit 禁止手搓**: 必须从 `git rev-parse origin/main`
   取完整 40 位 sha，禁止短 sha 补零/凭记忆拼。

## 动态化

review_before 2026-11-28。若 bet-ledger 增加 evidence 自动刷新/审计功能，
本契约第 2/3 条可简化为工具调用。
