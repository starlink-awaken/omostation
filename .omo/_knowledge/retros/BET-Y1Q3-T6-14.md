---
bet_id: BET-Y1Q3-T6-14
date: 2026-08-24
lifecycle: history
last-reviewed: 2026-08-24
status: candidate
owner: resident-governance
---

# BET-Y1Q3-T6-14 Retro — resident 常驻体系与治理接线全面深度复盘

> 交付: PR #2080 (merge 29998a6dc) — 9 维度复盘文档 `docs/reports/2026-08-24-resident-system-deep-review.md` + 台账 T6-14 条目 + Spec `docs/superpowers/specs/2026-08-24-resident-system-deep-review-design.md`
> 契约: run `20260824T013845Z-project-doc-change-3a0ec522` (project-doc-change / docs-agent)

## Q1 实际耗时 vs appetite

- appetite: 4 hours
- 实际: ~1 会话 (文档撰写 + Spec + 台账 + 契约收尾)
- 偏差: 契约收尾在共享 checkout 并发分支上被台账分支差异 (T6-14 不在并发分支) 与 spec 文件缺失阻塞, 额外消耗轮次 (refresh-packet 同步 hash + 临时台账/spec + affected receipt)。

## Q2 done_when 通过情况

| # | done_when | 状态 | 证据 |
|---|---|---|---|
| AC-01 | 复盘文档入库 `docs/reports/2026-08-24-resident-system-deep-review.md` | ✅ | PR #2080 merged |
| AC-02 | make gac-local-gate 全部 PASS | ✅ (main CI) | PR #2080 phase-gate pass; 本地共享 checkout 有并发 pre-existing FAIL 与 docs 无关 |

## Q3 打假 / 与 plan 不符的事实

- 复盘前传闻"resident 接线缺 MOF/SGF/BOS/agent-workflow 感知", 深度核查后发现 `bos-services.yaml` 实际已含 resident 4 条服务 (声明式加载), cockpit resident 已接线 (`_subcommands` + `cli.py:813` + `commands/resident.py`), agora BOS_URI_DOMAINS 已含 resident —— 真实缺口收敛为 5 项 (check 工具缺失 / governance-checks 未登记 / ci-surfaces 未登记 / agent-workflows registry 无 resident / 文档漂移)。
- `bin/ssot/resident-*` 兼容脚本在文档中被宣称存在, 实际已随 omo/resident 迁移删除 —— 文档漂移, 已在复盘中标出。

## Q4 净增减

- 新增 docs: 1 份 9 维度深度复盘报告 (docs/reports/)
- 新增治理数据: 台账 BET-Y1Q3-T6-14 条目 (candidate) + 1 份 Spec (docs/superpowers/specs/)
- 无运行时代码改动 (BET 定位为纯分析沉淀, non_goals 明确不改 resident 行为)

## Q5 下一个认领本 track 的 agent 需要知道什么

- resident 治理接线的真实缺口 (F1-F7 已完成, 详见复盘文档) 已全部闭环; 台账 T6-14 从 candidate 推进 done 需在 main 分支独立 PR 提交 retro 关联。
- 契约收尾陷阱: 共享 checkout 并发分支台账不含 main 新增 BET → claim 前先确认台账版本; run hash 随台账演化须 `refresh-packet` 同步; claim 的 affected receipt 用 `bin/gac/affected-graph.py --changed-projects workspace-root --output <path> --json` 生成。
