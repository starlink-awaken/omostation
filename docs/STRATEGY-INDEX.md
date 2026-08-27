---
title: 长期战略与执行索引
status: active
type: strategy-index
owner: 夏明星
created: 2026-07-15
updated: 2026-08-15
lifecycle: contract
last-reviewed: 2026-08-17
review-state: plan-mainline-adr-0410
note: >
  从愿景、战略、ADR、执行任务到运行证据的一页导航。动态事实必须读取对应 SSOT，
  本页不维护当前 Phase、健康分、项目数、服务数或任务数。
---

# 长期战略与执行索引

## 战略判断

织星是夏明星一个人的业务操作系统。它的唯一职责是：把外部进来的信号，变成他愿意署名发出去的东西，并且记住他每次改了什么。
若到 2027-12-31 未能连续 12 周每周产出 ≥3 条被本人采纳的建议，则本定位被证伪。

四条黄金旅程是上述北极星的产品投影（不是并列愿景）：

1. 工程交付闭环。
2. 知识到行动闭环。
3. 受控多 Agent 协作闭环。
4. 外部知识与能力触达闭环。

主线是 [`STRATEGY-3YEAR-PLAN-2026H2-2029.md`](STRATEGY-3YEAR-PLAN-2026H2-2029.md)（ADR-0410）。
[`STRATEGY-3YEAR-PANORAMA.md`](STRATEGY-3YEAR-PANORAMA.md) 已 superseded，五平面结构仅作投影阅读。

## 核心文档

| 角色 | 文档 | 状态 |
|---|---|---|
| 终极愿景 | [`VISION-ROADMAP.md`](VISION-ROADMAP.md) | active（历史蜂群叙事见折叠区） |
| 三年主线 | [`STRATEGY-3YEAR-PLAN-2026H2-2029.md`](STRATEGY-3YEAR-PLAN-2026H2-2029.md) | active，ADR-0410 主方案 |
| 产品结构投影 | [`STRATEGY-3YEAR-PANORAMA.md`](STRATEGY-3YEAR-PANORAMA.md) | superseded |
| 收敛总纲 | [`STRATEGY-CONVERGENCE-MASTER-2026-08.md`](STRATEGY-CONVERGENCE-MASTER-2026-08.md) | active |
| 收敛落地包 | [`STRATEGY-CONVERGENCE-LANDING-PACKAGE-2026-08.md`](STRATEGY-CONVERGENCE-LANDING-PACKAGE-2026-08.md) | active |
| Workflow Mesh 实施与运行合同 | [`WORKFLOW-MESH-IMPLEMENTATION.md`](WORKFLOW-MESH-IMPLEMENTATION.md) | active |
| 外部连接机器 SSOT | [`../.omo/_truth/registry/external-connection-fabric.yaml`](../.omo/_truth/registry/external-connection-fabric.yaml) | ssot |
| 外部连接操作标准 | [`../.omo/standards/external-connection-fabric.md`](../.omo/standards/external-connection-fabric.md) | contract |
| 下一阶段 Agent 任务包 | [`proposals/2026-08-01-ECOS-NEXT-STAGE-AGENT-TASK-PACKS.md`](proposals/2026-08-01-ECOS-NEXT-STAGE-AGENT-TASK-PACKS.md) | approved-for-dispatch |
| 项目全景与用户入口 | [`PROJECT-COMPLETE-GUIDE.md`](PROJECT-COMPLETE-GUIDE.md) | active |
| 架构演进与项目边界 | [`ARCHITECTURE-EVOLUTION.md`](ARCHITECTURE-EVOLUTION.md) | active |
| 稳定架构契约 | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) | contract |
| 战略收敛决策 | [`../.omo/_knowledge/decisions/0210-three-year-strategy-execution-convergence.md`](../.omo/_knowledge/decisions/0210-three-year-strategy-execution-convergence.md) | ACCEPTED |
| 协作优先、物理多机延后 | [`../.omo/_knowledge/decisions/0247-strategic-pivot-collab-first-physical-deferred.md`](../.omo/_knowledge/decisions/0247-strategic-pivot-collab-first-physical-deferred.md) | ACCEPTED |
| 交付诚实看板 | [`G-DEL-PHASE2-BOARD.md`](G-DEL-PHASE2-BOARD.md) | active |
| 三年执行台账 (SSOT) | [`plans/3y-bet-ledger.yaml`](plans/3y-bet-ledger.yaml) | ssot（112+ bet） |
| Agent 执行指令 | [`plans/AGENT-BRIEF.md`](plans/AGENT-BRIEF.md) | contract（含 §8.5 L3 归并规程） |
| 里程碑节拍 | [`plans/MILESTONES-2026Q3Q4.md`](plans/MILESTONES-2026Q3Q4.md) | active |
| gbrain+kairon 归并决策 | [`../.omo/_knowledge/decisions/0413-gbrain-kairon-merge-disposition.md`](../.omo/_knowledge/decisions/0413-gbrain-kairon-merge-disposition.md) | PROPOSED (T6-01 实施已完, 待人类确认) |
| 物理多机张力澄清 | [`../.omo/_knowledge/decisions/0414-physical-multihost-tension-resolution.md`](../.omo/_knowledge/decisions/0414-physical-multihost-tension-resolution.md) | PROPOSED |

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
P0 产品真相、场景身份与 Cockpit 信息架构收敛
  -> P0 公文审查 / 会议到督办 / 工程交付三条真实样板
  -> P1 周期报送 / 项目监督 / 绩效证据包复用
  -> P1 外部 Source/Method/Tool/Model/Channel 按场景激活
  -> P2 真实评测集、受控适应与多 Agent 正收益验证
  -> P3 个人工作与决策 OS、领域包和可审核连接生态
```

KEMS 与 Family Hub 当前作为冻结领域包保存。物理多机保持 deferred。未来十二个月原则上
不新增顶层项目，除非通过场景激活门并证明现有责任方无法承载。

## 执行纪律

- 人类入口只走 Cockpit，Agent 跨域入口只走 Agora，治理写入只走 OMO/C2G broker。
- 产品与用户旅程投入不低于 70%，治理和元模型投入不高于 30%。
- 任何智能化能力必须有上下文、评测、成本、置信度和回滚证据。
- 自进化只生成提案，必须经过影子运行、人工审批、灰度和回滚。
- 每个任务使用独立 worktree、Agent Workflow、PR 和合并证据。
- 卫健委等现有领域 Skills 迁为 DomainPack/WorkflowTemplate，不保留第二套任务、调度和运行真相。
- 外部资料、理论、方法、渠道、工具和模型只通过 External Connection Fabric 动态接入。

## 文档职责

- `VISION-ROADMAP.md` 只拥有稳定愿景、原则、场景波次和长期退出条件。
- `STRATEGY-3YEAR-PANORAMA.md` 拥有产品定位、真实场景、项目边界、Mesh 蓝图和阶段决策。
- `WORKFLOW-MESH-IMPLEMENTATION.md` 拥有已实现能力、状态机、实施缺口和验证命令。
- registry、OMO state、任务台账和项目 gitlink 拥有动态事实；战略 Markdown 不复制当前数值。
