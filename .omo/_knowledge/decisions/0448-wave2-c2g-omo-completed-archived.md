---
id: ADR-0448
status: ACCEPTED
lifecycle: spec
owner: governance-agent
last_updated: 2026-08-01
---

# ADR-0295: Wave 2 (C2G + OMO) — Completed & Archived

> **Status**: ACCEPTED (Phase A/B/C) → ARCHIVED (completed, maintenance mode)
> **Date**: 2026-08-01
> **Source**: `draft/WAVE2-C2G-OMO-ROADMAP.md`
> **Supersedes**: Phase A ADR-0183, Phase B ADR-0185, Phase C ADR-0188

## 背景

Wave 2 路线图自 2026-07-25 起草，覆盖 Phase A/B/C 三个已接受的 ADR。核心目标（数据闭环、预测合约、治理提案）已全部实现并在线运行。

## 已交付价值（Phase A/B/C 全部 accepted + 实现）

| 交付物 | 模块 | 行数 | 状态 |
|--------|------|------|------|
| **OutcomeTracker** — pitch/task/outcome 全生命周期追踪 | `c2g/outcome_tracker.py` | 184 | ✅ 生产可用 |
| **Backtest CLI** — 历史数据回测报告 | `c2g/outcome_backtest.py` | 35 | ✅ 可用 |
| **Predictive Engine** — EMA + 线性趋势 + 风险热力图 | `c2g/predictive.py` | 237 | ✅ 生产可用 |
| **Governance Feedback** — C2G outcome → OMO proposals | `c2g/governance_feedback.py` | 231 | ✅ 生产可用 |
| **Dashboard Export** — 统一 JSON 契约 | `c2g/dashboard_export.py` | 114 | ✅ 被 cockpit 消费 |
| **Cockpit CLI** — `cockpit wave2 dashboard/proposals/predictivity` | `cockpit/commands/wave2.py` | 65 | ✅ 在线 |
| **Cockpit API** — `/api/wave2/dashboard` 等 3 端点 | `cockpit/dashboard/routes.py` | 3 routes | ✅ 在线 |
| **测试覆盖** | 19 文件, 200 test fns | 1987 行 | ✅ 全绿 |

## 6 项待办终态判定

| # | 方向 | 原优先级 | 终态 | 理由 |
|---|------|---------|------|------|
| 1 | 数据闭环（自动调参） | P0 | ✅ **已完成**框架 | 自动调参缺真实数据源，当前仅 demo seed，不推进 |
| 2 | 预测增强（ARIMA/Prophet） | P0 | 🚫 **否决** | ADR-0185 明确 EMA+linear 为最终方案，heavy deps 为 non-goal |
| 3 | 可视化（Cockpit 仪表盘 UI） | P1 | ⏸️ **降级** | JSON API 就绪，前端非战略所需 |
| 4 | 自动联动（规则自动调整） | P1 | 🚫 **禁止** | ADR-0188 明确禁止，proposal-first 是红线 |
| 5 | MOF M0 验证器 | P1 | ⏸️ **降级** | 投入产出比低，待 P82 重新评估 |
| 6 | 跨仓一致性审计 | P2 | ⏸️ **降级** | relationConstraints 未填充，前置条件不具备 |

## 架构教训

1. **ADR 先于实现** — Phase A/B/C 均先写 ADR 再实现，避免了方向漂移，值得后续 Wave 复用。
2. **"no auto rule mutation" 红线** — 治理规则自动修改是高风险操作，ADR-0188 的 proposal-first 模式是正确的安全边界。
3. **预测模型够用即可** — EMA+linear 在数据量不足时足够，ARIMA/Prophet 需要 30+ 时间点才有优势，过早引入增加 CI 负担。
4. **JSON API > 前端 UI** — cockpit JSON 合约已够用，React/Vue 组件在非前端优先战略中投入产出比低。

## 维护模式

- Wave2 模块进入维护模式：bug fix only，不再扩展
- OutcomeTracker / Predictive / Governance Feedback 持续被 cockpit dashboard API 消费
- 如未来需要自动调参或高级预测模型，需新建 ADR 并证明有真实数据源

## 引用

- ADR-0183 (Phase A), ADR-0185 (Phase B), ADR-0188 (Phase C)
- `projects/c2g/` — 26 模块, 3318 行 Python
- `projects/cockpit/commands/wave2.py` — CLI 入口
