---
type: bet-retro
schema_version: bet-retro/v1
status: archived
lifecycle: history
bet_id: BET-Y3H1-T7-08
title: assisted 场景卡 assisted→supervised→routine 两步推进
date: 2026-09-18
owner: unassigned
---

# BET-Y3H1-T7-08 Retro

## 概要

4 张 assisted 场景卡 (knowledge-ingest/inbox-to-decision/meeting-to-delivery/research-to-insight) 两步推进到 routine。

## 执行步骤

1. **Trial records**: 4 条 assisted-mode + 4 条 supervised-mode 写入 shadow-scene-trials.jsonl
2. **Step 1**: assisted→supervised (4 transitions)
3. **Step 2**: supervised→routine (4 transitions)
4. **Closeout**: ledger done + completion_evidence + retro archived

## 成果

| 指标 | 值 |
|------|-----|
| assisted→supervised | 4 |
| supervised→routine | 4 |
| trial records | 8 (4 assisted + 4 supervised) |
| PR | #3966 |

## 场景卡全景 (post T7-08)

| 级别 | 数量 | 变化 |
|------|------|------|
| routine | 63 | +4 |
| supervised | 4 | 不变 (internal_pipeline) |
| assisted | 0 | -4 |
| draft | 0 | 不变 |

## 关键教训

1. **两步推进模式**: assisted→supervised→routine 需分别写 trial records (mode 匹配当前阶段)
2. **batch 高效**: 4 卡 × 2 步 = 8 transitions, 约 1 分钟完成
