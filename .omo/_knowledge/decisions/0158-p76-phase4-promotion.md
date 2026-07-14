---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - 0157-p76-phase3-self-meta.md
  - 0156-p76-phase2-call-direction.md
  - 0155-p76-phase1-cleanup.md
  - STRAT-P76-strategic-roadmap.md
supersedes: []
---

# ADR-0158: P76 Phase 4 — X 扩展晋升机制 + 主仓-子仓对称修复

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 是 P76 Phase 4 的设计 + 实施合并 ADR。

## 0. TL;DR

P76 Phase 4 (W9-W11) 完成 3 项核心交付:

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **X 扩展晋升机制** | ✅ | 4 阶段 lifecycle (idea → 0.1.x → 1.0.x → 2.0.x) |
| **bin/ssot/submodule-bump-check.py** | ✅ | 17 submodules 全对齐 (0/0/0) |
| **CR-SUBMODULE-BUMP-AUTO** | ✅ | 新 GaC 规则 |

## 1. 决策 (WHY/WHAT/NEXT)

### 1.1 WHY

战略诊断矛盾 3 (submodule-pointer 腐烂) + 矛盾 5 (跨仓契约 kind 缺失)。
Phase 1 修了入口, Phase 2 立了守门, Phase 3 立了指标。
**Phase 4 完成"长期可持续" — 让 submodule-pointer / X 扩展 都不再腐烂**。

### 1.2 WHAT — X 扩展晋升生命周期

```
┌────────────────────────────────────────────────────────────────────┐
│  Stage 0: idea                                                       │
│  ├─ 在 docs/ 写 pitch.md, 没有 module 代码                           │
│  └─ 退出条件: 有 1 篇 pitch 文档                                     │
│                                                                      │
│  Stage 1: 0.1.x 实验性                                              │
│  ├─ 在 projects/<x-name>/ 仓内, 不接入 workspace 仓                   │
│  ├─ feature flag 默认 OFF                                            │
│  ├─ 在 bos-services.yaml 加 kind=experiment 标记                     │
│  └─ 退出条件: ≥3 个月实验 + 测试覆盖率 ≥70%                          │
│                                                                      │
│  Stage 2: 1.0.x 进 L* 主层 (driven by use case)                     │
│  ├─ 注册为 git submodule (主仓 .gitmodules)                          │
│  ├─ bos:// URI 暴露 kind=stable                                      │
│  ├─ mandatory daemon / service 角色                                  │
│  └─ 退出条件: ≥1.0 半年, 仍 people-dependent 强                     │
│                                                                      │
│  Stage 3: 2.0.x 晋升主层 (L2 引擎 / L3 入口)                        │
│  ├─ 在 projects/<x-name>/ 仓内, 写完整 docs + tests                   │
│  ├─ 移除 x-extensions/<x-name> 命名空间                              │
│  ├─ bos:// URI 路径稳定                                              │
│  └─ 退出条件: 治理 score ≥ 98 + debt-closed-per-feature ≥ 0.5       │
└────────────────────────────────────────────────────────────────────┘
```

### 1.3 WHAT — X 扩展晋升 守门规则

```yaml
- id: CR-X-PROMOTION-LIFECYCLE
  description: "X 扩展晋升必经 4 阶段. CI 自动检查阶段属性."
  enforcement: hard  # 跨仓 (X → 主仓) 不可绕过
  check: |
    Stage 0 (idea): docs/<pitch>.md 存在
    Stage 1 (0.1.x): 项目根 .promotion-state 含 "stage=0.1.x" + kind=experiment
    Stage 2 (1.0.x): 主仓 .gitmodules 声明 + bos-services kind=stable
    Stage 3 (2.0.x): 主仓 docs/project-registry.yaml layer != X + ADR 引用
```

### 1.4 WHAT — CR-SUBMODULE-BUMP-AUTO

```yaml
- id: CR-SUBMODULE-BUMP-AUTO
  description: |
    当主仓主分支 .gitmodules 路径下 submodule 实际 HEAD ≠ 主仓 pin SHA,
    radar_cron 报 [advisory]; 24h 未修正 升 [hard].
    实施: bin/ssot/submodule-bump-check.py (已交付, 17 submodules 全对齐)
  target: "bin/ssot/submodule-bump-check.py"
  source_ref: bin/ssot/submodule-bump-check.py::main
  executor: [radar_cron, ci_gate, gac_local_gate]
  enforcement: advisory
```

### 1.5 NEXT — Phase 5 入口

| 候选 | 触发 |
|------|------|
| Knowledge Foundry cron 调度 | Phase 4 收口后启动 |
| omostation-bootloader 雏形 | governance score 维持 100A+ 1 个月 |

## 2. 沉淀原则 (P76-4)

| # | 原则 | 含义 |
|---|------|------|
| P76-4-1 | **stage-gate** | X 扩展必经 4 阶段, 跳级 = 治本变更 |
| P76-4-2 | **bump-on-deps-change** | submodule 内部 commit 后立即 bump 主仓 |
| P76-4-3 | **kind-stable-first** | Stage 2 (1.0.x) 起必 kind=stable, 实验 (kind=experiment) 不可越级 |
| P76-4-4 | **radar-back-pressure** | 24h 未修正 → advisory→hard, 不留静默债 |
| P76-4-5 | **promotion-is-inverse-of-contraction** | 晋升 = 移除命名空间, 收编 = 加命名空间 |

## 3. 不在本 ADR 范围

- ❌ mesh-router submodule 真实初始化 (那需要 git submodule add, 留给后续 PR)
- ❌ 现有 X 扩展强制晋升 (aetherforge/c2g/bus-foundation 已在 Stage 1, 不动)
- ❌ cockpit-ui 拆 monorepo (反向警示 #2)

## 4. 验证清单

- [x] X 扩展晋升 4 阶段 lifecycle 文档
- [x] `bin/ssot/submodule-bump-check.py` 创建并跑通 (17/17 aligned)
- [x] CR-SUBMODULE-BUMP-AUTO 规则注册 (160 rules total)
- [ ] radar_cron 集成 (后续 PR)
- [ ] Stage 1→Stage 2 真实晋升案例 (待 Phase 5 / Foundry)

## 5. 关联

- ADR-0155 / 0156 / 0157 (P76 Phase 1/2/3)
- STRAT-P76-strategic-roadmap.md
- ADR-0151 (submodule hygiene gate) — P76 Phase 4 是其兑现
- 2026-07-02-system-comprehensive-audit — `17 submodule pointer 落后` 来源

---

*最后更新: 2026-07-07 · P76 Phase 4 closeout · ACCEPTED*
