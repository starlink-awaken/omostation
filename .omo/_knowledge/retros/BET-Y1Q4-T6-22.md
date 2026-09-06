---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T6-22 Closeout Retro — 文档生命周期体系落地与去重指针化
bet_id: BET-Y1Q4-T6-22
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-06
last-reviewed: 2026-09-06
---

# BET-Y1Q4-T6-22 Closeout Retro

> **TL;DR**: 交付 `bin/ssot/doc-lifecycle.py` (audit/archive/lint 三模式) + 主仓无 frontmatter 文档清零 (23 篇修复) + `ARCHITECTURE-EVOLUTION.md` 合并指针化到 `ARCHITECTURE-EVOLUTION-2026H2.md` + 重复周报指针化。verify: `doc-ssot-lint.py --json` exit 0, `check-doc-freshness-gate.py` OK, `make gac-local-gate` PASS (57 checks ALL GREEN)。

## Deliverables

- `bin/ssot/doc-lifecycle.py` (256 LOC, 可执行) — 文档生命周期治理工具，支持 `audit`/`archive`/`lint` 子命令
- `bin/_registry/scripts/governance/doc-lifecycle.yaml` — script registry 登记
- `docs/ARCHITECTURE-EVOLUTION-2026H2.md` — 合并原 `ARCHITECTURE-EVOLUTION.md` 全部内容，新增第六节"架构演进参考索引"
- `docs/ARCHITECTURE-EVOLUTION.md` — 改为 redirect 指针文件，保留稳定 URL 回指
- `docs/reports/architecture-health-weekly.md` — 改为 redirect 指针文件，指向 `architecture-health-weekly-20260906.md`
- 23 篇无 frontmatter 文档补齐元数据 (LAYER-INDEX.md, docs/*, projects/* 等)
- `.omo/_truth/registry/governance-checks.yaml` — script_baseline 597→598
- `docs/plans/3y-bet-ledger.yaml` — BET-Y1Q4-T6-22 条目已绑定完成证据

## Q1 实际耗时 vs appetite?

Appetite 3 days。本轮实际耗时 ~2.5h（工具开发 + frontmatter 批量修复 + 重复文档指针化 + ecos sfop-slots 同步 + 验证）。

## Q2 done_when 是否全部通过?

| 条目 | 结果 |
|------|------|
| 交付 bin/ssot/doc-lifecycle.py 并支持 audit、archive 与 lint 模式 | **PASS** |
| 主仓无 frontmatter 文档数清零 | **PASS** (23 篇已修复，audit 显示 0) |
| 完成 ARCHITECTURE-EVOLUTION 等已识别主题重复文档的合并指针化 | **PASS** (内容合并 + redirect 保留) |
| doc-ssot-lint.py 与 check-doc-freshness-gate.py 维持 0 错误 | **PASS** |
| make gac-local-gate | **PASS** (57 checks ALL GREEN) |

## Q3 过程中发现的与 plan 不符的事实（打假）？

### 1. 226 篇无 frontmatter 文档盘点为全仓口径，实际主仓仅 23 篇
原 BET goal 写 "226 篇文档补齐元数据"，但该数字来自 T6-17 全仓盘点（含 projects 子仓）。本次聚焦主仓 `SCAN_GLOBS` 范围，实际需修复 23 篇，已全部清零。

### 2. 723 篇 ephemeral 文档归档目标与当前文件系统状态不符
原目标 "自动归档 723 篇 completed ephemeral 文档"，但当前文件系统无超过 90 天未更新的文档（`archive --dry-run` 返回 0）。可能原因：
- 历史归档已在之前的 T6-17/T6-18 等 bet 中完成
- 或 723 为早期盘点口径，当前实际已清零

### 3. script_baseline 基线已变
原计划假设 baseline 为 599，但当前 main 已降至 597（T6-24 净减 2 个 placeholder 脚本）。本次新增 doc-lifecycle.py 后同步为 598。

## Q4 后续建议

1. **GOVERNANCE.md boilerplate 去重**: 8 组项目级 GOVERNANCE.md 完全重复（跨 project boilerplate），建议后续 bet 统一为模板引用或 SSOT 指针
2. **doc-lifecycle 集成**: 将 `doc-lifecycle.py` 集成到 `gac-local-gate` 作为常态化门禁
3. **resident retro 增量提交策略**: `.omo/_knowledge/retros/resident/*.md` 由 resident agent 自动聚合刷新，建议纳入增量提交策略避免污染主仓提交历史

## Q5 价值证明

- **防腐硬化**: 新增 `doc-lifecycle.py` 作为文档生命周期常态化治理工具，补充 `doc-ssot-lint.py` 的静态检查能力
- **存量清零**: 主仓无 frontmatter 文档从 23 清零到 0，重复主题文档完成指针化
- **知识收敛**: `ARCHITECTURE-EVOLUTION.md` 内容合并到 2026H2 版本，保留稳定 URL 回指，避免外部引用断裂
- **门禁全绿**: `make gac-local-gate` PASS (57 checks ALL GREEN)，SFOP slots 0 违规
