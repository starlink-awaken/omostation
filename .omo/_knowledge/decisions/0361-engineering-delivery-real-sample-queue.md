---
id: ADR-0361
title: Engineering Delivery 真实复核元数据进入 KEMS 双人标注队列
status: ACCEPTED
date: 2026-08-04
owner: governance-team
lifecycle: spec
last_updated: 2026-08-04
---

# ADR-0361: Engineering Delivery 真实复核元数据进入 KEMS 双人标注队列

## 背景

Phase 67 已经让责任人可以在 Cockpit 复核工程交付 receipt，但 M2 仍缺少从真实低风险运行到 KEMS 标注队列的稳定入口。
直接把人工 `adopted` 决策当成评测标签会产生标签泄漏，也会把机器/人工消费语义与评测真值混在一起。

## 决策

1. Kairon 新增一个只接受 OMO `engineering-delivery-review-queue/v1` 投影的转换和持久化入口。
2. 入口只允许固定 `engineering-delivery` 场景绑定、只读控制面和已复核行；pending 或未复核行不能进入真实样本队列。
3. 产物使用既有 `kems.adjudication-queue.v1`，只写稳定 sample ID、source SHA-256、`vault://redacted/` 引用、scenario 和 split，标签初始为空。
4. 新增 `engineering-delivery-review-v1` 标签合同，标签由两名独立标注员和一名独立 adjudicator 产生；`adopted/rejected/reviewed` 只保留为上游消费事实，不作为 gold label。
5. 输入、JSONL、SQLite 和证据文件递归拒绝原文、OCR、prompt、模型输出、自由文本和凭据；重复 source 元数据必须幂等，哈希冲突必须失败。
6. 本阶段不创建 evaluation manifest、不训练模型、不改变 Workflow Mesh 状态、不派发 OMO 任务、不激活 provider。

## 影响

- M2 获得从真实工程交付复核投影到双人标注队列的可重复路径。
- Kairon/KOS 继续拥有评测队列、标签校验和 adjudication 生命周期，OMO 继续拥有运行事实和消费反馈真相。
- 真实标注和裁决仍是人工执行项；在此之前，系统只能声明“队列入口可用”，不能声明真实评测集或模型准确率。

## 验证

```bash
cd projects/kairon
PYTHONPATH="packages/kos/src" uv run --no-project --with pytest pytest -q \
  tests/scripts/test_kems_build_engineering_delivery_queue.py \
  tests/scripts/test_kems_sync_engineering_delivery_queue.py
```
