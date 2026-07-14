---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0054: P60 治理方法论内化 — L/X/M/L4/cockpit/Skill 6 层落地

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P60
- **Extends**: ADR-0050/0051/0052/0053 (P50-P57 治理决策链)
- **Superseded by**: (无)

## Context and Problem Statement

P43-P59 共 17 个 phase 完成治理收敛主体工作, 但**方法论沉淀分散在 15 份收口报告 + 4 个 ADR + 2 个新工具** 中, 未形成系统化的内化机制。

P60 调研发现:
- L0 强制约束未覆盖闭环纪律 (P59 教训)
- X1-X4 规则未覆盖工作树累积检测
- M3 model-driven 阶段定义止步于 7 阶段 (无 GOVERNANCE_MAINTENANCE)
- L4-kernel capability 未专门覆盖 governance 跨域
- 工作流 skill 缺 governance-phase-orchestrator
- CLAUDE.md 启动指令未含 RISE 循环 / 维度饱和律 / 软分层原则

## Decision

P60 实施 6 层落地, 把 P43-P59 沉淀方法论内化为机器可执行规则 + 智能引导:

### D1: L0 强制约束增量 (5 条)

```
projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml
新增 governance_closure_constraints 块 (5 条):
- CR-GOV-CLOSED-LOOP-01 (error)   # 强制闭环原则 (P59 教训)
- CR-GOV-FRONTMATTER-SCHEMA-01 (warn)  # frontmatter 4 字段契约
- CR-GOV-DOC-CATEGORY-01 (warn)  # 4 类生命周期 (P45 标准)
- CR-GOV-DIMENSION-SATURATION-01 (warn)  # linter ≥15 用 bin 工具 (P57)
- CR-GOV-COMMIT-FREQUENCY-01 (warn/error)  # 工作树累积预警
```

### D2: X1-X4 规则增量 (3 条)

```
.omo/_truth/x1-governance-policies.yaml: X1-AUD-COMMIT-LOOP
.omo/_truth/x2-freshness-rules.yaml: X2-FRESH-COMMIT-FATIGUE
.omo/_truth/x4-consistency-rules.yaml: X4-CONS-DRIFT-VS-GOVERNANCE
```

### D3: M0 桥接 (M3/M2/M1 三层)

```
M3: LifecycleStage.GOVERNANCE_MAINTENANCE (新阶段, 紧接 BUSINESS_OPS)
  projects/model-driven/src/model_driven/mof/m3_extended.py

M2: GovernanceDecision schema (新 type)
  projects/ecos/src/ecos/ssot/mof/m2/governance_decision.yaml
  必填: decision_id (GOVD-YYYY-NNN) + decision_type + rationale (WHY/WHAT/NEXT 3 段)
       + alternatives_considered (≥1 被拒方案) + consequences + evidence

M1: GOV-MAINTENANCE-PHASE (新实例)
  projects/ecos/src/ecos/ssot/mof/m1/governance/GOV-MAINTENANCE-PHASE.yaml
  5 objectives + 5 gates (frontmatter / drift / closure / dimension / ADR)
  + 双向引用 (m3_parent + model_driven_refs)
```

### D4: L4-kernel 6 governance capability

```
projects/l4-kernel/src/l4_kernel/registry.py (OPC 域)
新增 6 capability:
- gov.frontmatter_audit        # omo lint doc-lifecycle
- gov.drift_monitor            # bin/mof-drift
- gov.commit_closure           # git status --short | wc -l
- gov.dimension_saturation     # linter 维度阈值
- gov.adr_index_integrity      # omo audit ADR 检查
- gov.rise_cycle               # governance-phase-orchestrator
```

### D5: Workflow Skill: governance-phase-orchestrator

```
.claude/skills/governance-phase-orchestrator/SKILL.md
内容: 5 大铁律 + RISE 循环 + 维度饱和律 + 3 类债务识别
     + commit-closure-recovery 恢复流程 + 失败模式
触发关键词: 治理, 收敛, P 阶段, drift, frontmatter, commit closure, linter saturation, RISE 循环
```

### D6: 治理就绪度评估工具

