---
schema_version: specification/v1
spec_version: 1.0.0
title: docs last_updated保鲜 batch1-6
bet_id: BET-Y1Q3-T10-200
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-03
last_updated: 2026-09-03
type: ssot
last_updated: 2026-09-03
---

# docs last_updated保鲜 batch1-6（BET-Y1Q3-T10-200）

## 背景（Context）

docdate 扫描要求 docs 携带合法 `last_updated` 字段。BET-Y1Q3-T10-200 作为
batch1 试点，只覆盖 3 个点名文件，验证扫描口径可用，不碰业务逻辑，
不一次全量改 165 个文件。

## 目标（Goal）

给以下 3 个文件补 `last_updated: 2026-09-03` 并跑 batch1-6 保鲜验证：

- `docs/local-compute/compute-fabric-workflow.md`
- `docs/local-compute/omlx-cluster-architecture.md`
- `docs/overview/cross-package-api-map.md`

## 非目标（Non-Goals）

- 不改文档正文语义，只补 `last_updated` 保鲜字段。
- 不碰业务代码与治理门禁逻辑。
- 不一次全量改 165 个文件，本 bet 只做 batch1-6。

## 完成标准（Done When）

1. 上述 3 文件均有 `last_updated` 且格式合法（`YYYY-MM-DD`）。
2. docdate 扫描对上述 3 文件不再报缺失。
3. `bin/plan/bet-ledger.py lint` 通过，BET-Y1Q3-T10-200 结构合法。
4. 本 spec 的 binding（spec_ref / spec_version / content_digest /
   decision_ref）与 ledger 记录一致，digest 与文件 sha256 一致。

## 验证（Verify）

- `uv run --with pyyaml python bin/plan/bet-ledger.py lint` → exit 0。
- `grep -n last_updated docs/local-compute/compute-fabric-workflow.md docs/local-compute/omlx-cluster-architecture.md docs/overview/cross-package-api-map.md` → 3 文件均有输出。

## 决策引用（Decision Ref）

- `decision://accepted/BET-Y1Q3-T10-200`
