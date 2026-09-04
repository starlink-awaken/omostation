---
lifecycle: history
owner: governance-team
last_updated: 2026-08-25
title: BET-Y1Q3-T6-14 复盘
type: retro
---

# BET-Y1Q3-T6-14 复盘

## Q1 实际耗时 vs appetite？

appetite=4h。实际约 1.5h（含环境排障：ecos 子模块坏 checkout 重置、workflow start 依赖链、affected-graph receipt 修正）。约 37%，远低于预算。

## Q2 done_when 是否全部通过？哪条没过，为什么？

全部通过（2/2）：
- 复盘文档入库 `docs/reports/2026-08-24-resident-system-deep-review.md` ✅（深化为 210 行实测支撑的 9 维度复盘）
- `make gac-local-gate` 全绿 PASS ✅（56 checks ALL GREEN，6 个 broken/known-unavailable skipped 环境性）
- workflow verify 4/4 PASS（doc-ssot-lint / gac-local-gate / doc-claims-check / lint）

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **三份 deliverable 已在 main 且被打薄**：spec 与复盘报告已由并发 agent 推入 main（PR #2077），但复盘报告只有 40 行占位（9 维度各 1-2 句）。真实工作不是"从零写"而是"把占位深化为真正的深度复盘"。
2. **ledger 声明的 spec digest 与 main 实际不符**：台账 `content_digest: af2e5547...`，实际文件 `7542b3ad...`。spec 文件入 main 后又被并发改过（或台账登记旧 hash），导致 workflow start 首次 SPEC_DIGEST_MISMATCH 失败。已把台账更新为实际值。
3. **E4 已提前解决**：bet evidence 描述"accepted-specifications 仅靠 legacy exception、新增第七份即 hard fail"，但实测 document-governance.yaml 已有原生 `accepted-specifications` surface（valid_statuses 含 accepted），doc-governance-check.py 支持它，25 份 spec 全过校验——E4 无需改动，仅验证。
4. **resident 运行时"接线完整、价值未兑现"**：health=recovered 但事件流 idle 9.25h、sediment 405 条产出 100% 为模板占位（"待补充五问"空复选框）、execute 角色全流仅 1 条 ExecutionRequested。系统管道建好但无真实事件与知识在流。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）

本 bet 仅 2 个文件净变更（其余 5 个写面文件已在 main，未改）：
- `docs/reports/2026-08-24-resident-system-deep-review.md`：40 → 210 行（+170）
- `docs/plans/3y-bet-ledger.yaml`：1 行 digest 修正（af2e5547 → 7542b3ad）

无新增文件、无新增 GaC 规则、无新增 ADR、无新增脚本。符合 Y1"做减法/不增表面积"主目标——本 bet 纯沉淀分析结论（non_goals 明确不改运行时），唯一"新增"是复盘报告本身的深化行数，属交付物内容而非表面积扩张。

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. **resident 体系治理接线已全部实测确认**：MOF digital_agent（tier=resident）、L0 CR-RESIDENT-STATUS-01/MOF-SYNC-01、Agora MCP resident_status/roles、cron 2min/5min、Makefile 12 目标、signal-sources personal-steward。做 resident 相关任务直接引用复盘报告 §0/§6 的实测基线。
2. **两大待办 follow-up（需另开 bet）**：① sediment 模板→完整知识晋升管线（promote 场景升迁落地，解决 405 条占位）；② 事件源自动接入 workflow 生命周期（解决 idle 空转）。decision 提案可观测出口也是候选。
3. **隔离 worktree 环境排障**：`gac-worktree.sh claim` 后 ecos 子模块常是坏 checkout（2110 个 D 状态），需 `git submodule deinit -f projects/ecos && git submodule update --init projects/ecos` 才能跑 work-packet compiler。workflow start 依赖 ledger 的 spec digest 与 main 实际一致，改了 spec 文件后必须同步更新 ledger。
4. **affected-graph receipt**：claim 写面需 `affected-graph.py --changed-projects <proj> workspace-root --output .omo/_delivery/affected-graph/<id>.json`（文档路径映射到 workspace-root 项目，必须包含它），receipt 是运行时文件不进 git。
