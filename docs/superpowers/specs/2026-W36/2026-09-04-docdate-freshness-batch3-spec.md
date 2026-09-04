---
schema_version: specification/v1
spec_version: 1.0.0
title: docs last_updated保鲜 batch3-6
bet_id: BET-Y1Q3-T10-201
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-04
last-reviewed: 2026-09-04
type: ssot
last_updated: 2026-09-04
---

# docs last_updated保鲜 batch3-6（BET-Y1Q3-T10-201）

## 背景（Context）

docdate 扫描要求 docs 携带合法 `last_updated` 字段。BET-Y1Q3-T10-201 作为
batch3 试点，覆盖 20 个 `docs/superpowers/plans/**` 文件，只补 `last_updated`
保鲜字段，验证扫描口径可用，不碰业务逻辑，不一次全量改剩余文件。

## 目标（Goal）

给以下 20 个文件补 `last_updated: 2026-09-03` 并跑 batch3-6 保鲜验证：

- `docs/superpowers/plans/2026-08-08-phase4-federalization.md`
- `docs/superpowers/plans/2026-08-12-chatgpt-secure-mcp-routing.md`
- `docs/superpowers/plans/2026-08-12-documents-owner-job.md`
- `docs/superpowers/plans/2026-08-13-codex-exec-worker.md`
- `docs/superpowers/plans/2026-08-13-orchestration-contract-mvp.md`
- `docs/superpowers/plans/2026-08-14-supervised-blueprint-control-loop.md`
- `docs/superpowers/plans/2026-08-14-weijian-sanyi-status-consistency.md`
- `docs/superpowers/plans/2026-08-22-governance-convergence.md`
- `docs/superpowers/plans/2026-08-24-exact-capability-binding.md`
- `docs/superpowers/plans/2026-08-31-documents-runner-log-quarantine.md`
- `docs/superpowers/plans/2026-08-31-family-dashboard-runtime-state-and-hitl-writes-phase-b.md`
- `docs/superpowers/plans/2026-08-31-l4-machine-log-classification.md`
- `docs/superpowers/plans/2026-09-03-vision-to-bet-portfolio-v2.md`
- `docs/superpowers/plans/2026-09-03-w0-cockpit-portfolio-view.md`
- `docs/superpowers/plans/2026-09-03-w0-portfolio-coverage-graph-critical-path.md`
- `docs/superpowers/plans/2026-09-03-w0-portfolio-dogfood-canary.md`
- `docs/superpowers/plans/2026-09-03-w0-portfolio-legacy-bet-migration.md`
- `docs/superpowers/plans/2026-09-03-w0-portfolio-milestone-vision-gates.md`
- `docs/superpowers/plans/2026-09-03-w0-portfolio-projections.md`
- `docs/superpowers/plans/2026-09-03-w0-portfolio-v2-schema-compatibility.md`

## 非目标（Non-Goals）

- 不改文档正文语义，只补 `last_updated` 保鲜字段。
- 不碰业务代码与治理门禁逻辑。
- 不一次全量改剩余文件，本 bet 只做 batch3-6。

## 完成标准（Done When）

1. 上述 20 文件均有 `last_updated` 且格式合法（`YYYY-MM-DD`）。
2. docdate 扫描对上述 20 文件不再报缺失。
3. `bin/plan/bet-ledger.py lint` 通过，BET-Y1Q3-T10-201 结构合法。
4. 本 spec 的 binding（spec_ref / spec_version / content_digest /
   decision_ref）与 ledger 记录一致，digest 与文件 sha256 一致。

## 验证（Verify）

- `uv run --with pyyaml python bin/plan/bet-ledger.py lint` → exit 0。
- `grep -l last_updated docs/superpowers/plans/2026-08-08-phase4-federalization.md ...` → 20 文件均有输出。

## 决策引用（Decision Ref）

- `decision://accepted/BET-Y1Q3-T10-201`
