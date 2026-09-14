---
schema_version: retrospective/v1
type: retro
title: 文档 SSOT 全量治理 — 去重/合并/指针化
bet_id: BET-Y1Q4-T6-17
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y1Q4-T6-17 复盘

## Q1 实际耗时 vs appetite？超出比例？

约 2.5 小时 vs 3 days appetite，约 10% 占比。主要时间在：T6-17 认领链门排障（spec binding 前置 + ecos 子模块未 init）+ 主仓 3216 文档扫描盘点。

## Q2 done_when 是否全部通过？哪条没过，为什么？

| 条目 | 结果 |
|------|------|
| 文档索引报告 | ✅ PASS（`docs/reports/doc-ssot-inventory-2026-09-05.md`，3216 文档分类盘点 + 重复/过时候选清单） |
| 重复内容合并 PR | ⚠️ 部分（3 个 completed ephemeral 顶层文档归档 `.omo/_knowledge/design/plans/archive/` + 2 retro 引用指针化；架构重复文档仅列入候选未合并） |
| AGENTS.md/CLAUDE.md 对齐更新 | ✅ PASS（AGENTS.md §2 加文档归档约定） |

第 2 条部分完成原因：架构重复文档（ARCHITECTURE-EVOLUTION × 2、STRATEGY-CONVERGENCE × 2 等）是高引用文档，合并需逐个人工复核，超出本次可交付范围，已在报告中列为候选。**3 days appetite 对 3216 文档的全量收敛不现实**——本 bet 交付了判定基线 + 高置信度归档，重复收敛作为持续工作。

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **T6-17 认领链门要求 spec binding**：candidate bet 无 accepted_specifications，`prepare_bet_execution` 无条件要求恰好 1 个 binding → SPEC_BINDING_REQUIRED 拦截 start。skill 说 candidate 可认领，但实际需先创建 spec + ledger 绑定（intent-to-spec 前置）。T6-01/02/03 也都没 spec（历史豁免）。**已在认领时补齐 spec**（`docs/superpowers/specs/2026-09-05-doc-ssot-governance-design.md`）。
2. **主仓文档规模远超预期**：3216 个 .md（非几百），全量逐文档人工判定不现实 → 采用目录级分类 + frontmatter type 统计的分层判定。
3. **顶层杂项文档已 'completed ephemeral'**：DOC_REFACTOR_SUMMARY/debt-audit-report/ECCP-HANDOFF 都是完成态一次性文档，应归档而非留存顶层（归档 3 个，低引用 1-3 次）。
4. **ROADMAP.md 被引 40 次**：虽是 ephemeral completed，但不能贸然归档（高引用），保留。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）

见 `bet-ledger.py surface`。主仓文件：+1 报告 +1 spec +1 AGENTS.md 编辑；-3 顶层文档（归档到 `.omo/_knowledge/design/plans/archive/` 为 rename 不增净文件数）；+2 retro 引用编辑。净表面积：文档收敛（顶层 -3），无新增代码/脚本/规则。

## Q5 下一个认领本 track 的 agent 需要知道什么？

- 认领 candidate bet 需先创建 spec + ledger accepted_specifications 绑定（intent-to-spec），否则 start 被 SPEC_BINDING_REQUIRED 拦截。
- worktree claim 超时会导致子模块空目录（omo/ecos），start 前检查 `projects/ecos/src/ecos/ssot/tools/work_packet_compiler.py` 存在。
- 文档治理的重复收敛是持续工作：报告列出的架构重复候选（ARCHITECTURE-EVOLUTION、STRATEGY-CONVERGENCE、SUBMODULE-PR 等）可开后续 bet。
- 归档顶层 completed ephemeral 文档到 `.omo/_knowledge/design/plans/archive/`（`.omo/_archive/` 被 .gitignore 忽略，新文件进不去）时，先查引用（ROADMAP 被引 40 次不可动，低引用才归档）。
