---
schema_version: specification/v1
spec_version: 1.0.0
title: 心智模型四件套（认知画像/决策偏好/学习风格/情绪基线）
bet_id: BET-Y2Q1-T3-05
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-14
last-reviewed: 2026-09-14
risk_level: L1
human_gate: false
type: ssot
last_updated: 2026-09-14
decision_ref: decision://accepted/BET-Y2Q1-T3-05
---

# 心智模型四件套（BET-Y2Q1-T3-05）

## 背景（Context）

当前 omostation 对「用户是谁」的理解仍停留在静态 TELOS 偏好字段，缺少对认知特征、决策偏好、学习风格与情绪基线的结构化建模。
这导致 Spine 拟草、Cockpit 推荐、Kairon 检索等环节无法做到「因人而异」的自适应——同一输出给不同状态/偏好的用户，体验与效率损失严重。

本 spec 为 BET-Y2Q1-T3-05 建立契约：围绕心智模型四件套——认知画像(PersonaProfile)、决策偏好(AgendaRadar)、学习风格(AttentionField)、情绪基线(ContextAnchor)——建立 JSON Schema、持久化层、热更新接口与 SceneWatcher 驱动的有状态路由。

## 目标（Goal）

落地 PersonaProfile（认知画像·表达文风）、AgendaRadar（决策偏好·轻重缓急）、AttentionField（学习风格·精力分配）、ContextAnchor（情绪基线·历史决策链）四件套模型：

1. 形成四件套 JSON Schema 与持久化/热更新机制
2. SceneWatcher 事件驱动延迟 <= 500ms
3. 覆盖 10 个典型真实业务上下文的分级决策仿真测试

## 非目标（Non-Goals）

- 不引入云端外部心智分析服务（闭环本地）
- 不做跨用户通用画像聚合，本 spec 仅服务单用户（夏明星）
- 不替代 Kairon 检索与 BGE-M3 向量库，四件套只做路由层输入
- 不做医学级情绪诊断，只做日常基线波动感知

## 设计约束（Constraints）

- Schema 必须可 JSON-Schema draft-2020-12 校验
- 持久化路径：`.omo/state/mindmodel/<dimension>.yaml`，支持热更新（inotify/SceneWatcher）
- 路由决策必须在 SceneWatcher 事件后 500ms 内完成降级输出
- 所有维度可独立回滚（circuit_breaker: 任一维度解析异常时回退至默认静态规则配置）
- 与现有 `projects/spine/src/spine/cognitive/` 目录对齐

## 验收标准（Acceptance Criteria）

| # | 标准 | 验证方式 |
|---|------|----------|
| AC1 | PersonaProfile Schema 覆盖文风/语气/详略偏好 | `jsonschema validate` 通过 |
| AC2 | AgendaRadar Schema 覆盖优先级/风险偏好/时间视野 | `jsonschema validate` 通过 |
| AC3 | AttentionField Schema 覆盖学习时段/精力节律/信息密度偏好 | `jsonschema validate` 通过 |
| AC4 | ContextAnchor Schema 覆盖情绪基线/历史决策链/认知负荷标记 | `jsonschema validate` 通过 |
| AC5 | 热更新延迟 <= 500ms（SceneWatcher 触发到路由生效） | `uv run python -m spine.cognitive.test_mind_quartet` exit 0 |
| AC6 | 10 个业务上下文分级决策仿真通过 | `uv run python -m spine.cognitive.test_mind_quartet` exit 0 |
| AC7 | gac-local-gate 全绿 | `make gac-local-gate` exit 0 |

## Write Surfaces

- `projects/spine/src/spine/cognitive/`（Schema + 路由 + SceneWatcher 适配）
- `.omo/state/mindmodel/`（持久化 YAML）
- `.omo/_knowledge/retros/BET-Y2Q1-T3-05.md`（retro 归档）
- `docs/superpowers/specs/2026-09-14-t3-05-mindmodel-four-pieces-spec.md`（本 spec）
