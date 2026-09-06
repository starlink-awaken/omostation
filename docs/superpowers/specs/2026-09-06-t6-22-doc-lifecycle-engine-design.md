---
schema_version: specification/v1
spec_version: 1.0.0
title: "文档生命周期体系落地与主仓+Documents 存量文档深度去重指针化"
bet_id: BET-Y1Q4-T6-22
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-06
last-reviewed: 2026-09-06
type: ssot
last_updated: 2026-09-06
---

# 文档生命周期体系落地与主仓+Documents 存量文档深度去重指针化 (T6-22)

## Intent

基于 T6-17 盘点发现（`docs/reports/doc-ssot-inventory-2026-09-05.md`），交付自动化文档生命周期引擎
`bin/ssot/doc-lifecycle.py`，实现三种模式：

- **audit**：扫描主仓 .md，按 frontmatter 与 type 判定文档生命周期状态（无 frontmatter / completed ephemeral / 重复主题）
- **archive**：批量归档 completed ephemeral 文档到 `.omo/_knowledge/design/plans/archive/`，保留反向指针
- **lint**：校验归档不引发死链、重复指针一致、frontmatter 完整

同时完成主仓存量文档的去重指针化（226 篇无 frontmatter 补齐元数据、723 篇 completed ephemeral 归档、
3 组主题重复文档合并指针化），使 `doc-ssot-lint.py` 与 `check-doc-freshness-gate.py` 维持 0 错误。

## Architecture

```
bin/ssot/doc-lifecycle.py (新)
├─ audit    — 扫描主仓 .md, 按 type/frontmatter 分类报告 (JSON)
├─ archive  — 批量移动 completed ephemeral → .omo/_knowledge/design/plans/archive/ + 写指针
├─ lint     — 校验归档死链/重复指针/frontmatter (exit 0/1)
└─ 输出: JSON status envelope + 摘要

.omo/standards/doc-ssot-contract.md (更新)
└─ 补充生命周期规则: completed ephemeral 归档约定 + 去重指针化约定

docs/reports/doc-ssot-inventory-2026-09-05.md (更新)
└─ 反映执行后状态 (已归档/已补齐/已合并)
```

## Done Criteria

1. `bin/ssot/doc-lifecycle.py` 交付并支持 audit/archive/lint 三模式
2. 主仓无 frontmatter 文档数清零（226 篇补齐元数据）
3. 723 篇 completed ephemeral 文档归档到 archive 目录，保留反向指针
4. ARCHITECTURE-EVOLUTION 等已识别主题重复文档合并指针化
5. `doc-ssot-lint.py --json` 退出 0
6. `check-doc-freshness-gate.py` 退出 0
7. `make gac-local-gate` 全绿

## Non-Goals

- 不删除任何具有历史决策价值的 ADR 或 Retro
- 不破坏外部系统正在引用的稳定 URL 路径（归档必须保留反向软链/指针说明）
- 不改动 projects/* 子仓内文档（仅主仓，子仓由各 maintainer 自理）

## Risks

- L1: 归档与合并操作必须保留原相对路径的反向软链或指针说明文件，绝不允许引发已有代码或测试的死链（broken links）
- L1: 无 frontmatter 补齐时须按 doc-ssot-contract 判定 type，不得臆造 SSOT 归属
- L2: 批量操作前必须 dry-run 预览 + 计数确认

## Evidence

- 盘点依据: `docs/reports/doc-ssot-inventory-2026-09-05.md`（T6-17 产出）
- 226 no-frontmatter / 723 ephemeral / 3 组重复 为盘点基准
