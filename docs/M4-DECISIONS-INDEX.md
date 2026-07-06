# M4 决策速查表 (Round 4b)

> **配套 ADR-0142** (Round 4b, 2026-07-06)
> **配套**: `.omo/_knowledge/decisions/INDEX.md`(权威索引,11 条 ACCEPTED ADR)
> **配套**: `docs/M4-ROADMAP.md`(14 周路线图,5 phase 38 里程碑)

---

## M4 决策全景图

| ADR | 标题 | Round | 实施产物 | 关闭测试 |
|-----|------|-------|----------|----------|
| [0132](./../.omo/_knowledge/decisions/0132-l0-mof-m4-metamodel.md) | L0/M0/MOF 统一元模型 (M4 升级) | R0 | 5 决策 + 14 周路线图 | — |
| [0133](./../.omo/_knowledge/decisions/0133-l0-constraints-v2-cutover.md) | L0-constraints v2 派生面 双轨切单轨 | R0 | 77 条 v2 schema | T5..T8 |
| [0134](./../.omo/_knowledge/decisions/0134-m3-meta-cutover.md) | meta_model ↔ m3.yaml 双轨桥接受 | R0 | m3-meta.yaml 22 element | T9..T14 |
| [0135](./../.omo/_knowledge/decisions/0135-derived-plane-unification.md) | 派生面统一收口 (ADR-0129 enforcement) | R0 | `bin/omo-state-cleanup.py` | T22..T24 |
| [0136](./../.omo/_knowledge/decisions/0136-m3-yaml-extension-p5.md) | P5 m3.yaml 扩展 4 gap 治本 | R0 | m3.yaml ConcurrencyElement + 3 m2 名称对齐 | T25..T27 |
| [0137](./../.omo/_knowledge/decisions/0137-derived-plane-relocation.md) | 派生面落点纠偏 (Round 2a) | R2a | `bin/l0-constraints-migrate.py` 默认路径迁移 + 主仓根 `.omo/_derived/` 退役 | T7, T8, T23 |
| [0138](./../.omo/_knowledge/decisions/0138-meta-element-promotion.md) | 元元模型类目提升至 m3.yaml 主流 (R2b) | R2b | m3.yaml MetaElement/MetaEntity/MetaRelationType/MetaConstraintRule | T1..T21 (跨测) |
| [0139](./../.omo/_knowledge/decisions/0139-model-driven-8stage-revival-rejected.md) | model-driven 8 阶段复活评估 — 拒回 (R2c) | R2c | (决策保留, 0 实施) | T39, T40 |
| [0140](./../.omo/_knowledge/decisions/0140-m4-health-score.md) | M4 Health Score 量化与派生面落地 (R3b) | R3b | `bin/m4-health-score.py` + `.omo/_derived/m4-health.json` | T41, T42 |
| [0141](./../.omo/_knowledge/decisions/0141-m2-base-schema.md) | M2BaseSchema 抽象基类 + check_5 (R3a) | R3a | m2_base_schema.yaml + check_5 | T43, T44 |
| [**0142**](./../.omo/_knowledge/decisions/0142-this-doc.md) | (本文档) | R4b | docs/M4-DECISIONS-INDEX.md | — |

---

## 时间线

```
R0 (7 决策, ADR 0132..0135, 0136)
  ↓
  [Plan: Round 1 = P0/P1/P2 全闭环, 38 回归测试]

R2 (3 决策)
├── R2a [派生面落点纠偏]       ADR-0137  ←  P1-S2 follow-up
├── R2b [MetaElement 提升]      ADR-0138  ←  m3.yaml 第 7 大类
└── R2c [8 阶段复活评估拒回]   ADR-0139  ←  决策保留, 0 实施

R3 (2 决策)
├── R3b [Health Score 量化]     ADR-0140  ←  99.17/100 baseline
└── R3a [M2BaseSchema + check_5] ADR-0141 ←  4-check → 5-check strict

R4 (1 决策 + 3 follow-ups)
└── R4b [本文档速查表]          ADR-0142  ←  你正在读
```

---

## 决策原则 (积累 11 个 ADR 沉淀)

按出现频率:

### 频繁出现 (≥ 3 ADR)

| 原则 | 体现 |
|------|------|
| **P52: 元模型/正则改动连环雷** | 0139 拒回 8 阶段, 0141 不强加 m2_parent, 0137 派生面路径而非改 schema 字段 |
| **P72: 路径不过载 + 历史踩坑不重做** | 0137 派生面落点纠偏走子模块而非主仓根, 0141 m2 隐式继承而非强改 50 文件 |
| **P74: governance 自闭环 + ADR 治理** | 0140 health score 持续可观察, 0142 决策速查, 每阶段都有 ADR + 回归测试 |
| **ADR-0129 投影面范式** | 0133/0135/0137 派生面三阶段收紧 (v2 yaml + gitignored + 跟随源) |

### 一次性但重要

