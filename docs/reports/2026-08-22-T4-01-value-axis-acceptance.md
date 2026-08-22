# BET-Y1Q3-T4-01 价值轴报告（非 ledger 真相）

- 报告编号: VALUE-ACCEPTANCE-Y1Q3-T4-01
- 生成时间: 2026-08-22
- 纠偏时间: 2026-08-22
- 验收对象: BET-Y1Q3-T4-01「真实个人价值证据脊柱」价值轴(value)
- 文件地位: **草稿 / 非权威诊断**。本文不推进 `completion-evidence-matrix`，
  不把 value 轴写成 ACCEPTED，也不把 BET 标为 done。
- 权威: `docs/plans/3y-bet-ledger.yaml` 的 completion-evidence-matrix/v1

| 轴 | 台账权威（2026-08-22） |
|---|---|
| engineering | `IN_PROGRESS` |
| operational | `DEGRADED` |
| value | `NOT_PROVEN` |
| overall_state | `blocked` |
| status | `in_progress`（`human_gate: true`） |

PR #1876 曾把本文件写成 **ACCEPTED(通过)**。那是报告草稿，不是 ledger 真相。
后续 agent 不得依据本文、`value-evidence/` 或 `human-attestations/` 单独把
value 轴翻成 ACCEPTED，或把 T4-01 closeout 成 done。

## 1. 范围

本文只说明：仓库里出现过一组价值样本文件，以及它们**不能**代替台账。
工程轴与运行轴仍按矩阵取证，不在本文范围内推导为 VERIFIED / PROVEN。

依据:

- spec: `docs/superpowers/specs/2026-08-20-value-proof-truth-rebaseline-design.md`
- 矩阵: `#1832` completion-evidence-matrix/v1
- 纠偏先例: `#1831` 缺 credential-bound attestation 仍把 BET 标 done，已被 `#1832` 撤回

value=ACCEPTED 需要矩阵字段 `real_signal` + `human_verdict` + `revision` +
`time_burden`，且不得绕过 `human_gate`。单份 Markdown 或 YAML 声明不够。

## 2. 仓库内相关文件（非权威）

下列路径是样本/附件，不是 completion-evidence-matrix 的写入面：

| 路径 | 作用 |
|---|---|
| `docs/operations/value-evidence/BET-Y1Q3-T4-01/` | 样本草稿 |
| `docs/operations/human-attestations/BET-Y1Q3-T4-01-accept.yaml` | 人类签名附件（若存在） |
| `docs/operations/human-attestations/BET-Y1Q3-T4-01-value-acceptance.yaml` | 绑定本报告的附件（若存在） |

附件即使带 SSH 签名，也只证明「有人签过某段消息」。它们不能：

- 改写台账 `value` / `overall_state`
- 覆盖 NorthStar / compound-attribution 投影
- 代替三轴同时满足的 closeout

## 3. 运行投影（AC-07 / AC-09）

本机只读投影在缺少 `principal_id` 或 bound live receipt 时必须 fail-closed：

- `bin/bc-os/north_star_meter_v2.py` → `status: unprovable`（`principal_id_required`）
- `bin/gac/compound-attribution-report.py` → `compound-attribution-report/v2`，
  `personal_value` 与成本/加速等均为 `UNPROVABLE` / `unproven_claims`

#1876 原文中的 `current_week_qualifying_outcomes = 1` **不是**当前投影权威。
未知量保持 `unknown` / `unprovable` / `not_connected`，禁止用 PR、BET 数、
测试数或自报 completed 填充。

## 4. 隐私与样本（AC-08 提醒）

若后续补真实低敏样本：不得持久化正文、绝对路径或凭证材料。
本文不声称已经走通 `SignalReceipt → never-send → human verdict →
RevisionReceipt/OutcomeFeedback` 全链。

## 5. 结论

T4-01 价值轴仍为 **NOT_PROVEN**。本文是对 #1876 假绿的纠偏，不是验收通过。

整体 closeout 仍要求：

1. engineering=`VERIFIED` 且带矩阵要求的直接证据
2. operational=`PROVEN` 且带 live canary / fresh receipt / replay / cleanup
3. value=`ACCEPTED` 且带矩阵直接证据 **加上** credential-bound human attestation
4. `human_gate` 由本人完成，agent 不得代签、不得伪造 `ssh-keygen -Y`

---
*纠偏说明: Markdown 报告不是 ledger。权威以 `3y-bet-ledger.yaml` 为准。*
