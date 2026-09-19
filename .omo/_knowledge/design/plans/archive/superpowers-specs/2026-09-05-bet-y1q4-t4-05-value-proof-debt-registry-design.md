---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T4-05
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
---

# BET-Y1Q4-T4-05: Spine Done 价值证明债清册与抽样回填 — Design Spec

## 1. Objective

扫描所有 `status=done` 的 spine/价值相关 bet，产出一份结构化债清册（docs/reports），
并对抽样 ≥5 条完成证据回填或书面豁免。

## 2. Deliverables

1. **债清册文件** `docs/reports/YYYY-MM-DD-value-proof-debt-registry.md`
   - 列出所有 `value_indicator_policy=false` 且 `completion_evidence.value=NOT_PROVEN/缺失` 的 done bet
   - 每条含：bet_id、track、title、vip 状态、value 轴状态、建议动作

2. **抽样回填** ≥5 条
   - 对每条抽样条目：补齐可复查证据或显式永久 NOT_PROVEN 理由（引用 D1/D6）
   - 回填写入 `docs/plans/3y-bet-ledger.yaml` 的 completion_evidence

3. **清册统计**
   - 总数、已回填数、NOT_PROVEN 豁免数、仍缺少数
   - 进入 OBJ-VALUE 相关报告

## 3. Non-Goals

- 不要求一次回填全部历史 done bet
- 不重做工程交付轴（engineering VERIFIED 保持）
- 不新增功能表面

## 4. Verification

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py show BET-Y1Q4-T4-05  # exit 0
ls docs/reports/*value-proof-debt-registry*  # exists
```

## 5. Decision Reference

This spec is created as part of BET-Y1Q4-T4-05 under the CMP-Y1-VALUE-PROOF campaign.
