---
status: accepted
lifecycle: spec
owner: governance-team
created: 2026-08-24
last_updated: 2026-08-24
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-08
type: ssot
last_updated: 2026-09-03
---

# Maturity Round 2 — G8: 治理演进专属 bet 机制

> 日期：2026-08-24
> 状态：accepted
> BET：BET-Y1Q3-T10-08
> 上游设计：docs/operations/90pct-maturity-design.md (Round 2, G8)

## 背景与问题

治理演进类工作（S1/S5/CONV-3 三次 blocked 实证）常走 waiver run 且无业务 bet 绑定，
导致 vision→retro closeout 硬门（chain-bind-check）拦截——因为 evaluate_closeout 对
status=ok 且无 bet_id 的 run halt missing_bet_binding。治理自进化本身就是"改进治理
机制"，不该强制绑定业务 bet，但也不能绕过闭环。

## 架构选择

在 `AGENT-BRIEF.md` 固化"治理演进登记专属 bet"流程：治理类改进必须先登记一个
T10-MATURITY 或 governance 类 bet（如 T10-07/08/09/10 本身就是治理演进 bet），
用该 bet 绑定 run，消除无 bet 的 waiver run。同时在 `chain-bind-check.py` 增加
**governance-bet 豁免识别**：当 workflow 是治理演进类（governance-audit /
governance-phase-*）且 ledger 存在匹配的治理 bet 时，无业务 bet_id 的 closeout
不 halt（治理演进闭环由 bet 本身承载）。

- 文档层：AGENT-BRIEF.md 新增"治理演进工作必须先登记治理 bet"流程段
- 检查器层：chain-bind-check.py 对治理 workflow 识别治理 bet（以 `BET-Y1Q3-T10-` 或
  track=T10-MATURITY 为治理演进标识）

## 验收标准

1. **[AGENT-BRIEF 含治理演进 bet 登记流程]**
   - 验证方式：grep "治理演进" docs/plans/AGENT-BRIEF.md
   - 证据类型：流程段存在

2. **[chain-bind-check 支持治理 workflow 无业务 bet 豁免]**
   - 验证方式：`python3 bin/plan/chain-bind-check.py` 对 governance-audit run 无业务 bet 的 closeout 不 halt
   - 证据类型：verdict ok

## 反指标

- 不改 observer-audit 豁免（保持窄豁免）
- 不豁免业务 run（只有治理演进 workflow 可无业务 bet）

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | 文档 only vs 文档+检查器 | 文档+检查器 | 光写文档不执行会复发, 检查器是机制化 |
| 2 | 新 workflow vs 识别治理 bet | 识别治理 bet | 不新增 workflow, 用现有 T10-MATURITY 标识 |

## 变更历史

| 日期 | 变更内容 | 变更人 |
|------|----------|--------|
| 2026-08-24 | 初始版本 (grill-me 设计树 G8) | agent |
