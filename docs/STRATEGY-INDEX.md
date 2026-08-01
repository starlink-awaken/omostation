---
title: 长期战略与执行索引
status: active
type: strategy-index
owner: 夏明星
created: 2026-07-15
updated: 2026-08-01
lifecycle: contract
last-reviewed: 2026-08-01
review-state: evidence-refreshed
note: >
  从愿景、战略、ADR、执行任务到运行证据的一页导航。动态事实必须读取对应 SSOT，
  本页不维护当前 Phase、健康分、项目数、服务数或任务数。
---

# 长期战略与执行索引

## 战略判断

eCOS 已从基础设施建设期进入“平台能力齐备、产品兑现开始、状态真相需要归一”的转折点。
后续不再以新增 Phase、子项目或治理规则数量衡量进度，而以三条黄金旅程衡量：

1. 工程交付闭环。
2. 知识到行动闭环。
3. 受控多 Agent 协作闭环。

北极星是每周成功完成并被实际消费的闭环旅程数。

## 核心文档

| 角色 | 文档 | 状态 |
|---|---|---|
| 终极愿景 | [`VISION-ROADMAP.md`](VISION-ROADMAP.md) | active |
| 长期战略与目标架构 | [`STRATEGY-3YEAR-PANORAMA.md`](STRATEGY-3YEAR-PANORAMA.md) | active v1.0 |
| 下一阶段 Agent 任务包 | [`proposals/2026-08-01-ECOS-NEXT-STAGE-AGENT-TASK-PACKS.md`](proposals/2026-08-01-ECOS-NEXT-STAGE-AGENT-TASK-PACKS.md) | approved-for-dispatch |
| 项目全景与用户入口 | [`PROJECT-COMPLETE-GUIDE.md`](PROJECT-COMPLETE-GUIDE.md) | active |
| 架构演进与项目边界 | [`ARCHITECTURE-EVOLUTION.md`](ARCHITECTURE-EVOLUTION.md) | active |
| 稳定架构契约 | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) | contract |
| 战略收敛决策 | [`../.omo/_knowledge/decisions/0210-three-year-strategy-execution-convergence.md`](../.omo/_knowledge/decisions/0210-three-year-strategy-execution-convergence.md) | ACCEPTED |
| 协作优先、物理多机延后 | [`../.omo/_knowledge/decisions/0247-strategic-pivot-collab-first-physical-deferred.md`](../.omo/_knowledge/decisions/0247-strategic-pivot-collab-first-physical-deferred.md) | ACCEPTED |
| 交付诚实看板 | [`G-DEL-PHASE2-BOARD.md`](G-DEL-PHASE2-BOARD.md) | active |

## 动态事实

| 事实 | SSOT |
|---|---|
| 当前 Phase、任务与健康 | [`.omo/state/system.yaml`](../.omo/state/system.yaml) |
| 当前目标 | [`.omo/goals/current.yaml`](../.omo/goals/current.yaml) |
| 项目元数据 | [`project-registry.yaml`](project-registry.yaml) |
| BOS 服务 | [`projects/agora/etc/bos-services.yaml`](../projects/agora/etc/bos-services.yaml) |
| 任务 registry | [`.omo/tasks/registry/INDEX.md`](../.omo/tasks/registry/INDEX.md) |
| Agent Workflow | [`.omo/_truth/registry/agent-workflows.yaml`](../.omo/_truth/registry/agent-workflows.yaml) |

## 近期执行顺序

```text
P0 根仓身份与 worktree/PR 远端修复
  -> P0 SSOT 与当前状态时间线归一
  -> P0 工程交付黄金旅程产品化
  -> 知识到行动闭环
  -> 受控适应与多 Agent 正收益验证
  -> 个人智能执行 OS 与领域包生态
```

KEMS 与 Family Hub 当前作为冻结领域包保存。物理多机保持 deferred。未来十二个月原则上
不新增顶层项目，除非通过场景激活门并证明现有责任方无法承载。

## 执行纪律

- 人类入口只走 Cockpit，Agent 跨域入口只走 Agora，治理写入只走 OMO/C2G broker。
- 产品与用户旅程投入不低于 70%，治理和元模型投入不高于 30%。
- 任何智能化能力必须有上下文、评测、成本、置信度和回滚证据。
- 自进化只生成提案，必须经过影子运行、人工审批、灰度和回滚。
- 每个任务使用独立 worktree、Agent Workflow、PR 和合并证据。
