---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
---


# T7-08: assisted 场景卡 assisted→supervised→routine 两步推进

## 目标

将 4 张 assisted 场景卡 (knowledge-ingest/inbox-to-decision/meeting-to-delivery/research-to-insight) 推进到 routine。复用 T7-02~T7-07 已验证的推进模式。

## 范围

- 4 张 inbound 场景卡: assisted→supervised→routine (两步)
- 8 条 trial records (4 assisted-mode + 4 supervised-mode)

## 非目标

- 不修复 4 张 internal_pipeline supervised 卡的结构缺陷
- 不修改 journey 定义
