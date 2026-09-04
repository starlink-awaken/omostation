---
id: ADR-0311
title: 当前状态一致性与场景激活门
status: ACCEPTED
type: decision
owner: architecture-governance
created: 2026-08-02
last_updated: 2026-08-02
lifecycle: spec
related:
  - ../../standards/external-connection-fabric.md
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../../docs/operations/current-state-coherence.md
---

# ADR-0311 当前状态一致性与场景激活门

## Context

eCOS 已经拥有 OMO 状态、目标文件、任务 registry、Scene Card 候选和 Workflow Mesh，但这些面
长期由不同工具读取。仅有 `state-goals-alignment` 检查不足以回答“当前到底是在执行、等待真实
场景，还是已经具备外部能力激活条件”。如果把历史完成目标或候选数量当作当前进展，后续 OCR、
知识图谱、预测模型和外部连接会在没有真实消费者的情况下被提前生产化。

## Decision

1. 增加只读 `current-state-coherence/v1` 投影，统一报告当前 phase/wave、任务计数、活动目标、
   执行模式、历史目标数量和 Scene Card 激活状态。
2. `waiting_for_scenario` 是合法的产品状态：没有活动任务和活动目标时，必须明确等待下一条真实
   场景或 Bet，不生成假任务、假指标或假成功。
3. 计数、Phase、Wave 和执行模式的实际矛盾阻断 GaC；仅当已计算真相为空而旧的 divergence 快照
   仍残留时，报告 warning 并等待 OMO state sync 刷新。
4. Scene Card 候选和 proposal-only 卡片永远不能推导出 `activation_allowed=true`；外部资源仍需
   真实消费者、结果指标、权限边界、健康、证据和可回滚准入。
5. 投影不写入 `.omo`，不拥有任务生命周期，不新增 Cockpit 或外部连接的第二套状态机。任何
   修复继续通过 OMO/C2G broker 完成。

## Consequences

系统会更早暴露“历史计划仍被当作当前执行”的状态歧义，同时允许在没有业务场景时诚实地停在
等待态。产品入口可以消费一个稳定的只读投影，后续真实场景激活时仍复用既有 Scene Card、OMO
Admission 和 Workflow Mesh 证据链。

## Verification

- `tests/test_current_state_coherence.py` 覆盖等待态、Phase 漂移、任务计数漂移和活动任务误用等待态。
- `bin/ssot/current-state-coherence.py --json` 输出可重复的 `current-state-coherence/v1`。
- 根 GaC 和 Agent Workflow diff check 均接入该检查。
