---
title: Scene Card 候选人工评审运行手册
status: active
type: runbook
owner: product-architecture
last-reviewed: 2026-08-02
related:
  - ./WORKFLOW-MESH-IMPLEMENTATION.md
  - ./scene-card-candidate-seeds.yaml
  - ../.omo/standards/scene-card-candidate.schema.yaml
lifecycle: entry
---

# Scene Card 候选人工评审运行手册

## 目的

本手册把候选发现结果交给人工审阅，形成可追踪的 proposal-only 回执。它解决的是“候选已经
被发现，但当前没有业务确认，系统应该如何正确停留”的问题，不是连接激活流程。

## 运行

先生成候选投影，再把指定候选送入评审队列：

```bash
uv run --with pyyaml python bin/ssot/scene-card-candidates.py --root . \
  | uv run python bin/ssot/scene-card-review.py \
      --candidate-id scene-candidate:engineering-delivery
```

人工决定时使用 `request_evidence`、`reject` 或 `approve`，并提供不透明的 reviewer ref 和
简短备注。备注只生成哈希，不进入回执正文：

```bash
uv run --with pyyaml python bin/ssot/scene-card-candidates.py --root . \
  | uv run python bin/ssot/scene-card-review.py \
      --candidate-id scene-candidate:engineering-delivery \
      --decision request_evidence \
      --reviewer-ref operator://redacted/reviewer-1 \
      --note "补充真实消费方、结果指标和脱敏样本引用"
```

## 状态解释

| decision | receipt status | 后续动作 |
| --- | --- | --- |
| `pending` | `pending` | 分配业务负责人 |
| `request_evidence` | `needs_evidence` | 补齐 Scene Card 和证据引用 |
| `reject` | `rejected` | 保持候选非活动状态 |
| `approve` | `blocked` | 当前工具始终阻断，必须走 OMO admission |

`approve` 返回 `blocked` 是设计约束，不是异常。候选投影缺少完整 Scene Card 时不能形成业务
激活事实；即使缺口已经补齐，仍必须由 Agora Scene Card gate 和 OMO admission 产生正式准入证据。

## 进入 admission 前的 preflight

当业务负责人已经补齐完整 Scene Card，并且拥有最新的外部目录快照时，先运行只读 preflight：

```bash
uv run --with pyyaml python bin/ssot/external-activation-preflight.py \
  --scene-card /path/to/scene-card.json \
  --catalog /path/to/external-resource-catalog.json
```

输出 `blocked` 表示需要补字段、证据或能力；`proposal_only` 表示候选存在但仍不可执行；
`ready_for_admission_preview` 只表示可以提交 OMO admission preview。三种结果都保持
`activation=forbidden`，命令不调用 provider、不写 OMO、不创建 WorkflowRun。

## 安全边界

- 只接受 `scene-card-candidate/v1` 且 `activation=forbidden` 的 JSON。
- 不调用外部 provider，不读私人原文，不落盘凭据，不写 OMO 运行态。
- 只回显安全候选摘要、来源引用、能力引用和缺失字段。
- 人工备注不进入回执正文，只输出 `sha256` 摘要，避免把业务原文复制到证据面。
- 回执是人工消费记录，不等价于 `EvidenceRecorded` 或 `WorkflowRun` 状态迁移。

## 进入真实场景的门槛

只有以下材料同时存在，才可以把评审回执交给正式 Scene Card 流程：唯一场景和旅程、真实消费
方、可量化结果指标、审批人和责任人、数据分级与权限引用、失败代价、回滚方案、三到十个脱敏
样本引用，以及真实需求证据或明确机会窗口。材料不足时继续停留在 `candidate`、`sandbox` 或
`proposal_only`。

## 内部 dogfood 卡片

`scene-cards/engineering-delivery-dogfood.yaml` 是第一张完整形态的内部 dogfood 卡片。它使用已
合并的工程交付 PR 和 Workflow Mesh 垂直切片作为不透明证据引用，便于验证“卡片可审阅、结果可
消费、回执可追踪”的产品路径；这些引用不等价于外部业务批准，也不代表外部连接已经激活。

该卡片明确保持 `proposal_only` 与 `activation=forbidden`。后续若要推广到公文审查、会议督办或
其他业务场景，必须替换为业务负责人确认的场景身份、消费方、权限引用和真实脱敏样本，不能直接
复制这张内部卡片的角色或证据。
