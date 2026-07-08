---
status: PROPOSED
lifecycle: strategy
owner: governance-team
last-reviewed: 2026-07-08
related:
  - STRAT-P76-strategic-roadmap.md
  - STRAT-P77-strategic-roadmap.md
  - 0173-p78-phase2-baseline-foundry-v2.md
  - 0172-p78-port-registry-convergence.md
  - 0170-p77-phase7-env-var-port-migration.md
  - 0164-p77-phase1-cross-repo-consistency.md
supersedes: []
---

# STRAT-P79: 2026H2 治理巩固 + Foundry 运营化路线图

> **For agentic workers**: 本文档是 **PROPOSED** 状态, 是 2026H2 治理/运营路线图。
> 基于 P76 (50 原则/161 GaC) + P77 (60 原则/173 GaC) 的完成状态。
> **P79 精神**: 从"建设"转向"运营" — 把已造的工具跑起来, 把已定的规则守住。

## 0. TL;DR

| 字段 | 值 |
|------|-----|
| **决策 ID** | STRAT-P79-2026-07-08 |
| **基线** | catalog 60 · GaC 173 · health 95 · planned 0 |
| **5 phase 总预算** | 8 周 · 5 个 ADR · 6-8 个 PR |
| **首推动作** | Phase 1: Foundry v2 cron 集成 |
| **总目标** | health 100 · foundry 运营化 · 文档刷新 |

## 1. 基线

### 1.1 已完成 (P77/P78 成就)

| 领域 | 成就 |
|------|------|
| 跨仓一致性 | detector: 0 unregistered BOS URI |
| 端口治理 | 32 SSOT ports, 27 env var 映射, 2 deprecated |
| GaC 规则 | 173 rules (P76: 157 → +16) |
| 原则沉淀 | catalog 60 原则 (P76: 25 → +35) |
| Foundry | 10-deck (新增 port-governance) |
| 治理健康 | health 95, governance 100, anomaly 0 |

### 1.2 未闭合项

| 项 | 类型 | 优先级 |
|----|------|:------:|
| Foundry deck 未入 cron | 运营 | P1 |
| cc-switch 0 凭证 | 环境 | P1 |
| `bos://capability/bus/data` unregistered | 合规 | P2 |
| 32 bare hardcoded ports | 工程 | P2 |
| ecos port-registry vs protocols 双源 | 架构 | P3 |
| 架构文档未反映 P77/P78 变化 | 文档 | P3 |

## 2. 路线图 (5 Phase)

### Phase 1: Foundry v2 cron 集成 (Week 1-2)

| 交付 | 价值 |
|------|------|
| port-governance deck 加入 `knowledge-foundry-cron.py` | 自动化 |
| foundry cron 增加到 10-deck 编排 | 运营化 |
| metrics 输出统一格式 | 可观测 |
| ADR-0174 | 决策记录 |

### Phase 2: Health 100 (Week 2-3)

| 交付 | 价值 |
|------|------|
| cc-switch 凭证修复 / 豁免 | 环境整洁 |
| 32 bare ports 分类: 豁免 vs 迁移 | 端口治理闭环 |
| health 95 → 100 | 治理达标 |
| ADR-0175 | 决策记录 |

### Phase 3: 跨仓零残留 (Week 3-5)

| 交付 | 价值 |
|------|------|
| `bos://capability/bus/data` 补登或豁免 | 合规 |
| ecos port-registry 与 protocols 对齐 (合并或 deprecate) | 架构 |
| ADR-0176 | 决策记录 |

### Phase 4: 文档刷新 (Week 5-6)

| 交付 | 价值 |
|------|------|
| ARCHITECTURE.md 更新 port-registry/transport/env-var 章节 | 知识 |
| LAYER-INDEX.md 更新 P77/P78 落地 | 导航 |
| docs/ 链式 SSOT 检查 | 质量 |

### Phase 5: 运营 SOP + 冻结声明 (Week 6-8)

| 交付 | 价值 |
|------|------|
| Foundry 运营 SOP | 可重复 |
| GaC 规则冻结声明 (173 封顶) | 稳定 |
| 归档 P76/P77/P78 完成 ADR | 闭环 |

## 3. 冻结区

- **health < 95** 时禁止新增 GaC 规则
- **planned > 5** 时禁止启动新 Phase (先消化存量)

## 4. 相关

- STRAT-P76: 已收口 (2026-07-07)
- P77 STRAT: 已收口 (2026-07-07)
- 本 STRAT 覆盖: 2026-07-08 ~ 2026-08-30
