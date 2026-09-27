---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-03 specification
bet_id: BET-Y2Q4-T10-03
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-26
---


# BET-Y2Q4-T10-03 — 主仓文档元数据漂移治理（批次一）

## Intent

修复仓库文档治理审计在主仓 `docs/` 面发现的现有生命周期元数据漂移。审计基线为
2026-09-26 的隔离 `origin/main`：18 份 `docs/` 文档产生 19 条 finding；全仓
`doc-governance-check` 为 0 errors、157 warnings，所有 warning 均在已登记预算内。

每份文档的 `status` / `lifecycle` 必须依据正文、用途和引用语义判定；不得为了让检查通过而统一填值、更新无关日期或改动文档正文。

## Scope

- 修复 `docs/` 内这 19 份文件的元数据告警，保持其正文和历史含义不变。
- 运行文档生命周期、SSOT、链接和索引检查，确保门禁不回退。
- 不改变 warning baseline、预算、扫描范围或任何 GaC 规则。

## Explicit exclusions

- 不改 `.omo/` 历史/证据文档及其受治理状态。
- 不改 `projects/*` 子模块拥有的文档；后续按各子仓 owner 与仓库工作流处理。
- 不删除精确重复的 `GOVERNANCE.md` 模板副本；先由各项目 owner 确认其复制意图。
- 不归档、删除、移动文档，不改文档正文，不提交或推送。

## Acceptance

1. `doc-governance-check` 对 `docs/` 的 `missing_frontmatter` 与 `invalid_metadata` findings 均为 0。
2. 全仓 doc-governance warning 不超出现有基线/预算，error 仍为 0。
3. `doc-ssot-lint`、`doc-link-check`、`check-index-drift` 均通过。
4. 所有变更均限于本 spec 与其列明的主仓 `docs/` 元数据字段。

## Decision provenance

用户于 2026-09-26 明确同意创建此 BET 并继续，批准范围即本 spec 的主仓 `docs/` 首批修复与上述排除项。
