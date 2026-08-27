---
status: active
lifecycle: ssot
owner: governance-team
last-reviewed: 2026-06-22
---

# P43 Closed-Loop Pattern — M3 Lifecycle Instance

> **Generated**: 2026-06-21 (post-P43 R5)
> **SSOT**: `.omo/_truth/mof-version.yaml` v0.0.12
> **Purpose**: 用 M3 元元模型实例化 P43 闭环作为可复用模式

## 7 阶段 ↔ P43 R1-R5 映射

| LifecycleStage | P43 Round | 关键产物 | 治理面写入 |
|----------------|-----------|----------|------------|
| PLANNING | R1 (debt evidence) | 5 项 debt closure / next-action | `.omo/debt/items/` (gitignore) |
| DESIGN | R2 (lint cleanup) | mof-version v0.0.7 + 18 F821 fix | `.omo/_truth/mof-version.yaml` |
| DEVELOPMENT | R3 (c2g tests) | 41 新 tests + SUBSYSTEM_MAP.md | `.omo/_knowledge/audits/` |
| DEPLOYMENT | R4 (4 subprojects) | cockpit/runtime/omo/metaos lint=0 | git commits (submodule pointers) |
| RUNTIME | R5 (3 subprojects) | aetherforge/ecos/cockpit lint=0 + governance 100 | `.omo/_knowledge/governance-history.jsonl` |
| OPERATIONS | — | 后续 cron 巡检 X2-FRESH-* | mof-extract post-commit hook |
| BUSINESS_OPS | — | 暂未触发 | — |

## 3 PipelinePhase ↔ P43 闭环

```
Phase 1: ColdStart (Planning + Design)
  └─ P43 R1+R2: 债务治理 + lint 治本 → governance 85 → 100 A+

Phase 2: Evolution (Development + Deployment)
  └─ P43 R3+R4: c2g 测试 + 4 子项目 lint → c2g ratio 0.02→0.07

Phase 3: Hardening (Runtime + Operations + BusinessOps)
  └─ P43 R5: 全 9 子项目 lint=0 + mof-version v0.0.12 baseline
```

## 4 Gate 实例化

| Gate ID | P43 状态 | 校验项 | 通过条件 |
|---------|----------|--------|---------|
| GATE-PLAN-TO-DESIGN | ✅ passed | OKR 审批 + Spec 草案 + ADR | X1-X4 policies 加 4 条 (P43 closed-loop) |
| GATE-DESIGN-TO-DEV | ✅ passed | Spec 审批 + 接口契约 + 设计评审 | L0 constraints +3 (CR-DEBT-CLOSURE-EVIDENCE-01 等) |
| GATE-DEV-TO-DEPLOY | ✅ passed | 测试 ≥ 95% + CI 绿灯 + Review | mof-enforce post-check 0 drift |
| GATE-DEPLOY-TO-RUN | ✅ passed | 部署成功 + 冒烟 + 监控 | governance 100 A+ 6/6 OK |
| GATE-RUN-TO-OPS | 🔄 进行中 | 30 天巡检 (X2-FRESH-*) | 待 cron wrapper 接入 |
| GATE-OPS-TO-BIZ | ⏸️ 待启动 | 业务指标 + ROI 归因 | P44 启动 |

## 关键 SSOT 引用链

| 层 | 路径 | 角色 |
|----|------|------|
| M3 元元 | `projects/model-driven/src/model_driven/mof/m3_extended.py` | 7 LifecycleStage + 4 Gate |
| M3 宏观 | `projects/model-driven/src/model_driven/lifecycle/pipeline.py` | 3 PipelinePhase |
| L0 强制约束 | `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` | 31 条 (含 3 条 P43 衍生) |
| X1 策略 | `.omo/_truth/x1-governance-policies.yaml` | 6 条 (含 2 条 P43 closed-loop) |
| X2 保鲜 | `.omo/_truth/x2-freshness-rules.yaml` | 7 条 (含 3 条 P43 巡检) |
| X3 价值 | `.omo/_truth/x3-value-stack.yaml` | 11 域覆盖 + P43 closed-loop metrics |
| X4 一致性 | `.omo/_truth/x4-consistency-rules.yaml` | 4 条 (含 2 条 P43 SSOT) |
| 治理面 SSOT | `.omo/standards/omo-governance-surfaces.md` | 三层契约 |
| 版本历史 | `.omo/_truth/mof-version.yaml` | v0.0.6 → v0.0.12 (6 步演进) |

## 闭环模式 (可复用范式)

```yaml
# c2g → omo → mof 闭环模式
Pattern:
  Step 1: c2g brainstorm
    command: "cd projects/c2g && uv run c2g --adapter local brainstorm '<topic>'"
    output: runtime/sandbox/pitches/<slug>.md

  Step 2: 补 Upstream/Appetite
    file: runtime/sandbox/pitches/<slug>.md
    required: Upstream (北星锚点) + Appetite (边界)

  Step 3: omo governance ingress-task
    command: "omo governance ingress-task <yaml> --ingress-plane projects/c2g"
    broker: omo_ingress.py:create_planned_task + fcntl lock + history

  Step 4: omo governance ingress-debt (修复型)
    command: "omo governance ingress-debt <yaml> --ingress-plane projects/c2g"
    broker: omo_ingress.py:upsert_debt_item + audit log + governance history

  Step 5: bin/mof-version record
    command: "bin/mof-version record '<description>'"
    output: .omo/_truth/mof-version.yaml (v+1)

  Step 6: omo governance 重跑 + mof-enforce post-check
    commands:
      - "omo governance"  # 6 项检查 → score
      - "bin/mof-enforce post-check"  # 0 drift 校验

  Step 7: git commit + submodule pointer bump
    workflow:
      - "git commit -m '...'"
      - "cd projects/<x> && git commit + bump root pointer"
      - "push (NOT automatic, manual only)"
```

## 6 个 P43 commit 的可复用性

| Round | commit count | 可复用度 |
|-------|-------------:|---------|
| R1 debt closure | 1 | **高** — broker upsert 模式可复用任意 debt 项 |
| R2 kairon F821 | 2 | **中** — 缺 typing import 模式可脚本化扫描 |
| R3 c2g tests | 2 | **高** — 41 测试模板可复用其他模块 |
| R4 4 subprojects | 4 | **低** — 一次性清理 |
| R5 3 subprojects + lint | 3 | **低** — 一次性清理 |

**结论**: R1+R3 的 broker-driven 闭环模式是 **可复用最佳实践**, R2/R4/R5 是 **一次性治本**, 应沉淀到 onboarding 文档供后续 P 阶段参考。