| 原则 | 体现 |
|------|------|
| **不改 m3.yaml / model-driven 引擎** | 0134/0136/0138/0141 都避免直接改这两个承上启下文件 |
| **双轨 vs 单轨 (D3 决策)** | 0134 双轨桥接 (m3.yaml + m3-meta.yaml), 0137 双轨保留 v1 |
| **不重做历史撤销** | 0139 拒绝复活 8 阶段 |

---

## 实施产物目录

### 主仓新增
- `bin/l0-constraints-migrate.py` (325 行, ADR-0133)
- `bin/mof-bootstrap.py` (260+ 行, ADR-0134/0136/0141)
- `bin/omo-state-cleanup.py` (226 行, ADR-0135)
- `bin/m4-health-score.py` (270 行, ADR-0140)
- `tests/integration/m4_metamodel/run_all.py` (650+ 行, 44 tests)
- `docs/M4-ROADMAP.md` (358 行)
- `docs/M4-DECISIONS-INDEX.md` (本文档, ADR-0142)

### 子模块 (projects/ecos) 新增
- `src/ecos/ssot/tools/mof-validate.py` (m2_type 优先 loader fix, ADR-0133)
- `src/ecos/ssot/mof/m2/constraint_l0.yaml` (ADR-0133, 8 required + 9 状态)
- `src/ecos/ssot/mof/m2/m2_base_schema.yaml` (ADR-0141, 抽象基类)
- `src/ecos/ssot/mof/m3.yaml` (增 +5 element: ConcurrencyElement, MetaElement, MetaEntity, MetaRelationType, MetaConstraintRule)
- `src/ecos/ssot/mof/m3-meta.yaml` (22 element, 15 relation matrix, ADR-0134)
- `src/ecos/l0/ssot/mof_bridge.py` (314 行, 5 API, ADR-0134)
- `src/ecos/ssot/mof/m0/mof_driven.py` (223 行, 7 阶段 + 6 transitions, ADR-0134)

---

## 测试覆盖矩阵

| 测试 ID | 主题 | Phase | ADR |
|---------|------|-------|-----|
| T1..T2 | mof-validate loader | P1-S0 | 0133 |
| T3..T4 | ConstraintL0 schema | P1-S1 | 0133 |
| T5..T8 | L0-constraints v2 migrate | P1-S2 | 0133 |
| T9..T10 | m3-meta shape | P2-S1 | 0134 |
| T11..T14 | mof_bridge 5 API | P2-S2 | 0134 |
| T15..T17 | mof_driven 7 阶段 | P2-S3 | 0134 |
| T18..T21 | 4-check strict (T21 移到 P5) | P2-S4 | 0134/0136 |
| T22..T24 | 派生面审计 | P3 | 0135 |
| T25..T27 | m3.yaml gap 治本 | P5 | 0136 |
| T28 | 4-check strict (整合) | P4 整合 | 0136 |
| T29..T34 | 5 ADR status | P4 整合 | 0132..0136 |
| T35..T36 | m2 锚通 | P5 | 0136 |
| T37 | mof-validate 无回归 | P5 守门 | 0136 |
| T38 | M4-ROADMAP 5 phase | P4 整合 | 0132 |
| T39..T40 | 8 阶段未复活 | R2c | 0139 |
| T41..T42 | M4 Health Score | R3b | 0140 |
| T43..T44 | M2BaseSchema + check_5 | R3a | 0141 |

---

## 关键数字 (R0+R2+R3+R4b 累计)

| 维度 | 数字 |
|------|------|
| M4 ADR (ACCEPTED) | 11 |
| 回归测试 | 44/44 PASS (5.5s) |
| 5-check strict | 0/0/0/0/0 |
| Health Score | 99.17/100 (mof-validate 98.62% 拉低) |
| m2 schema | 51 (含 M2BaseSchema) |
| m3.yaml elements | 33 (含 4 新 MetaElement 系列) |
| 主仓 commits | 22 (worktree ahead of main) |
| 子模块 commits | 10 (projects/ecos ahead of base) |
| 累计文件改动 | 1495+ 主仓 + 893+ 子模块 |
| 派生面 (gitignored) | 3 个: l0-constraints.v2, m0-driven, m4-health |

---

## 接下来 (Round 4 follow-ups)

| Round | 工作 | 状态 |
|-------|------|------|
| **R4c** | 8 schema date → datetime 迁移 | 待做 |
| **R4d** | OMO cron 读 m4-health.json | 待做 |
| **R4a** | MCPTOOL 19 节点占位 → 真实值 (治本 99% → 100%) | 待做 |

按用户指令"先b后啊"顺序, 本文档 (R4b) 是 R4b 工作本身的输出。
R4c/R4d/R4a 顺序执行。

---

## 维护说明

更新速查表: 任何 M4 ADR 增删必同步更新本文件。
本文件**不是** SSOT, 不写权威状态(权威状态在 ADR 自身的 status 字段 + INDEX.md)。
