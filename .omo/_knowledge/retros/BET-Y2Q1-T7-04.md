---
schema_version: retrospective/v1
type: retro
title: BET-Y2Q1-T7-04 Closeout Retro — omo phase15/16 死链清理 + ecos 第四家存储收口
bet_id: BET-Y2Q1-T7-04
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y2Q1-T7-04 Closeout Retro

> **TL;DR**: 实质性工作早 ship — omo + ecos 子模块 commit (e11b30a76) 已修复 6 处死链 + 给 scene-cards.yaml 加 SSOT 注记。本轮 closeout 写在工作树里的 ledger: 补 T7-04 专用 spec (因 spec frontmatter bet_id 必须等于 BET id, 复用 T7-03 spec 不被接受) + CE matrix + retro + flip status。verify: `rg -c "_truth/scenarios" projects/omo/src/omo/omo_phase15.py projects/omo/src/omo/omo_phase16.py` = 0 (PASS), gac-local-gate 57 checks ALL GREEN。

## Deliverables (跨仓)

- **omo 子模块**: `fix(phase15/16): redirect dead _truth/scenarios refs to real paths` — 6 处 deadlink 重定向 (commit 64671ea96)
- **ecos 子模块**: `docs(ecos): clarify scene-cards.yaml is schema/contract, instances in docs/scene-cards/` (commit d37951477)
- **主仓**: `fix(scene-cards): omo phase15/16 dead link cleanup + ecos registry scope note (BET-Y2Q1-T7-04)` (commit e11b30a76) — pointer bump + 合并来自 origin/main
- **本轮 closeout**:
  - `docs/superpowers/specs/2026-09-05-t7-04-omo-deadlink-ecos-registry-design.md` — T7-04 专用 spec (44 行, 4 段)
  - `docs/plans/3y-bet-ledger.yaml` — T7-04 entry 补 spec binding + CE matrix + flip status
  - `.omo/_knowledge/retros/BET-Y2Q1-T7-04.md` — 本 retro

## Q1 实际耗时 vs appetite?

Appetite 1 day。实质工作在子模块 commit (e11b30a76 by another agent) ~30 min。本轮 closeout ~20 min (spec + ledger + retro)。

## Q2 done_when 是否全部通过?

| 条目 | 结果 |
|------|------|
| omo 死链改指真实路径或删除引用 | **PASS** (3 处 research-pipeline + 3 处 knowledge-capture-search 重定向, rg -c = 0) |
| ecos registry 的定位结论落盘 | **PASS** (scene-cards.yaml 文件头加 SSOT 注记, 明确 schema/contract + 实例在 docs/scene-cards/) |

## Q3 过程中发现的与 plan 不符的事实（打假）?

1. **实质工作早已 ship**: 子模块 commits 64671ea96 (omo) + d37951477 (ecos) 都在 e11b30a76 合并进我的工作树。本轮不需要改任何 .py 或 .yaml 文件, 只需在主仓 ledger 里登记 CE + retro.

2. **多仓 closeout 模式已成熟**: 跟 T10-117 (kairon) 模式一样 — 实质在子仓, 主仓只做 ledger closeout. 但本 bet 与 T10-117 不同的是, 子仓 commit **已经在 e11b30a76 合并时 bump 到主仓**, 所以不需要单独的 "kairon PR #69 等合入" 步骤. 整个 closeout 是纯文档.

3. **ecos registry 4 家存储问题**: 原计划担心 ecos scene-cards.yaml 是 "第四家存储" (与 docs/scene-cards/ 重复). 实际是 schema/contract 文件, 与 docs/scene-cards/ 的 instance 文件不是同一类. 修复方案是文件头加 SSOT 注记, 不是删除或合并. 这种 "schema vs instance" 区分在治理文档中常见, 但易被忽略.

4. **Spec frontmatter bet_id 严格化**: 跟 T7-05 一样, agent-workflow start 校验 spec frontmatter bet_id 必须等于 BET id. 复用 T7-03 spec 不被接受. 教训: 写 T7-04 自己的 spec, 内容 80% 重复但必须独立.

5. **rg 验签命令的 0-hits 输出**: `rg -c "..." 2 file.txt` 没有匹配时输出空 (stderr 不报错), exit code = 1. 验证用 `2>&1 | head` 看不到 0, 容易误判失败. 实际是 PASS. 教训: 用 `; echo "exit: $?"` 或 `|| true` 后置判断.

## Q4 净增减

- 新文件 2: spec (44 行), retro
- 改文件 1: docs/plans/3y-bet-ledger.yaml (T7-04 entry)
- 子模块 + 合并 commit: 0 改动 (e11b30a76 已在工作树)

## Q5 下一个认领本 track 的 agent 需要知道什么?

1. **多仓 closeout 模式可复用**: 实质在子仓, 主仓只做 ledger. 主仓 PR 不必包含子仓 commit (它已是 base 的一部分). 当 claim 工作树已经 merge 过子仓提交时, closeout 工作极简.

2. **ecos registry scene-cards.yaml 是 schema 不是 instance**: 未来治理文档/registry 需明确 "schema/contract" vs "instance/data" 区分. 建议在 `.omo/standards/registry-classification.md` 加全局约定, 避免每次都临时澄清.

3. **omo phase15/16 后续**: omo 还有 phase1-14 没扫, 可能也有 _truth/scenarios 引用. 但本 bet 限定 phase15/16, 其他 phase 是 follow-up. 建议下一个 bet: `omo phase1-14 deadlink audit + cleanup`.

4. **rg 验证命令的鲁棒性**: `rg -c PATTERN FILE` 0 hits → exit 1, 易混淆. 建议 gate check wrapper 兼容 "0 hits = pass" 语义.

## Closeout refs

- run: `20260905T234519Z-project-code-change-0cb57fd6`
- branch: `work/bet-y2q1-t7-04`
- spec: `docs/superpowers/specs/2026-09-05-t7-04-omo-deadlink-ecos-registry-design.md` (accepted, T7-04 专用)
- prior delivery: e11b30a76 (本工作树已含) by another agent — fix omo deadlinks + ecos registry note
- verify: `rg -c "_truth/scenarios" ...` = 0 (PASS); gac-local-gate 57 checks ALL GREEN
- dependency: T7-03 (存储归一)
- 被依赖: 无 (T7-04 是收口, 不再衍生)
