---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract

bet_id: BET-Y1Q2-T7-01
owner: human-principal
last_updated: 2026-08-24

risk_level: L1
human_gate: false
type: ssot
last_updated: 2026-09-03
---

# 工程交付 dogfood shadow 决策样本观测

## 目的

建立高频低风险、可绑定显式 reviewer credential 与 human adjudication 的真实
decision_outcome 样本源(工程交付场景)。产出**永不计入价值指标**(value_indicator_policy=False)。

## 决策样本链

```text
merged PR(真实)
  → consume-engineering-delivery(机器记录供给侧元数据)
  → engineering-delivery-review-queue(只读候选队列)
  → submit-engineering-delivery-review(人类裁决, HMAC 凭证绑定)
  → qualified-decision-outcome(jsonl, value_indicator_policy=False)
  → engineering-delivery-shadow-observer(7 日窗口 qualified 计数)
```

## 治理约束

- 机器记录供给侧: consume 只存 receipt + submitted feedback, 不产生 human verdict
- qualified outcome 仅由 human-review broker 创建: 需现有 workflow run + receipt + submitted feedback + HMAC principal assertion
- HMAC 签名: COCKPIT_ENGINEERING_REVIEW_SIGNING_KEY(env 或 .omo 文件 fallback)
- 主体验证: `_verify_principal_assertion`(binding_digest + signature + freshness)
- observer 7 日窗口计数 >= 20 为 done_when; value_indicator_policy=False 恒成立

## 验收

- lifecycle=shadow 场景卡
- 7 日窗口 >=20 条 qualified decision outcome(可关联非测试 human adjudication)
- observer verdict=PASS
