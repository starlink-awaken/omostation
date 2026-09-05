---
schema_version: specification/v1
spec_version: 1.0.0
title: 子模块 doc frontmatter 批量迁移收尾 + doc-index 合规收口
bet_id: BET-Y1Q4-T10-02
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-04
last-reviewed: 2026-09-04
type: ssot
last_updated: 2026-09-04
---

# 子模块 doc frontmatter 批量迁移收尾 + doc-index 合规收口（BET-Y1Q4-T10-02）

## 背景（Context）

P78 结构化重构后，子仓文档缺少统一 frontmatter（type/owner/last_updated）。
T10-01 完成批量迁移，T10-02 负责收尾：doc-index 合规问题从 1402 降至
legacy warning 预算内（≤800），同步更新主仓 gitlink。

## 交付物（Deliverables）

- 所有子模块 frontmatter 覆盖率 ≥95%
- doc-index 合规问题 ≤800（仅 legacy warnings）
- gitlink drift = 0
- 主仓 gitlink 同步至 origin/main

## 验收标准（Acceptance Criteria）

- `uv run --with pyyaml python bin/ssot/generate-docs-index.py --check` 通过
- `python3 bin/ssot/submodule-reachability-gate.py --source index` exit 0
- ledger lint 通过
