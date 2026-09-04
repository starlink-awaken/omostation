---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-19
last_updated: 2026-09-03
type: ssot
---
# Agent Capability Gap Matrix — 对齐 AGT 能力基线

> **维护规则**
> owner: governance-team
> trigger: 能力项状态变更、新 BET 认领、AGT GA 发布
> method: 人工维护，Y1Q4 各能力 BET 反向引用本文
> upstream: [ADR-0415](../../.omo/_knowledge/decisions/0415-reject-agt-integration-adopt-capability-parity.md)
> created_at: 2026-08-18

对照基线：[Microsoft Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)（MIT，公开预览，评估于 2026-08-18）。

**决策前提（ADR-0415）**：不整体接入 AGT。本文追踪**语义级**能力对齐 —— 5 项缺口建能力，产品化包装项标「不适用」，已有能力标现状。

---

## 能力矩阵

| # | AGT 能力 | omostation 现状 | Gap 判定 | 对齐方式 | 目标窗口 |
|---|----------|----------------|---------|---------|---------|
| 1 | 策略执行 PEP（fail-closed, <0.1ms） | `agora/mcp/policy_enforcement.py`（PEPDenied fail-closed + permit 传播）+ admission 三态（required/strict/degraded） | ✅ 已对齐 | — | — |
| 2 | 零信任身份（Ed25519/SPIFFE） | `agora/auth/identity_ca.py`（issue/verify/revoke/list）+ node_identity | 🟡 部分对齐 | 见 #6 信任评分 | Y1Q4 |
| 3 | 执行沙箱 | `runtime/kei_sandbox.py`（深度待 BET 时核实） | 🟡 待核实 | BET 时先审计再定 | Y1Q4 |
| 4 | kill-switch / 紧急终止 | `make mesh-orphan-cleanup-apply`（仅孤儿清理，无硬终止令牌） | 🔴 缺失 | **自建**（runtime mesh 耦合） | Y1Q4（高优） |
| 5 | 0-1000 信任评分 | 无评分模型，仅二值身份 | 🔴 缺失 | **自建**（挂 IdentityCA） | Y1Q4（高优） |
| 6 | Agent SRE（SLO/回放/混沌/渐进发布） | health/metrics 有；无回放、无错误预算、无渐进发布 | 🔴 缺失 | **借鉴设计**（存储接 event-ledger） | Y1Q4 |
| 7 | MCP 安全扫描（投毒/typosquatting/rug-pull） | `external_connections` 仅入库校验（_reject_secrets + health_probe） | 🔴 缺失 | **直接搬** MIT 规则清单改造 | Y1Q4（低优，第三方 MCP 接入前完成） |
| 8 | 信任报告 CLI | `cockpit status/health` 面板 | 🟡 无评分输出 | 随 #5 交付 | Y1Q4 |
| 9 | 审计 append-only + 飞行记录 | event-ledger（append-only + 幂等键）+ audit DB + receipt | ✅ 已对齐 | — | — |
| 10 | OPA/Cedar 策略语言 | 自研 admission 结构 | ⚪ 设计差异，非缺口 | 不对齐 | — |
| 11 | OWASP Agentic Top-10 映射 | 无映射文档 | 🔴 缺失 | 文档 | Y1Q4（低优） |
| 12 | Saga 编排 | 无 | 🔴 缺失 | 随 #4/#6 评估是否需要 | 触发式 |

## 明确不对齐（产品化包装，单仓自用无场景）

- 5 语言 SDK（Python/TS/.NET/Rust/Go）
- 20+ 框架适配器（LangChain/AutoGen/CrewAI…）
- 13,000+ 测试量级认证
- 商业合规认证叙事（OWASP 认证 / EU AI Act 映射产品化）
  - 条件重开：eCOS 对外商业化时再评估（ADR-0415）

## 验收标准

- 核心 5 项（#4 kill-switch、#5 信任评分、#6 SRE、#7 MCP 扫描、#11 OWASP 映射）：**实现 + 测试 + 一次真实使用证据**
- 🟡 项：BET 内先审计现状再定补充范围
- ✅ 项：无动作，本表即证据

## 关联

- [ADR-0415: 拒绝 AGT 整体接入，确立能力对齐路线](../../.omo/_knowledge/decisions/0415-reject-agt-integration-adopt-capability-parity.md)
- Y1Q4 BET 认领：`uv run --with pyyaml python bin/plan/bet-ledger.py claim-check <BET-ID>`（各能力 BET 立项时补链）
