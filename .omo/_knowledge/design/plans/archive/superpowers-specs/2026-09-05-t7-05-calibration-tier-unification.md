---
schema_version: specification/v1
spec_version: 1.0.0
title: T7-05 calibration 与五档 tier 语义统一
bet_id: BET-Y2Q1-T7-05
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
---

# T7-05 calibration 与五档 tier 语义统一

## 1. 目标

T7-03 归一后, 场景卡的 calibration 字段与 lifecycle 5 档 tier 字段同源 (.omo/standards/scene-card-lifecycle.yaml), 但语义分工不清:
- review 工具 (bin/ssot/scene-card-review.py) 输出 `lifecycle: assisted|...`
- lifecycle 标准定义 `min_calibration: 0.6` for assisted 升级
- 当前 0.65 calibration 在随卡字段, 是参考视图而非升级门

本 bet 统一二者为单一路径: calibration 字段升级为 assisted→supervised 升级门 (沿用现有 readiness 门), 5 档 tier 字段是单一 SSOT 状态。

## 2. In scope

1. `.omo/standards/scene-card-lifecycle.yaml` 写明 calibration 角色 (assisted→supervised 升级门, 与 readiness 互为参考)
2. `bin/ssot/scene-card-review.py` 输出的 `lifecycle` 字段枚举与标准 5 档 (draft/shadow/assisted/supervised/routine) 完全一致
3. weekly-review JSON 输出 schema 与 5 档枚举对齐 (消费方不变)

## 3. Out of scope

- 不改 readiness 门 (T7-02 刚固化)
- 不改 scene-card-lifecycle.yaml 的 5 档定义本身
- 不引入新 SSOT 文件

## 4. 验收

1. `python3 bin/ssot/scene-card-review.py status inbox-to-decision` → exit 0, lifecycle 字段在 [draft, shadow, assisted, supervised, routine] 中
2. `.omo/standards/scene-card-lifecycle.yaml` 写明 calibration 字段语义
3. weekly-review 消费方 (make report-weekly) 输出 schema 不变
