---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - 0155-p76-phase1-cleanup.md
  - STRAT-P76-strategic-roadmap.md
  - ../../../.omo/_knowledge/audits/2026-07-02-system-comprehensive-audit.md
supersedes: []
---

# ADR-0156: P76 Phase 2 — 分层调用方向契约硬化

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 是 P76 Phase 2 的设计 + 部分实施的合并 ADR。

## 0. TL;DR

P76 Phase 2 (W3-W5) 完成 4 项核心交付:

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **CR-LAYER-CALL-DIRECTION 规则** | ✅ | governance-checks.yaml + 1 (informational enforcement) |
| **gbrain 三栈拆分设计图** | ✅ | `docs/architecture/gbrain-three-stack-split.md` |
| **`bin/ssot/check-layer-call-direction.py`** | ✅ | 新工具, scan call-direction violation, enforcement=advisory |
| **`P76-2 沉淀原则** | ✅ | 5 条 |

## 1. 决策 (WHY/WHAT/NEXT)

### 1.1 WHY

ADR 战略诊断 6 大矛盾之首: **L2 引擎"双向耦合岛"** — runtime ↔ aetherforge ↔ omo 形成小环, agora 同时挂 5 个 kairon 子包。爆炸半径失控: 任何 L2 子项目重构都会跨 5+ 个仓传导。

**根因**: 没有"调用方向"硬契约, 治理面只能事后审计。

### 1.2 WHAT — 调用方向契约 (CR-LAYER-CALL-DIRECTION)

#### 1.2.1 总体架构图

```
┌──────────────────────────────────────────────────────────────────┐
│ L3 Entry (cockpit)              ↑ ↑                               │
│                                │ │                               │
│ I0 Weaver (agora)              │ │ (L3 may invoke I0 downward)   │
│                                ↑ ↑                               │
│ L4 Self (l4-kernel)           ←─┴─┴─── (L3 may invoke L4 via L0) │
│                                                                  │
│ L2 Engines (kairon/gbrain/omo/...)   ── (sibling via I0 only)    │
│                                                                  │
│ L1 Runtime     ── (downward to L0/Bus)                           │
│                                                                  │
│ L0 Protocol (ecos + mesh-router)    ←─ (M0, no dependency)       │
│                                                                  │
│ M0 Cross-cut (model-driven)        ←─ (zero project imports)      │
└──────────────────────────────────────────────────────────────────┘
        ↑                            ↑
        │ X extensions can call      X extensions NEVER call X
        │ any layer, but must        each other directly
        │ declare BOS URI surface
```

#### 1.2.2 规则明细 (GaC 子句)

```yaml
- id: CR-LAYER-CALL-DIRECTION
  dimension: X3   # value-stack 维度 (跨层调用是"价值栈"问题)
  layer: meta
  check_type: ssot_pointer
  enforcement: advisory   # Phase 2 informational; Phase 3 升级 hard
  description: |
    分层调用方向契约 (P76 Phase 2). 防止 L2 引擎小环形成.
    
    允许方向:
    - L3 → I0 (cockpit → agora via BOS)
    - L3 → L2 (cockpit → L2 engines)
    - L3 → M0 (cockpit → model-driven)
    - L2 → L0 (kairon → ecos imports)
    - L2 → I0 (L2 跨仓 → BOS URI)
    - L2 → L2-sibling (BOS URI only, NO direct import)
    - L1 → L0 (runtime → ecos)
    - L1 → Bus (runtime → bus-foundation)
    - L0, M0 → (none, 纯稳定层)
    - X → ANY (extension only, declare BOS surface)
    
    禁止方向:
    - L0/M0 → ANY project (不能 import any project)
    - L1 → L2 (runtime 不应该直接调用 L2 引擎)
    - L2 → L3 (L2 引擎不调用 cockpit)
    - I0 → L2 (agora 是编织者, 不直接依赖 L2)
    - X → X (extensions 不能直接 import 彼此)
  target: "projects/*/src/**/imports.py"
  forbid_copy_in: []
