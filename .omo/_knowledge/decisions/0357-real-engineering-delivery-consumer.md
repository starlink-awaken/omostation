---
id: ADR-0357
title: Engineering Delivery 真实元数据消费者与 Workflow Mesh 回执顺序
status: ACCEPTED
date: 2026-08-03
owner: governance-team
lifecycle: spec
last_updated: 2026-08-03
---

# ADR-0357: Engineering Delivery 真实元数据消费者与 Workflow Mesh 回执顺序

## 背景

Phase 63 已具备 manifest-bound Shadow Evaluation 报告，但真实低风险消费者仍缺少连续的 receipt 和 outcome feedback。工程研发交付
是当前唯一具备稳定、可脱敏、可回溯证据的低风险场景：仓库、PR、merge SHA、CI 和 Workflow Mesh 运行都能形成明确引用。

如果消费者直接创建 WorkflowRun、替调用方准入或在 PR 合并后补写任意 EvidenceRecorded，会混淆“真实元数据消费”和“真实业务执行”，
并违反 Workflow Mesh 的 append-only 状态顺序。

## 决策

1. 在 OMO 增加独立的 `engineering-delivery-consumption/v1` broker，并挂到现有 `omo external-resources` CLI。
2. 消费者只接受已脱敏的交付摘要：delivery ID、repository ref、PR URL、merge SHA、合并时间和证据引用；原文、自由内容、凭据和未知字段一律拒绝。
3. 调用方必须提供已存在且场景绑定为 `engineering-delivery / intent-to-evidence / verified_delivery_lead_time` 的 WorkflowRun。
   消费者不创建 WorkflowRun、不执行 admission、不启动 worker、不调用 provider，也不自动晋升。
4. 在 WorkflowRun 为 `succeeded` 且尚未进入 `WorkflowVerified`、`PRMerged` 或 `WorkflowClosed` 时，先通过既有 receipt broker 写 `EvidenceRecorded`，
   再通过既有 outcome broker 写 `reviewed`/`adopted` 等消费反馈；后续人工验证和合并事件沿原生命周期继续推进。
5. 重复 delivery ID 使用既有幂等键；已进入后续状态的重试只有在相同 receipt 已存在时才允许通过，否则 fail-closed。
6. 输出固定声明 `proposal_only`、`activation=forbidden`、`provider_invocation=false` 和 `automatic_promotion=false`。该证据不等同于真实业务结果，
   仍须经过人工复核、双人标注、adjudication 和脱敏 manifest 才能进入 M2/M6。

## 影响

- Workflow Mesh 获得第一条可执行的真实工程交付元数据消费路径，复用既有 receipt/outcome 契约，避免第二套状态机。
- 事件顺序清晰：消费者必须在验证/合并/关闭前写入 receipt；后续重试保持安全幂等。
- 工程 dogfood 不再被误报为业务 provider 激活、OCR 质量或预测模型准确率。
- 如果未来要消费真实外部业务场景，必须复用同一回执边界，并新增场景级 ADR、权限、回滚和人工放行证据。

## 验证

```bash
cd projects/omo
uv run --no-project --python 3.13 --with pytest --with pyyaml pytest tests/test_engineering_delivery_consumer.py -q
uv run --no-project --python 3.13 --with ruff ruff check src/omo/engineering_delivery_consumer.py src/omo/omo_external_resources.py tests/test_engineering_delivery_consumer.py
```
