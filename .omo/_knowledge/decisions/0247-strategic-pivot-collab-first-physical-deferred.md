---
id: ADR-0247
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last_updated: 2026-07-26
related:
  - 0414-physical-multihost-tension-resolution.md
  - 0210-three-year-strategy-execution-convergence.md
  - 0228-physical-hosts-failclosed.md
  - 0235-c1-role-directory.md
  - 0236-c2-collab-protocol.md
  - 0237-c3-gbrain-blackboard.md
supersedes: []
amends:
  - 0210-three-year-strategy-execution-convergence.md
  - 0228-physical-hosts-failclosed.md
---

# ADR-0247: 战略转向 — 多 agent 协作优先, 物理多机 DEFERRED (补立)

## Context (补立原因)

2026-07-24 做出方向级决策: 兑现期主轴重排为**多 agent 协作深化优先**,
物理多机达标 **DEFERRED** (机会窗口, 不设时间表), 撤销物理底座周提醒.
该决策已被所有后续工单执行 (P81 C 波协作主轴 / P82 §B 治理预算 40/40/20),
但**未立 ADR 文件** — 起草时与 0233 撞号, 删除后引用改指 "ADR-0235",
而 0235 号后被 C1 角色目录占用, 形成悬空引用.

这是 decl-exec-gap 实例: 决策被执行但未记录. 本 ADR 补立追认既成事实.

## Decision

1. **多 agent 协作优先**: 兑现期主轴 = 协作深化 (ADR-0236 协议 + ADR-0237 黑板),
   占预算 ≥40% (P82 §B). 物理多机不占主轴.
2. **物理多机 DEFERRED**: 不设时间表, 不占预算, 不再周提醒. macmini 可达但测量 hang
   (两端 commit 错位), 待插网线顺手跑 G-DEL.3 wired 重测.
3. **撤销物理周提醒**: needs-human-p80-physical-hosts 不再 weekly reaffirm
   (amends ADR-0228 D3 suspend-weekly).
4. **amends ADR-0210**: 三年三阶段中, 物理多机达标从"兑现期硬指标"降级为"机会窗口".
   协作深化 (G-DEL.2b 已 PASSED ADR-0232) 成兑现期核心.

## 追认既成事实 (decision date 2026-07-24)

- P81 C 波 (PR #510 5角色协作 + PR #523 Round 3 C2 协作管线) 照此决策走
- P82 §B 治理预算 40/40/20 (协作 ≥40%) 照此决策
- 物理底座 needs-human 卡 (p80-physical-hosts / physical-recovery) 保留但不再周提醒

## 悬空引用修正

历史工单中 `ADR-0235(协作主轴)` / `ADR-0235 D2 三条线` 悬空引用 (0235 实为角色目录),
应改指本 ADR-0247 (协作主轴 / 物理延后). 指"角色目录 C1"的保留 0235.

## Confirmation

- next-adr-id 占号 p82-stage-a-s1 (无撞车)
- amends ADR-0210+0228 明确
- 悬空引用修正后 adr-coverage.py 通过

## Status

**ACCEPTED** (2026-07-26, 补立追认 2026-07-24 既成事实).

## Amend · 协作适用面边界 (2026-07-29 · human-delegated D2)

> 凭据: `.omo/_control/2026-07-29-human-delegated-decisions.md` D2  
> 证据: A2 多 agent 真 dispatch **3 类型**负证据（ordered / coupled+write / independent+write）+ R1 纯 text；  
> 简单独立批量 = **D2 政策授权**，**非**已闭环的多 agent 墙钟正收益（5.4x 作废；batch5 仅微基准已 demote）。  
> SSOT: `.omo/_knowledge/audits/2026-07-29-p86-a2-collaboration-gain-map.md` · ADR-0289 shortfall

1. **主轴地位保留**: 多 agent 协作优先（本 ADR Decision §1）**不变**；物理多机仍 DEFERRED。
2. **适用面收窄（硬边界）**: 协作管线**仅**用于「简单独立批量」
   （A1: independent + none/read + well_defined）— **政策允许**，多 agent 真 dispatch 正收益 **未闭环**。
3. **明确不适用**: 分析 / 方案设计 / 审查 / 调试 / 思考性设计 → **单 agent 直做**，
   不得默认多角色管线（C1 五角色在思考性任务上同界；A2 类型 2–4）。
4. **产能目标**: 月真实任务 **15**（完成率 ≥85%）；P84 旧爬坡 30→45→60 **作废**，
   不得作门禁。详见 BRIEF C 波节 + ADR-0287。
5. **不授权**: D4 四项（涌现实装 / 物理多机达标宣称 / KOS 新源 / BET-3b90 走查）仍须人类逐项拍板。

**Amend status**: ACCEPTED 2026-07-29 (delegated execution E5)；措辞对齐 #620 于 2026-07-29 (ADR-0290)。
