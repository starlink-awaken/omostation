---
id: ADR-0403
status: active
lifecycle: spec
owner: '@Builder'
last-reviewed: '2026-08-09'
type: ssot
---

# ADR-0403: Agent本体与模型驱动约束架构

- status: accepted
- date: 2026-08-08
- owner: architecture-team
- related: ADR-0400(DoD), ADR-0402(门禁后移), MOF M2模型, grill-me 12轮决策

## Context

Agent从8个hardcode Python类进化为可治理的生态体系。需要统一agent的身份/能力/约束/关系/资源管理。
经grill-me 12轮 + 全网调研(survey arXiv 2507.21046 + Letta/MemGPT + A2A + PI)，确定本体+模型驱动架构。

## Decision

**Agent本体统一声明 + 模型驱动自动生成约束制品**:

1. 每个Agent在一个yaml本体里声明全部属性（identity/mental/knowledge/constraints/relationships/resources）
2. MOF M2 digital_agent模型扩展constraints/shapes语义
3. 模型驱动：从本体自动生成constraint-gate规则/permission-matrix条目/Agent Card/PR审查维度
4. 约束统一层：governance-checks + permission-matrix + redlines通过本体bindings统一引用

## Drivers

- MOF M2已有5个agent模型（复用基础）
- governance-checks 136条规则已存在（被本体引用）
- permission-matrix三级名单已存在（从本体生成）
- constraint-gate已存在（扩展为本体驱动）
- arXiv survey确认本体驱动是行业方向

## Architecture (4层存在 + 评估层)

```
第5层: 评估层 — AutonomyAssessmentAgent (5维度持续评估)
第4层: 社会层 — A2A(agora BOS) + Governor调度 + PR审查矩阵
第3层: 认知层 — 规则+LLM(PI)+学习 (D方案)
第2层: 记忆层 — MOS四表+技能库+经验库+遗忘 (扩展Letta模式)
第1层: 身份层 — Agent本体yaml + Agent Factory (模型驱动)
```

## Consequences

- 正面: Agent全属性可声明/可查询/可验证/可变更
- 正面: 约束制品自动生成，消除配置漂移
- 正面: A2A Agent Card自动发现异构agent
- 负面: 需要维护本体一致性（SHACL-like验证）
- 约束: 本体变更走MOF流程（mof adr → validate → 实施）

## Phased Rollout

| Phase | 内容 | 复用 |
|-------|------|------|
| P1 | Agent本体声明(yaml) + 约束生成器 | MOF M2 + registry |
| P2 | MOS记忆扩展(技能库+遗忘) | omo_belief |
| P3 | AutonomyAssessmentAgent | verify.py |
| P4 | A2A适配器(agora BOS) | agora路由 |
| P5 | PI集成(深判引擎) | PI SDK |
| P6 | 多agent协作 | AgentHost+agora |
