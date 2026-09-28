---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-27
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: KOS 治理语料摄入 — workspace 知识资产入索引 + 消费验证
bet_id: BET-Y2Q4-T3-03
---

# BET-Y2Q4-T3-03 — KOS 治理语料摄入

## 授权链

T3-02 摄入提案（"owner 表态后立项"）→ principal 下阶段「go」→ 本单执行。
批次一至四（规则接线 42→0）与 ADR-0456 减法为同周背景。

## 目标

把 workspace 治理知识资产摄入 KOS 索引（T3-02 实证：索引 12,553 篇中治理语料为 0）：

- 摄入对象：`.omo/_knowledge/decisions/`（~420）、`retros/`（~550）、`patterns/`（37）、
  `pitfalls/`（47），合计 ~1,050 篇
- 通道：`kos-cli.py ingest <dir>`（官方增量通道，dry-run 已验证 420/420 可构建）
- 安全：摄入前 sqlite 文件级备份（data/kos/kos-index.sqlite → 同目录 .bak-<date>）

## 验收（done_when 摘要）

1. 四目录摄入完成，documents 计数 12,553 → ≥13,500；
2. 消费验证：`kos-cli search "ADR-0453 声明执行鸿沟"` 类治理查询 ≥3 命中且
   doc 指向 .omo/_knowledge/decisions/；
3. 抽查 ADR-0453 / 一个 pattern / 一个 pitfall 的索引记录（title/canonical_path 正确）；
4. 摄入报告落 docs/reports/（before/after 计数 + 命中证据 + 备份路径）；
5. retro 固化。

## 红线

- 只增量摄入，不重建/不清空既有索引；
- 备份先行，摄入失败可回滚（恢复 .bak）；
- 不改 kos 包实现（发现工具缺陷只记录提案）。

## verify

- `sqlite3 data/kos/kos-index.sqlite "SELECT COUNT(*) FROM documents;"` → ≥13,500
- `kos-cli.py search "ADR-0453"` → ≥3 命中且含 decisions 路径
- `make gac-local-gate` → exit 0
