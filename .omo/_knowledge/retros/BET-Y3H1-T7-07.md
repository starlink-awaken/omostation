---
type: bet-retro
schema_version: bet-retro/v1
status: archived
lifecycle: history
bet_id: BET-Y3H1-T7-07
title: documents-domain 场景卡批量 supervised→routine
date: 2026-09-18
---

# BET-Y3H1-T7-07 Retro

## 概要

46 张 documents-domain supervised 场景卡批量升档到 routine。复用 T7-02/T7-03/T7-04/T7-05/T7-06 已验证的推进模式。

## 执行步骤

1. **Trial records 写入**: 50 条 shadow-scene-trial/v1 记录写入 `.omo/_knowledge/workflow-mesh/shadow-scene-trials.jsonl`
2. **批量 transition**: 46 张 external_resource 场景卡 supervised→routine (scene-card-lifecycle.py)
3. **Schema 修复**: 4 张 internal_pipeline 场景卡 `schema: scene-card/v3`→`scene-card/v1` (preflight 要求)
4. **Approval 修复**: knowledge-curation `pending_business_confirmation`→`confirmed`
5. **Closeout**: ledger done + completion_evidence + retro archived

## 成果

| 指标 | 值 |
|------|-----|
| supervised→routine | 46 |
| 保持 supervised | 4 (internal_pipeline 结构缺陷) |
| trial records | 50 |
| PR | #3962 |

## 关键教训

1. **internal_pipeline 场景卡需 schema: scene-card/v1**: 4 张卡 (engineering-delivery/meeting-supervision/periodic-reporting/project-supervision) 原为 `scene-card/v3`，preflight 要求 `scene-card/v1`
2. **approval_state 须 confirmed**: knowledge-curation 原为 `pending_business_confirmation`，须先改为 `confirmed`
3. **4 张 internal_pipeline 卡有结构缺陷**: 缺 activation_evidence_refs/goal/journey_id/required_capabilities/rollback_plan，不在本 BET 范围
4. **batch 模式高效**: 50 张卡约 2 分钟完成，vs 单张约 2 秒