```
bin/gac/governance-readiness.py (新)
5 维度评分 (满分 100):
1. 元数据覆盖 (25 分) — frontmatter ≥ 95%
2. 漂移检测 (20 分) — mof-drift LOW ≤ 5
3. 闭环纪律 (20 分) — 工作树 ≤ 50
4. 决策可追溯 (20 分) — ADR INDEX 无 UNLISTED
5. 治理评分 (15 分) — omo governance = 100

评级: ≥90 A+ 稳态 | 80-89 A 成熟 | 70-79 B 基础 | 60-69 C 起步 | <60 缺失
实测: 80/100 (A L3 成熟治理, P60 R1)
```

### D7: CLAUDE.md 增量 (Agent Prompt 注入)

```
CLAUDE.md §0.1 治理纪律 (新增段落)
内容: 5 大铁律表 + RISE 循环示意 + 软分层 vs 硬分层
     + 治理债务识别 (3 类) + 治理就绪度命令
     + mof-version vs git commit 双轨制
```

## Consequences

### Positive

- **方法论系统化**: 从 15 份分散报告 → 5 层规则 + 1 skill + 1 工具 + 1 文档
- **机器可识别**: L0 + X1-X4 + M0 三层规则全部机器可读
- **智能引导**: governance-phase-orchestrator skill 自动激活
- **影响扩散**: 未来 agent 启动即读 CLAUDE.md §0.1, 工作流 skill 自动加载
- **可评估**: governance-readiness.py 5 维度评分可量化进展
- **决策可追溯**: M2 GovernanceDecision schema + GOVD- 编号

### Negative

- **CLAUDE.md 增重**: 38 行治理纪律段 (但收益远大于成本)
- **L0 约束增加**: 5 条新规则需 omo audit 验证 (P60 R1 已验证 100 A+)
- **skill 维护成本**: governance-phase-orchestrator 需随方法论演化更新

### Neutral

- **未触发新的 linter 维度**: 沿用 P57 维度饱和律, 用独立 bin 工具
- **未触动 M3 现有 7 阶段**: 仅追加 GOVERNANCE_MAINTENANCE 第 8 阶段
- **未重构现有代码**: 所有改动都是增量 (约束/M2/M1/capability/skill/tool)

## Compliance

### 验证指标

| 指标 | P59 末 | **P60 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.47 | **v0.0.49** | +2 (本 ADR + 收口) |
| governance | 100 A+ | **100 A+** | 持平 |
| mof-drift LOW | 2 | **2** | 持平 |
| L0 强制约束 | 31 | **36** | +5 |
| X1-X4 规则 | 8 | **11** | +3 |
| omo lint 维度 | 15 | **15** | 持平 (饱和) |
| 独立 bin 治理工具 | 2 | **3** | +1 (governance-readiness) |
| L4 governance capability | 4 | **10** | +6 |
| Workflow skill | 0 | **1** | +1 (governance-phase-orchestrator) |
| M3 阶段 | 7 | **8** | +1 (GOVERNANCE_MAINTENANCE) |
| M2 schema | 45 | **46** | +1 (GovernanceDecision) |
| M1 实例 | 1031 | **1032** | +1 (GOV-MAINTENANCE-PHASE) |
| ADR 数量 | 13 | **14** | +1 (0054) |
| 治理就绪度 | (未评估) | **80/100 (A)** | 新增 |

### 关联 ADR

- **ADR-0050**: gbrain 53 TODOs 4 类决策 (P50)
- **ADR-0051**: gbrain TODOs v5 终极收敛 (P52)
- **ADR-0052**: P54-P55 知识面深度收敛 (P56)
- **ADR-0053**: P56 frontmatter 100% + doc-lifecycle (P57)

### 关联报告

- `.omo/_knowledge/audits/2026-06-23-p43-p59-systematic-retrospective.md` (方法论沉淀)
- `.omo/_knowledge/audits/2026-06-23-p60-governance-internalization-proposal.md` (内化提案)
- `.omo/_knowledge/audits/2026-06-23-p60-implementation-closeout.md` (实施收口)

## Notes

本 ADR 是 P43-P59 治理收敛的**系统化收口**, 把 17 个 phase 的方法论沉淀内化为机器可执行规则 + 智能引导。

后续 P61+ 候选:
- management/ 142 拆 3 类 (大重构, 需深度访谈)
- graphify-out 重生覆盖 1622 文件
- 自治治理代理 (cron 每 6h 自动跑 governance-readiness)
- OmniFrame 开源化 (把治理模式抽象为通用框架)

---

*最后更新: 2026-06-23 · P60 · omostation 治理方法论内化*