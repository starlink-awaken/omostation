---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-24
type: ephemeral
status: archived
---

# BET-Y1Q3-T4-01 价值轴证据清单（非 closeout）

- schema: value-axis-acceptance/v1
- bet: BET-Y1Q3-T4-01
- 轴: value
- 台账权威: **NOT_PROVEN**（`overall_state=blocked`，`human_gate=true`）
- 生成: 2026-08-22
- 纠偏: 2026-08-22 — 本文不是 closeout 证据，也不把 value 轴标 ACCEPTED

## 地位

本清单只索引仓库内已出现的样本文件。`validate_completion_evidence` 不得被
解读为「value=ACCEPTED 且 errors=NONE 即可 closeout」：台账矩阵仍是
`value=NOT_PROVEN`，且缺少矩阵要求的直接证据字段绑定。

完整 closeout 仍需三轴全绿 **并且** 写入 ledger，而不是写在本文件：

- value: ACCEPTED（未达成）
- engineering: VERIFIED（未达成，现为 IN_PROGRESS）
- operational: PROVEN（未达成，现为 DEGRADED）

## 相关文件（非权威）

| 证据 | 文件 | 说明 |
|---|---|---|
| real_signal | `real_signal.md` | 样本草稿，不推进矩阵 |
| human_verdict | `human_verdict.md` | 样本草稿，不推进矩阵 |
| revision | `revision.md` | 样本草稿，不推进矩阵 |
| time_burden | `time_burden.md` | 样本草稿，不推进矩阵 |
| attestation | `docs/operations/human-attestations/` | 签名附件若存在，仍不改 ledger |

## 投影

NorthStar / compound-attribution 在缺 principal 或 bound live receipt 时为
`unprovable`。禁止把 `current_week_qualifying_outcomes: 1` 当作当前权威。

## 结论

本清单不能用于 T4-01 done。权威见 `docs/plans/3y-bet-ledger.yaml`。
