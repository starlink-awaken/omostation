---
id: ADR-0315
title: Knowledge to Action 以引用、任务和行动回执组成 J2 垂直切片
status: ACCEPTED
date: 2026-08-02
owner: engineering-team
lifecycle: spec
last-reviewed: 2026-08-02
type: ssot
---

# ADR-0315: Knowledge to Action 以引用、任务和行动回执组成 J2 垂直切片

## 背景

系统已经具备 KOS 检索、OMO 任务承接和 Workflow Mesh 运行事件，但三者之间缺少可验证的产品路径：
无法区分“看过知识”“引用知识”“创建任务”和“真正进入执行”。在没有真实外部业务场景时，直接
建设 OA、邮件、短信、OCR 或预测模型执行链会扩大边界而没有可验收结果。

## 决策

以 `knowledge-action/v1` 建立参考平面，采用 `检索 -> 引用 -> 受治理任务 -> 行动回执` 的 J2
垂直切片：

1. OMO append-only 日志保存引用元数据、查询哈希、场景绑定和关联 ID，不保存任何原文或秘密。
2. Cockpit 通过既有 KOS 搜索展示候选，任务创建统一进入 OMO task ingress。
3. `task_created` 必须有真实场景、旅程、结果指标、知识引用和任务 ID。
4. 行动回执与 WorkflowRun 状态分离；回执失败不回滚已创建任务，也不得伪造成功。
5. `workflow_requested`、外部连接和结果反馈保持显式准入，暂不自动激活。
6. Workflow Mesh 的运营快照只增加 `knowledge_action` 派生区，不建立第二套运行状态或指标库。

## 结果

系统获得一个可操作、可测试、可度量的 J2 入口，并能回答知识是否被承接为行动。后续可以在真实
场景出现时，把 `task_created` 沿既有审批、证据、外部 receipt 契约推进到 Workflow Mesh，而不需要
重做知识库或任务系统。

## 不做

本 ADR 不启用外部私有数据连接，不把 KOS 变成 WorkflowRun 数据库，不引入知识图谱生产库，不
训练预测模型，不把行动回执解释为业务成功或自动学习。
