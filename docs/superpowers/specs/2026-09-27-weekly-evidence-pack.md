---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-27
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: 交付周报证据包 — 2026-09-20→09-27 真实交付记录 → principal 可签发周报
bet_id: BET-Y2Q4-T4-02
---

# BET-Y2Q4-T4-02 — 交付周报证据包（业务首单）

## 授权链

- BET-Y2Q4-T4-01-DECISION：principal 2026-09-27 会话内选择 **② 周报证据包，现在开工**
  （decision_ref: `decision://accepted/BET-Y2Q4-T4-02`，铸造记录即独立回执）
- 已确认输入：2026-09-20→09-27 workspace 交付记录（主仓 345 commits、PR #4376–#4429、
  7 个复盘 BET 关单、ADR-0456 批准）；渠道：docs/reports/ 报告 + 会话摘要；签发者：principal 本人

## 目标

产出一期 principal 可签发的**交付周报 + 逐项证据包**：
每条完成/阻塞声明锚定可核验来源（PR 号 / commit / ledger id），报告含
证据索引节与证据完整率；**principal 签发为价值门槛**——未签发不记价值（value 保持
NOT_PROVEN）。人工基线对比项留槽（用户自估分钟数，未提供则如实标 UNPROVABLE，不填假数）。

## 写面

`docs/reports/weekly-2026-09-20-27.md`、`.omo/tasks/planned/**`（决策卡状态落账）、
`docs/plans/3y-bet-ledger.yaml`、本 spec、retro。

## 验收（done_when 摘要）

1. 周报落 `docs/reports/weekly-2026-09-20-27.md`：覆盖 09-20→09-27 全部主仓合并 PR
   （含多 agent 并行线），每条声明带锚；
2. 证据完整率 = 带锚声明 / 总声明 = 100%，报告内附证据索引节；
3. 决策卡状态落账（已决策 ② + 回执指向本 BET）；
4. principal 签发节留槽：签发记录（日期 + 确认人）交付后回填；未签发时 value 如实 NOT_PROVEN；
5. retro（含签发请求时点与人工基线槽位状态）。

## 红线

- 报告只陈述可核验事实；无锚的判断句一律标注"推断"或删除（D1）；
- 人工基线未提供时该项 UNPROVABLE，禁止编造基线分钟数（D6）；
- 签发前不得把本报告计为已创造价值；
- 不改写历史 PR/ledger 记录（只引用）。

## verify

- 抽 3 条声明的锚原样核验（gh pr view / git show）→ 与声明一致
- `python3 bin/plan/bet-ledger.py lint` → 不引入新错误
- `make gac-local-gate` → exit 0
