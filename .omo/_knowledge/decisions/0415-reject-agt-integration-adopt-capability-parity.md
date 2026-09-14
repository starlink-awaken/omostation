---
id: ADR-0415
title: 拒绝 AGT 整体接入，确立能力对齐路线
status: archived
lifecycle: spec
owner: governance-team
created: 2026-08-18
last-reviewed: 2026-08-18
deciders:
  - 夏明星 (最终确认)
  - governance-agent (起草, grilling 三轮共识)
related:
  - docs/governance/agent-capability-gap-matrix.md
  - https://github.com/microsoft/agent-governance-toolkit
type: ssot
---

# ADR-0415: 拒绝 AGT 整体接入，确立能力对齐路线

## Context

评估 [Microsoft Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)（AGT，MIT，公开预览）是否接入 omostation。经 grilling 三轮共识（2026-08-18）逐项决策。

## Decision

### 1. 不整体接入 AGT

理由：
- **双轨治理冲突**：本仓 GaC/admission/workflow 是 workspace 级声明式体系；AGT 是进程内 SDK 中间件体系。全量引入 = 两套 PDP 并行，语义互相打架。
- **架构层级错位**：AGT 定位「单代理进程内中间件」；本仓治理发生在 workspace 编排层（BOS URI 域路由 + 卡片 + workflow），AGT 管不到真正需要治理的跨编排层。
- **预览版风险**：官方明示 GA 前 breaking changes，governed monorepo 维护成本高。
- **重叠度高**：PEP/身份/审计/外部接入校验已有自研实现（policy_enforcement、IdentityCA、event-ledger、external_connections）。

条件重开项：若未来 eCOS 对外商业化交付需要 OWASP/EU AI Act 认证叙事，再评估 AGT 作为合规叙事层接入。

### 2. 走能力对齐（语义级，非产品级）

对齐 AGT 具备而本仓缺失的 5 项运行时治理语义：

| # | 能力 | 实施方式 | 优先级依据 |
|---|------|---------|-----------|
| 1 | kill-switch / 紧急终止控制 | 自建（与 runtime mesh 深度耦合） | 高 — 多 agent 并行有事故史（2026-08-16 并发吸收） |
| 2 | 0-1000 信任评分模型 | 自建（挂接 IdentityCA） | 高 — 同上 |
| 3 | SRE 回放调试 + 渐进发布 | 借鉴设计（存储接 event-ledger） | 中 |
| 4 | MCP 运行时安全扫描（投毒/rug-pull） | 直接搬 MIT 检测规则清单改造 | 低 — 当前无第三方不可信 MCP，接入前完成即可 |
| 5 | OWASP Agentic Top-10 映射表 | 文档 | 低 |

产品化包装项（5 语言 SDK、20+ 框架适配器、13k 测试量、认证叙事）**明确不适用**单仓自用体系，不对齐。

### 3. 验收与排期

- 核心 5 项验收 = 实现 + 测试 + 一次真实使用证据
- 其余 gap 项在 [gap matrix](../../../docs/governance/agent-capability-gap-matrix.md) 中诚实标注现状
- 本 ADR + gap matrix 进 Y1Q3 收口；5 个能力 BET 进 Y1Q4 排期

## Consequences

- 后续会话再遇「要不要接 AGT」类评估，本 ADR 一票否决重复评估（除非触发条件重开项）
- gap matrix 成为 Y1Q4 各能力 BET 的母文档（反向引用）
- MIT 许可允许直接搬检测规则，搬运时保留版权声明

## References

- AGT 中文文档评估摘要（会话内 WebFetch, 2026-08-18）
- agora 源码重叠度核查：policy_enforcement.py / identity_ca.py / external_connections.py / kei_sandbox.py
