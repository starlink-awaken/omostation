---
type: report
title: 主仓 Markdown 文档 SSOT 判定盘点
date: 2026-09-05
owner: governance-agent
bet: BET-Y1Q4-T6-17
---

# 主仓 Markdown 文档 SSOT 判定盘点

> 盘点日期：2026-09-05 | 扫描范围：主仓（不含 projects/* 子仓，共 3216 个 .md）

## 1. 全量 type 分布

| type | 数量 | 判定 |
|------|------|------|
| ssot | 1249 | SSOT（正交唯一事实源，AGENTS/CLAUDE/ARCHITECTURE 等） |
| doc | 172 | 普通文档（有 owner 的生命周期文档） |
| ephemeral | 723 | 一次性/已完成文档（可归档候选） |
| retro | 453 | 复盘（知识库，非 SSOT） |
| decision | 37 | 决策记录（ADR 等） |
| audit | 40 | 审计记录 |
| report | 12 | 报告（含生成报告） |
| skill | 7 | 技能文档（.agents/skills） |
| adr | 17 | ADR 决策 |
| bet-retrospective | 68 | bet 复盘 |
| implementation-evidence | 44 | 实施证据 |
| collab-trail | 44 | 协作轨迹 |
| requirement-iteration-waiver | 27 | 需求迭代豁免 |
| runbook | 8 | 操作手册 |
| delivery-report | 8 | 交付报告 |
| no-frontmatter | 226 | 无 frontmatter（判定为普通/需人工标注） |

## 2. 顶层根目录文档

| 文档 | type | SSOT 判定 |
|------|------|-----------|
| AGENTS.md | ssot | SSOT |
| ARCHITECTURE.md | ssot | SSOT |
| BRIEF.md | ssot | SSOT |
| CHANGELOG.md | ssot | SSOT |
| CLAUDE.md | ssot | SSOT |
| CODE_OF_CONDUCT.md | ssot | SSOT |
| CONTRIBUTING.md | ssot | SSOT |
| DOC_REFACTOR_SUMMARY.md | ephemeral | 归档候选(completed ephemeral) |
| ECCP-HANDOFF.md | ephemeral | 归档候选(completed ephemeral) |
| GOVERNANCE.md | ssot | SSOT |
| LAYER-INDEX.md | no-frontmatter | 待标注 |
| README.md | ssot | SSOT |
| ROADMAP.md | ephemeral | 归档候选(completed ephemeral) |
| SECURITY.md | ssot | SSOT |
| SUPPORT.md | ssot | SSOT |
| SYSTEM-INDEX.md | ssot | SSOT |
| debt-audit-report.md | ephemeral | 归档候选(completed ephemeral) |

## 3. 按目录 type 分布（SSOT 判定概览）

| 目录 | 主要 type | 判定 |
|------|-----------|------|
| . | ssot=12, ephemeral=4, no-frontmatter=1 | 见分类规则 |
| .agents | ssot=33, no-frontmatter=11, skill=7 | 见分类规则 |
| .githooks | no-frontmatter=2 | 见分类规则 |
| .github | no-frontmatter=7 | 见分类规则 |
| .kilo | no-frontmatter=2, ssot=1 | 见分类规则 |
| .mimocode | no-frontmatter=4 | 见分类规则 |
| .omo | ssot=911, ephemeral=589, retro=453 | 见分类规则 |
| Plans | no-frontmatter=2 | 见分类规则 |
| aetherforge-archive | no-frontmatter=2 | 见分类规则 |
| artifacts | no-frontmatter=2 | 见分类规则 |
| bin | no-frontmatter=7, ssot=3 | 见分类规则 |
| data | no-frontmatter=3, debt=2, task=2 | 见分类规则 |
| docs | ssot=289, ephemeral=130, doc=49 | 见分类规则 |
| domains | no-frontmatter=3 | 见分类规则 |
| evidence | no-frontmatter=3 | 见分类规则 |
| lib | no-frontmatter=2 | 见分类规则 |
| locks | no-frontmatter=2 | 见分类规则 |
| protocols | no-frontmatter=3 | 见分类规则 |
| runtime | no-frontmatter=14 | 见分类规则 |
| scenarios | no-frontmatter=3 | 见分类规则 |
| spaces | no-frontmatter=5 | 见分类规则 |
| src | no-frontmatter=1 | 见分类规则 |
| tests | no-frontmatter=2 | 见分类规则 |
| tools | no-frontmatter=2 | 见分类规则 |

## 4. 重复/过时候选（需人工复核）

| 候选 | 依据 | 建议 |
|------|------|------|
| DOC_REFACTOR_SUMMARY.md | completed ephemeral，顶层冗余，被引 1 次 | 已归档 .omo/_knowledge/design/plans/archive |
| debt-audit-report.md | completed ephemeral，被引 2 次 | 已归档 .omo/_knowledge/design/plans/archive |
| ECCP-HANDOFF.md | completed ephemeral，被引 3 次 | 已归档 .omo/_knowledge/design/plans/archive |
| docs/ARCHITECTURE-EVOLUTION.md vs ARCHITECTURE-EVOLUTION-2026H2.md | 主题重复 | 合并/指针化 |
| docs/STRATEGY-CONVERGENCE-MASTER vs LANDING-PACKAGE | 主题重复 | 合并/指针化 |
| docs/SUBMODULE-PR-REVIEW-GUIDE.md vs SUBMODULE-PR-STRATEGY.md | 主题重复 | 合并/指针化 |

## 5. 判定规则（对齐 doc-ssot-contract）

1. **SSOT 文档**（type: ssot）：每份拥有一个正交维度，禁止重复维护运行时值（doc-ssot-lint 强制）。
2. **知识库**（.omo/_knowledge/*）：历史决策/复盘/审计，非 SSOT，检索噪音可控。
3. **生成文档**（docs/reports、docs/generated）：派生产物，勿手改。
4. **spec/plan**：生命周期文档，有 owner + frontmatter。
5. **completed ephemeral**：一次性交付记录，完成即归档候选。

## 6. 子仓说明

16 个子仓各自维护 .md，SSOT 判定需各仓 maintainer 配合（T6-17 risks 已记录）。本次仅盘点主仓。