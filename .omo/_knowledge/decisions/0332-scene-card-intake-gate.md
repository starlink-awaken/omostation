---
id: ADR-0332
title: Scene Card 业务输入闸门与提案态归一化
status: archived
type: decision
owner: product-architecture
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - 0326-external-activation-preflight.md
  - 0317-workflow-requested-admission.md
---

# ADR-0332: Scene Card 业务输入闸门与提案态归一化

## 背景

已有候选发现、人工评审和 external activation preflight，但缺少一个统一的业务输入入口。没有
这个入口时，调用方容易把任意 JSON、原文或“已批准”字段直接拼接到后续准入链，形成隐式绕过；
同时，当前尚无需要立即激活的真实业务场景，不能用一个假场景证明执行链已经成立。

## 决策

1. 根仓新增 `bin/ssot/scene-card-intake.py`，将 `scene-card/v1` 输入归一为
   `scene-card-intake/v1`。它检查必填业务字段、3-10 个脱敏样本引用、需求/机会证据、激活证据、
   能力标识和 proposal-only 生命周期。
2. 输入中的原文、凭据和非不透明引用 fail-closed；输出只保留安全合同字段、引用、计数、摘要哈希
   和缺失字段，不输出原文。输入摘要哈希只用于幂等识别，不是业务证据。
3. 完整输入也只得到 `proposal_only`，下一步是运行 external activation preflight；缺失或越权
   激活字段得到 `blocked`。两种状态都固定 `activation=forbidden`，不写 OMO、不调用 provider、
   不创建 WorkflowRun。
4. Cockpit 增加 `POST /api/scene-cards/intake` 作为薄适配，只返回 intake projection 和
   `persistence=none`；它不新增审批状态机，不把输入成功渲染为执行成功。
5. 真实业务场景出现后，业务负责人仍需在同一张 Scene Card 上补齐消费者、责任人、权限、回滚和
   结果指标，再由 preflight 和既有 OMO admission 接管。没有真实场景时只验证输入闸门和 sandbox
   契约，不提前激活 OCR、知识图谱、预测模型或外部写入渠道。

## 验证

- 根仓 `tests/test_scene_card_intake.py`：5 项通过。
- Cockpit `src/cockpit/tests/test_api_scene_cards.py`：6 项通过。
- 根仓与 Cockpit 变更文件 Ruff 检查通过。
