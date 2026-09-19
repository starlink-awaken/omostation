---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-18
---

# T7-07: documents-domain 场景卡批量 supervised→routine

## 目标

将 documents-domain 50 张 supervised 场景卡批量升档到 routine。复用 T7-02/T7-03/T7-04/T7-05/T7-06 已验证的推进模式。

## 范围

- 46 张 external_resource 场景卡: supervised→routine (含 knowledge-curation)
- 4 张 internal_pipeline 场景卡: 因结构缺陷保持 supervised (engineering-delivery/meeting-supervision/periodic-reporting/project-supervision)

## 前置条件

- 50 张场景卡均有 approval_state=confirmed
- 50 条 trial records 已写入 shadow-scene-trials.jsonl
- bet-ledger lint exit 0

## 非目标

- 不复活 BET-Y3H1-T7-01 / BET-Y3H2-T7-01
- 不修复 4 张 internal_pipeline 场景卡的结构缺陷
- 不修改 journey 定义
