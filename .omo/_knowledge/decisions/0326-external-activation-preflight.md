---
id: ADR-0326
title: 外部连接激活前置检查与只读提案边界
status: archived
type: decision
owner: architecture-governance
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../../docs/SCENE-CARD-REVIEW-RUNBOOK.md
  - 0325-external-route-admission-closure.md
---

# ADR-0326: 外部连接激活前置检查与只读提案边界

## 背景

外部目录观察、Scene Card 候选评审和 OMO admission 之前存在一个容易被人工拼接绕过的间隙：
业务方需要同时判断场景卡是否完整、所需能力是否在最新目录中可用，以及当前是否只能停留在
proposal-only。缺少统一投影时，目录的“可见”、候选的“已评审”和运行时的“可执行”容易被混为一谈。

## 决策

1. 新增根仓 `bin/ssot/external-activation-preflight.py`，输入完整 Scene Card JSON 和
   `external-resource-catalog/v1` 只读快照，输出 `external-activation-preflight/v1`。
2. Preflight 校验业务身份、结果指标、责任/审批、权限、回滚、脱敏样本、需求证据和必需能力；
   它同时将能力映射到目录候选，并区分 `blocked`、`proposal_only` 和
   `ready_for_admission_preview`。
3. Preflight 永远输出 `activation=forbidden`，不加载 provider、不读取原文、不写 OMO、不创建
   WorkflowRun、不改变 Agora admission。`ready_for_admission_preview` 只表示材料齐备，不能表示
   已获准执行。
4. Scene Card 或目录包含原始内容、凭据字段、非不透明引用、错误 schema 或非只读目录时，
   preflight fail-closed；输出只保留能力、资源 ID、可用性、生命周期和 reason code 等安全摘要。
5. 该门是外部真实场景激活前的统一准备面。没有真实消费者、结果指标和责任人时，系统继续使用
   候选评审与 preflight，不提前激活 OCR、知识图谱、预测模型或外部写入渠道。

## 验证

- 完整 Scene Card 与 available/degraded 目录输出 `ready_for_admission_preview`。
- 缺少样本/激活证据、能力不可用或 proposal-only 能力分别输出可解释阻断状态。
- 原始内容和非 opaque 引用被拒绝，且 CLI 不写输入目录或 OMO 状态。
- preflight、外部目录、Scene Card 候选和评审回归测试共 22 项通过。
