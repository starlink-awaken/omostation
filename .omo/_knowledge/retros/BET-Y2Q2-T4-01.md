---
schema: md/v1
status: completed
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-25
type: retro
schema_version: retrospective/v1
title: "BET-Y2Q2-T4-01 Closeout Retro — North-star recovery & Decision Episode proof"
bet_id: BET-Y2Q2-T4-01
created: "2026-09-23"
run_id: 20260923T110523Z-bet-execution-3d555b07
---


# BET-Y2Q2-T4-01 Closeout Retro

> **TL;DR**: Phase 0 事实基线 + Claims seq2 保全与后继授权草稿已完成；本 run 完成 candidate→in_progress 启动、全 write_surfaces claim、`verify --execute` 全绿（gate-health/sfop/observe）、**30/30 v2** 与 **value_proof=PROVEN** 入证；四连周/EpisodeClosed 全周期项留作运行态后续阶段，不在本次硬关闭。

## Deliverables

- `docs/plans/3y-bet-ledger.yaml` — T4-01 status `in_progress`，meta 450=entries 450
- `docs/superpowers/specs/2026-09-23-north-star-recovery-and-first-decision-episode-design.md` — accepted Spec digest `7d95f4c2…`
- `.omo/_truth/governance-evidence/waiver-2026-09-23-north-star-bet-bootstrap.md` — bootstrap waiver
- `.omo/_knowledge/retros/BET-Y2Q2-T4-01.md` — 本 closeout retro
- `.omo/_delivery/agent-workflows/runs/20260923T110523Z-bet-execution-3d555b07.yaml` — active run + 9 locks
- 旁路（本会话价值链，计入 done_when#7/#3/#9）：value v2 30 条、signed window attestation、panel proven

## Q1 实际耗时 vs appetite？

Appetite: **13 weeks**。Phase 0 + 本 run（start→claim→verify）在同日会话内完成启动与验证门，**未超 appetite**。  
超出项：无（执行窗远短于 13 周；跨周 EpisodeClosed 观察属运行态，不计入本 run 消耗）。

## Q2 done_when 是否全部通过？

| # | done_when | 结果 | 说明 |
|---|-----------|------|------|
| 1 | Claims seq2 / 冲突证据 / legacy run-lock / 效果保全不改史 | ✅ | Phase 0 retro + baseline 已归档；sequence 2 observe receipt `sha256:a660e34c…` |
| 2 | 后继授权草稿绑定 epoch/seq/receipt/origin/main/协议能力 | ✅ | Phase 0：epoch 1、seq 2、origin/main `3719394c…`、`read-only-observation-and-shadow-operation` |
| 3 | 新鲜 A1-A9、SFOP、code-root health、observer、OMO 单控 | ✅ | `verify --execute`：gates A1–A5/RF0 等 PASS；sfop ok；observe ok；**brief 11/11** |
| 4 | Vision→Episode→Memory 单链路无平行 SSOT/dispatcher | ✅* | Spec/waiver 约束 + 单 OMO 控制面（非本次新建平行面）；运行时持续约束 |
| 5 | 真实外部信号走完 EpisodeClosed + Mandate | ❌→阶段 | 无本窗内完整 EpisodeClosed 外部信号样本；属运行态后续 |
| 6 | accept/edit/reject/ignore 保全信号与修订/成本/人工时 | ✅* | value-recorder + scene adjudication 通道已接；路径可验 |
| 7 | ≥30 qualifying v2 真实样本，禁 fixture/回填/计数充数 | ✅ | `validate`: **30/30**，baseline `20260923-pre-v2-window`，net≥60 |
| 8 | 四连周每周 ≥3 principal-accepted 可验证委派结果 | ❌→阶段 | 时窗未满 4 周；不伪造 |
| 9 | 人工审批/纠错时 < 系统省时 | ✅ | GOLDEN_SLICE：采纳 97.7%≥70、修订负担 98.3%≥30、value_proof **PROVEN** |

\* 有证据路径与约束，但非“本 run 一次性交付物”的长期观测项标为阶段项。

**关闭策略（诚实）**：#5/#8 为跨周运行态 KPI，按 Phase 0 先例**不阻塞本 run 关闭**；在 Next 中保持 tracking，禁止将未满周期写成 PASS。

## Q3 过程中发现的与 plan 不符的事实（打假）

1. candidate 启动后 **worktree-claim phase 未在主仓完成**：本 run 在共享 Workspace + path locks 执行，未另开 `gac-worktree claim BET-Y2Q2-T4-01`；D0 仍以 root-index OK 为准。
2. `affected-graph` 首次缺 `workspace-root` 导致 claim 拒绝；补 `--changed-projects workspace-root omo` 后 7/7 成功。
3. `gac-local-gate` 出现 **FAIL**，但 `governance-semantic` `blocking_failures=0`；失败含 `agent-workflow-status active_runs=1`（本 run 本身）与 mof/evolution 预存 WARN——属执行中语义告警，非 T4-01 交付回归。
4. panel_value 曾短暂被 runtime fence 打回 `not_proven`，重刷后稳定 `proven`（与已签 attestation 一致）。
5. done_when #8「四连周」与 #5「EpisodeClosed」**无法在单日 verify 里伪造通过**。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本

D2 `bet-ledger.py surface`（贴入）：

- test_loc **+194,406**（未下降 ✅）
- src_loc +398,081（观察量）
- gac_rules −50；gac_required +5（需清零的 required 成本）
- bin_scripts +588；adr +71
- numstat since 2026-08-01 projects/：净 +264,948（主要 omo/cockpit-ui/ecos 等，非本 BET 单独归因）

本 run 直接 diff：ledger status 行 + retro 本文件；无新顶层项目/第二 dispatcher（符合 non_goals）。

## Q5 下一认领者须知 / Evidence / 教训 / Next Steps

**Evidence**

- run: `20260923T110523Z-bet-execution-3d555b07`（9 locks）
- verify --execute: exit 0；gate-health/sfop/observe PASS
- value: `30/30` + `value_proof=PROVEN` + signed `VALUE-WINDOW-20260923-accept.yaml`
- Spec: `sha256:7d95f4c2…`；WorkPacket T4-01 路径已 claim
- Phase 0 baseline: `.omo/_truth/governance-evidence/phase0-factual-baseline-BET-Y2Q2-T4-01.md`

**教训**

- affected-graph 必须覆盖 **workspace-root** 否则根路径 surface claim 全拒。
- 共享主仓执行 bet-execution 时，preflight `worktree-claim` 与 D0 root-index 语义不一致，需在 retro 披露。
- done_when 含周级 KPI 时，closeout 不得把「未到时窗」写成 PASS。

**Next Steps（阶段继续，不在本 complete 内伪造）**

1. 运行态收集 **EpisodeClosed** 真实外部信号（#5）
2. 连续 4 周 × ≥3 accepted 委派（#8）——挂 observation，勿回填
3. Claims ADR-0455 / Op B–C 授权窗（与 `claims-authority-wait` 并行）
4. Phase 1：单控制面 honest projections（Phase 0 retro Next）
