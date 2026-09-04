---
title: Current State Coherence 操作合同
type: operations-standard
owner: governance-team
last_updated: 2026-08-02
related:
  - ../../bin/ssot/current-state-coherence.py
  - ../../.omo/_truth/registry/agent-workflows/_root.yaml
  - ../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
lifecycle: contract
---

# Current State Coherence 操作合同

## 目的

`current-state-coherence/v1` 是一个只读投影，用来把已有的运行状态、当前目标、任务目录和
Scene Card 候选放到同一个可验证结果里。它不拥有任何业务、任务、权限或运行时真相，也不
直接写入 `.omo/`。

## 输入与输出

输入只来自以下 SSOT：

- `.omo/state/system.yaml`
- `.omo/goals/current.yaml`
- `.omo/tasks/{active,planned,blocked,done}/`
- `docs/scene-card-candidate-seeds.yaml`
- `.omo/_truth/scenarios/`
- `docs/scene-cards/`

运行：

```bash
uv run --with pyyaml python bin/ssot/current-state-coherence.py --json
```

输出包含 `phase`、`execution`、`scene_activation`、`divergence`、`errors` 和 `warnings`。
产品入口可以消费这份投影，但不得把它回写成另一份状态。

## 工程交付旅程消费语义

Cockpit 的 `DeliveryJourney` 是上述状态的只读产品投影，不是第二套任务状态机。它必须区分：

| `status` / `mode` | 含义 | 产品动作 |
| --- | --- | --- |
| `live` / `active` | 有可读取的受治理 WorkflowRun | 展示当前步骤、审批、验证、证据和恢复动作 |
| `live` / `completed` | 该 Run 已收口，但结果仍可复盘 | 展示证据、结果反馈和复盘入口 |
| `stale` / `waiting_for_run` | 工作树可读，但没有活动 WorkflowRun | 引导创建或认领受治理任务，不得显示为活跃交付 |
| `failed` / `failed` | Run 明确失败 | 展示失败原因和恢复路径，不得自动标记完成 |
| `unavailable` / `unavailable` | 事实源不可读取 | 显示不可用并保留来源，不生成默认数据 |

`scene_binding` 只有在 Run 或其上下文明确携带完整 `scene_id`、`journey_id`、`outcome_metric`
时才返回。工作树、分支、文件或 Git 提交本身不能推导业务场景，也不能证明交付成功。

## 状态解释

| 状态 | 含义 | 是否阻断 |
| --- | --- | --- |
| `active` | 有真实活动目标或活动任务，且字段和计数对齐 | 否 |
| `waiting_for_scenario` | 没有活动任务和活动目标，系统明确等待下一真实场景或 Bet | 否 |
| `error` | Phase、Wave、执行模式、任务计数或快照出现不可接受矛盾 | 是 |

`waiting_for_scenario` 不是失败，也不是业务自动化授权。它只说明系统没有足够的真实消费方
来启动下一条生产旅程。

## Scene Card 激活边界

`scene_activation.status=candidate_only` 表示系统可以继续发现和评审候选，但不能激活外部
知识、数据、方法、工具、模型或渠道。只有存在正式激活的 Scene Card，并且仍需经过既有 OMO
准入、权限、健康、证据和回滚门禁，`activation_allowed` 才会为真。

因此，候选数量增加不会被误报成产品进展；真正的进展必须表现为有消费者、有结果指标、有
责任人并能在 Workflow Mesh 中留下可验证结果。

## 治理接线

该检查由根仓 GaC 运行，并由 Agent Workflow `current-state-coherence` diff check 覆盖状态、
任务和 Scene Card 相关路径。所有状态修复仍必须通过 OMO/C2G broker；本检查只负责发现矛盾
和输出安全投影。