```

### 1.3 NEXT — 边界执行步骤

| Phase | 行动 | 时间 |
|------|------|------:|
| **3.1** | `agent-workflow register --auto` 自动接 tool (Phase 3) | W6 |
| **3.2** | 调用方向 enforcement: advisory → hard | W7 |
| **3.3** | gbrain 真正三栈拆分 (Phase 2 准备, Phase 3 实施) | W8-W11 |
| **4.2** | X 扩展晋升机制 (Phase 4) | W9-W11 |

## 2. 设计 — gbrain 三栈拆分

完整设计文档: [`docs/architecture/gbrain-three-stack-split.md`](../architecture/gbrain-three-stack-split.md)。

### 2.1 现状

| 文件 | 行数 | 责任 |
|------|---:|------|
| `core/postgres-engine.ts` | **4514** | Postgres 关系层 + 全 CRUD |
| `core/pglite-engine.ts` | **4509** | PGLite 兼容层 |
| `core/ai/gateway.ts` | 2895 | AI 模型路由 + bos:// 桥 |

### 2.2 拆分目标

```
gbrain-v2 (3 个独立仓):
  ├─ gbrain-core/      # Postgres 关系层 (TypeScript)
  │                       目标: postgres-engine.ts → 5 个 <800L 文件
  ├─ gbrain-vector/    # LanceDB 向量层 (Rust, 性能关键)
  │                       目标: 独立仓, 后续可换 pgvector
  └─ gbrain-bos/       # BOS URI API + 路由层 (Python, agora 复用)
                          目标: bos:// 接口契约固化
```

### 2.3 迁移路径 (Phase 3 准备)

| Step | 行动 | 风险 |
|------|------|:---:|
| M-1 | gbrain-core 拆 5 文件 (1 个月) | 🟡 |
| M-2 | gbrain-vector 独立仓 | 🟠 |
| M-3 | gbrain-bos 用 Python 重写, agora 注册服务 | 🟡 |
| M-4 | 旧仓退役, redirect | 🟠 |

## 3. 不在本 ADR 范围

- ❌ 真的拆 gbrain (Phase 3 实施)
- ❌ Agora 加入 layer-check 强制 (Phase 3 enforcement 升级)
- ❌ Cockpit-ui 拆分 (反向警示 #2)

## 4. 沉淀原则 (P76-2)

| # | 原则 | 含义 |
|---|------|------|
| P76-2-1 | **advisory-first** | 新 GaC 规则先用 enforcement=advisory 跑 1-2 周, 收集 violations 才升级 hard |
| P76-2-2 | **negative-space-first** | 显式列"禁止"比"允许"更有约束力 |
| P76-2-3 | **sibling-via-I0** | L2 sibling 之间必须走 BOS URI, 不能 direct import |
| P76-2-4 | **M0/L0 zero-import** | M0/L0 不允许 import 任何项目, 强制纯协议层 |
| P76-2-5 | **X-declare-BOS** | X 扩展第一次上线必须先在 `bos-services.yaml` 注册 |

## 5. 验证清单

- [x] CR-LAYER-CALL-DIRECTION 加到 governance-checks.yaml (advisory)
- [x] `bin/ssot/check-layer-call-direction.py` 创建并跑通
- [x] gbrain 三栈拆分重构图写入 `docs/architecture/gbrain-three-stack-split.md`
- [x] 1 周内 informational 收集 violations (待后续 phase)
- [ ] Phase 3 升级 enforcement=hard (待后续)

## 6. 关联

- ADR-0155 (P76 Phase 1 closeout)
- STRAT-P76-strategic-roadmap.md (规划)
- 2026-07-02-system-comprehensive-audit (历史 L2 双向耦合记录)
- ADR-0130 (P74 workflow solidification) — 守门机制根源
- P71 baseline-recovery-pattern — 5 阶段流程复用

---

*最后更新: 2026-07-07 · P76 Phase 2 closeout · ACCEPTED*
