---
status: PROPOSED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - ../audits/2026-06-29-l0-ssot-m0-mof-alignment.md
  - ../audits/2026-06-28-comprehensive-system-audit.md
  - ../patterns/p71-baseline-recovery-pattern.md
  - ../patterns/p72-follow-up-completion-pattern.md
  - ../patterns/p74-workflow-solidification-pattern.md
  - 0115-p52-model-driven-8-stages.md
  - 0117-p52-undo-p60-stage-8.md
  - 0128-state-generation-concurrency.md
  - 0129-state-projection-plane-phase3.md
  - ../../../projects/ecos/src/ecos/ssot/mof/m3.yaml
  - ../../../projects/ecos/src/ecos/ssot/LAYER-L0.yaml
  - ../../../projects/ecos/src/ecos/l0/ssot/meta_model.py
  - ../../../../docs/M4-ROADMAP.md
precedents:
  - 0054-p60-governance-internalization.md
  - 0090-mof-schema-design.md
  - 0091-layer-modeling-spec.md
supersedes: []
---

# ADR-0132: L0 / M0 / MOF 统一元模型 (M4 升级)

> **For agentic workers**: REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`。
> **本 ADR 是 PROPOSED 状态**,接受需通过 superpowers:brainstorming + ADR review。
> 决策点 (5 开关) 默认走 §6 "default branch",如采用非默认值需单独标注。

---

## 0. TL;DR

**单一论断**: 整个 eCOS v6 应该用**单一 M4 元元模型**覆盖 L0 (协议层) / M0 (model-driven 横切) / MOF (元架构) 三者,消除 6 个闭环缺口,达成 14 周 5 阶段可持续演进。

| 维度 | 重构前 | 重构后 |
|------|--------|--------|
| L0-constraints 在 M3 闭环 | ❌ 双轨 | ✅ m3_parent 锚通 |
| meta_model.py ↔ m3.yaml | ❌ 双轨 | ✅ 单轨桥接 |
| M0 model-driven 7 阶段 闭环 | ❌ 无 | ✅ m3_parent "MetaProcess"  |
| mof-validate.py 通过率 | 1315/1366 (96.27%) | ≥1355/1366 (99.19%) |
| M2 schema 闭环 | 49 (含 8 loader bug) | 49+(loader bug fix) + 3 新 M2 (ConstraintL0/M0Stage/Gate) |
| L0-constraints 元数据 | 7 字段扁平 | 12 字段含 m3_parent/severity/relationConstraints/confidence |
| 派生面 | 双源(SSOT + .omo/state) | 单源(SSOT + .omo/_derived,gitignored,ADR-0129) |

**5 阶段 (14 周)**:

| 阶段 | 周 | 目标 | PR |
|------|-----|------|-----|
| P1-S0 | W1 | mof-validate loader bug fix + 基线快照 | PR1 |
| P1-S1 | W2 | 新 M2 ConstraintL0 schema | PR2 |
| P1-S2 | W3-4 | L0-constraints 1065 条 v2 迁移 (双轨) | PR3 |
| P1-S3 | W5 | 切 ADR 接受 v2 + 监控 | PR4 |
| P2-S1 | W6-7 | M3-meta schema (新文件,m3.yaml 不动) | PR5 |
| P2-S2 | W8-9 | mof_bridge.py 桥接器 | PR6 |
| P2-S3 | W10 | M0 engine m3_parent 暴露 (mof-driven.py 新文件) | PR7 |
| P2-S4 | W11 | 自反校验 (mof-bootstrap check_3) | PR8 |
| P3 | W12 | 派生面统一 (单源,gitignored) | PR9 |
| P4 | W13-14 | 切 ADR-0133 + 38 回归测试 | PR10 |

---

## 1. 触发与上下文

### 1.1 用户意图

> "理解一下当前项目情况" + "L0 全面抽象建模,A+B 都要,按最理想态落地"

**澄清: 用户给的 "按最理想态落地"**:
- ❌ "最理想态" ≠ 一次性大爆炸式重构(违反 P74+P72 已证明的"分阶段 + 路径不过载")
- ✅ "最理想态" = 用最严谨的工程标准,把方案做到完整闭环、可演进、可回滚
- ✅ 忽略历史包袱 = 不被"现状兼容"反绑架,新方案可以**重构**而不是"修补"

### 1.2 触发动机 (3 个实证)

1. **P72 历史教训**: model-driven 8 阶段错改(P60)→ 15 测试 fail → ADR-0117 撤销。这次不在 P60 同样位置再踩坑。
2. **mof-validate 实证基线 (2026-07-06)**: 1366 节点,1315 通过,**70 错误中 8 类 M2 schema 加载失败**(大小写 bug,1 行正则可修)。
3. **P74 compliance 实证**: c2g-spec-ingress 仍 warn,代表新方案必须在 workflow 闭环内做,不能引发更多 silence。

### 1.3 现状(基于 2026-07-06 worktree e2f8f4d7 实证)

| 层 | 实体 | 自反 | 与上下游闭环 |
|----|------|------|--------------|
| M3 (mof/m3.yaml) | 4 大类 Element | ✅ (mof-bootstrap self) | — |
| M2 (mof/m2/*.yaml) | 49 schema, 100% m3_parent | ✅ | → M1 |
| M1 (mof/m1/*.yaml) | 1366 节点 (49 目录) | ✅ | ← M2 |
| M0 (mof/m0/snapshot.yaml) | 1 yaml + model-driven 引擎 | ✅ | ← M1 |
| **L0-constraints** (registry/L0-constraints.yaml) | 1065 条 7 元组 | **❌ 无 m3_parent** | **❌ 与 M2 不通** |
| **meta_model.py** (l0/ssot/meta_model.py) | 8+4+4 MET + 6 YAML schema | **❌ 与 m3 双轨** | **❌ 与 m3.yaml 不通** |
| **M0 model-driven 7 阶段** (projects/model-driven) | lifecycle.py 状态机 | **❌ 元模型级无** | **❌ P52 撤销 8 阶段** |

**6 个闭环缺口** (逐一对应方案阶段):

| 缺口 | 修复 |
|------|------|
| L0-constraints 不在 M3 闭环 | P1 阶段加 `m3_parent: ConstraintL0` |
| meta_model.py 与 m3.yaml 双轨 | P2 阶段 m3-meta.yaml 桥接 |
| M0 model-driven 引擎自反 | P2 阶段 mof-driven.py 暴露 M0Stage |
| mof-validate 70 错误 | P1-S0 一行修复 + 8 类 schema 排查 |
| 派生面双源 | P3 阶段 gitignored 派生面 (ADR-0129) |
| 132 GaC 规则 ↔ L0 constraints 对应不明 | P1-S2 统计 + P4 文档化 |

---

## 2. 决策

### 2.1 核心决策

**单一 M4 元元模型**采用三层结构:

```
M3-meta.yaml (新增,ssot/mof/m3-meta.yaml, P2 阶段)
    ↑ 自反 (M3 锚定自身)
m3.yaml (现有,不动)
    ↑ m3_parent (49/49 schema,已有)
mof/m2/*.yaml (现有 49 + 新 3)
    ↑ entity_type (1366 + L0-constraints 1065 迁移)
mof/m1/*.yaml + L0-constraints-migrated.v2 (gitignored 派生面)
    ↑ MetaType 八类映射 (meta_model.py)
meta_model.py (现 674 行,改造 read-only)
    ↑ bridge
L0 + M0 引擎
```

### 2.2 关键决策点(5 个,逐项裁决)

#### D1: 双轨 vs 单轨

**单轨**: 用一份 schema 替代两套
**双轨**: 旧 schema 保留,新建一份,验证通过后切换

**决策: 双轨。** (理由: 5+4+1+1 架构强调"路径不过载",P72 教训,永远留兜底)

#### D2: L0-constraints schema 增强幅度

**选项 A**: 7→8 字段 (最小: 加 m3_parent)
**选项 B**: 7→12 字段 (加 m3_parent + severity + relationConstraints + confidence + stateMachine 引用 + examples)
**选项 C**: 7→7 (维持现状,只元数据)

**决策: B (12 字段)。** 因为用户明确"忽略历史包袱",且 M2 ConstraintMgmt 已含 stateMachine/severity/blocks/fix_action/validationRules 5 维度,7 字段不够。

#### D3: meta_model.py ↔ m3.yaml 关系

**A. 8 类迁入 m3.yaml**: 删 meta_model.py,在 m3.yaml 内多 8 类 Element 子类
**B. m3.yaml 迁入 meta_model.py**: 用 8+4+4 替代 m3.yaml 的 4 大类 Element
**C. 双轨桥接**: meta_model.py 保留为 read-only check helper,m3.yaml 不动,新增 m3-meta.yaml 暴露桥

**决策: C (双轨桥接)。** 理由: A 风险极高(m3.yaml 是 P60 ADCP 创世文件),B 完全破坏 P60+P74 历史。

#### D4: M0 model-driven 与 M4 闭环

**A. 改 model-driven 7→8 阶段 (复活 P52)**: 立刻加回 GOVERNING_MAINTENANCE
**B. 暴露 mof-driven.py 桥接器**: model-driven 引擎不动,只暴露其 7 阶段到 M3-meta 的 MetaProcess
**C. 冻结**: 不动 model-driven

**决策: B (暴露桥接)。** 理由: A 直接违反 ADR-0117 撤销决定;C 无收益。

#### D5: L0-constraints 历史保留

**A. 永久保留 + gitignored**: 派生面范式(ADR-0129)
**B. 1 年后删**: 冷却期
**C. 切完即删**: 极简主义

**决策: A (永久保留 + gitignored)。** 理由: ADR-0129 投影面范式已确立,符合 gitignored 派生面原则。

---

## 3. 实施路径 (5 阶段 / 14 周 / 38 个里程碑)

完整路线图见 `docs/M4-ROADMAP.md`。本 ADR 只列 Phase 0-4 的**核心产出版本控制点**。

### Phase 0: 基线快照 (本会话已落)

- ✅ `bin/gac-worktree.sh claim m4-metamodel-v1` 创建隔离 worktree (branch `work/m4-metamodel-v1` 从 `e2f8f4d7`)
- ✅ mof-validate.py 基线: 1366 节点 / 1315 通过 / 70 错误 (5.13%)
- ✅ mof-m2-coverage 基线: 49 M2 schema
- ✅ P74 compliance: continue (run_count=56, ok=true)
- ✅ 增量记录: `.omo/debt/m4-baseline-snapshot.md`

### Phase 1 (P1): L0 ↔ M2 闭环 (W1-W5)

#### P1-S0: loader bug 一行修复 + 基线复测 (W1)

**A. 主仓 PR1**: 修 `bin/mof-validate.py` loader 大小写正则
**B. ecos 子模块 PR1**: 同 fix(若两边都有)
**C. 验收**: 70 错误 → ≤10 错误 (95% 修复)

#### P1-S1: 新 M2 ConstraintL0 schema (W2)

**A. 文件**: `projects/ecos/src/ecos/ssot/mof/m2/constraint_l0.yaml` (新增)
**B. content**: `m3_parent: ConstraintMgmt` + 12 required + optionalProperties + stateMachine(沿用 7 态) + relationConstraints
**C. 验收**: `mof-bootstrap check_3` 全绿

#### P1-S2: L0-constraints 1065 条 v2 迁移 (W3-W4)

**A. 文件**: `bin/l0-constraints-migrate.py` (新增,~200 行)
**B. output**: `L0-constraints.v2.yaml` (gitignored,ADR-0129) + `docs/generated/l0-constraints-migration-report.md`
**C. 验收**: 1065 条全部通过 ConstraintL0 校验 + 132 GaC rules 引用未变 + 双轨 1 周

#### P1-S3: 切 ADR (W5)

**A. 文件**: `bin/l0-constraints-cutover.sh` (新增)
**B. 流程**: 1 周 monitor → 若 v2 100% 绿 → 写 ADR-0133 接受 → 删除 v1 入口(物理保留,gitignored)
**C. 验收**: `mof-validate.py` PASS,GaC gate PASS,gac-drift 0

### Phase 2 (P2): meta_model ↔ mof 闭环 (W6-W11)

#### P2-S1: M3-meta schema (W6-W7)

**A. 文件**: `projects/ecos/src/ecos/ssot/mof/m3-meta.yaml` (新增)
**B. content**: 8 MET-Entity + 4 MET-Relation + 4 MetaConstraint 映射 m3.yaml Element 子类
**C. 验收**: `mof-bootstrap check_4` (新增) 全绿

#### P2-S2: mof_bridge.py 桥接器 (W8-W9)

**A. 文件**: `projects/ecos/src/ecos/l0/ssot/mof_bridge.py` (新增)
**B. 接口**: `M3MetaLoader` + `check_meta_relation_allowed` + `compute_meta_confidence`
**C. 验收**: 单测 100% pass (target 24 个 test)

#### P2-S3: M0 引擎暴露 (W10)

**A. 文件**: `projects/ecos/src/ecos/ssot/mof/m0/mof-driven.py` (新增,~150 行)
**B. content**: 把 `model-driven/lifecycle.py` 7 阶段暴露为 m3_parent="MetaProcess" 的 M0 实例
**C. 验收**: `mof-audit` 跑过,M0 snapshot yaml 含 7 阶段节点

#### P2-S4: 自反校验 (W11)

**A. 文件**: `bin/mof-bootstrap.py` (增强,加 check_3 + check_4)
**B. 验收**: 全部 schema 自反 100%

### Phase 3 (P3): 派生面统一 (W12)

**A. 文件**: 
  - `bin/omo-state-cleanup.py` (新增) — 把 `.omo/_derived/` 路径收口
  - `.gitignore` 加 `.omo/_derived/` + `**/L0-constraints.v2.yaml`
**B. 验收**: `git status` 不再 .omo/_derived/ 噪声

### Phase 4 (P4): 切 ADR + 38 回归测试 (W13-W14)

**A. 文件**: 
  - `.omo/_knowledge/decisions/0133-l0-constraints-v2-cutover.md` (新增)
  - `tests/integration/m4_metamodel/` (新增,~38 测试)
**B. 验收**: `make test-integration` 全绿 + P74 compliance ok + mof-validate 99%+

---

## 4. 风控 (P72 原则)

### 4.1 不可逆操作 (P72 红线)

| 操作 | 是否做 | 兜底 |
|------|--------|------|
| 删 L0-constraints.yaml v1 | ❌ **绝不** | v1 gitignored 永久保留 |
| 改 m3.yaml 字段 | ❌ **绝不** | 新增全部走 m3-meta.yaml |
| 改 meta_model.py 公开 API | ❌ | 仅内部重构,8+4+4 enum 顺序不变 |
| 删除 model-driven 7 阶段 | ❌ | 永远不动 |
| 改 132 GaC 规则 schema | ❌ | 全部 P1-S2 增量加字段 |
| 单 commit 跨 lane | ❌ | P72 原则 4,单 lane |

### 4.2 回滚机制 (每阶段独立 PR)

- 每个 phase 一个独立分支
- PR fail → revert 不影响其他 phase
- ADR-0129 派生面范式兜底一切 gitignored

### 4.3 验证证据 (每阶段)

| 验证 | 工具 | 期望 |
|------|------|------|
| M3/M2 自反 | `bin/mof-bootstrap.py check_3 check_4` | 全绿 |
| M2→M1 | `mof-validate.py` | 99%+ |
| L0-constraints v2 | `l0-constraints-migrate.py --validate` | 1065/1065 |
| GaC gate | `make gac-local-gate` | 全绿(非 subspace init FAIL) |
| P74 | `agent-workflow.py compliance` | continue |
| evidence | `bin/evidence-smoke.py` | 1.0 |
| M2 coverage | `bin/mof-m2-coverage.py` | ≥49 |
| Meta-bridge | `pytest tests/l0/test_mof_bridge.py` | 100% |

---

## 5. 关联与影响

### 5.1 上游依赖

- ADR-0128 (state generation concurrency) — 派生面范式前置
- ADR-0129 (state projection plane) — gitignored 派生面范式前置
- ADR-0130 (P74 workflow solidification) — workflow 治理已落地
- `Plans/3-130-adr-greedy-micali.md` — P0-P3 治理债务必须先清

### 5.2 下游影响 (跨仓 caller)

| Caller | 影响 | 兜底 |
|--------|------|------|
| projects/cockpit | 引用 L0-constraints id 字符串 | 不强改,验证 grep 命中数前后相等 |
| projects/omo | 引用 X1-C01 等 id | 同 |
| projects/agora | BOS URI 引用 ConstraintMgmt | P1 不触 X1-C01 |
| projects/runtime | 类似 | 同 |
| projects/family-hub | 类似 | 同 |
| projects/model-driven | 引擎不改 | P2 仅暴露桥接 |

### 5.3 ADR 链

- ADR-0132 (本 ADR, PROPOSED) — 主决策
- ADR-0133 (P1 切 v2, PROPOSED → ACCEPTED 当 P1-S3 完成)
- ADR-0134 (P2 切 M3-meta, PROPOSED → ACCEPTED 当 P2-S4 完成)
- ADR-0135 (派生面统一, PROPOSED → ACCEPTED 当 P3 完成)

---

## 6. Default Branch / How To Override

本 ADR 的 5 开关**默认走**:
- D1 双轨
- D2 12 字段 (B)
- D3 双轨桥接 (C)
- D4 暴露桥 (B)
- D5 永久保留 gitignored (A)

若采用非默认,reviewer 需在 PR description 标 "M4-DECISION-OVERRIDE: <开关>=<值>",否则按默认执行。

---

## 7. 不在本 ADR 范围

明确不做,防 scope creep:

- ❌ 改 projects/cockpit CLI
- ❌ 改 projects/omo broker
- ❌ 改 projects/model-driven 7 阶段引擎
- ❌ 复活 model-driven 8 阶段(可后续 ADR-0136 单独评估)
- ❌ 改 132 GaC 规则 yaml
- ❌ 改 mof-version 大版本(只 +1 小版本)
- ❌ 跨仓触达 caller schema 升级

---

## 8. 关闭标准

ADR-0132 可被关闭当且仅当:

1. 38 个里程碑全部 PR 合并
2. `mof-validate.py` 通过率 ≥99%
3. `make test-integration` 全绿
4. P74 compliance `decision: continue` 持续 4 周
5. ADR-0133 + ADR-0134 + ADR-0135 全部 ACCEPTED

否则保持 PROPOSED,继续推进。

---

## 9. 决策点(待审议)

### 9.1 决策清单

| # | 决策 | 默认 | 评审 |
|---|------|------|------|
| D1 | 双轨 vs 单轨 | 双轨 | ☐ |
| D2 | schema 字段 7→? | 12 字段 (B) | ☐ |
| D3 | meta_model ↔ m3 | 双轨桥接 (C) | ☐ |
| D4 | M0 闭环 | 暴露桥 (B) | ☐ |
| D5 | L0-constraints v1 | 永久保留 gitignored (A) | ☐ |

### 9.2 实施开关

- ☐ 同意本 ADR 进入 ACCEPTED
- ☐ 跳过 P1-S0 (loader 修复),直接进 P1-S1 (新 schema) — 不推荐,会让基线漂移
- ☐ 跳过 P2-S3 (M0 暴露),直接进 P3 — 不推荐,M0 闭环是 user 的明确需求
- ☐ 推迟 P3 (派生面统一) 到 M5 — 可接受,但需单独 ADR

### 9.3 命名 / 路径

- `ssot/mof/m3-meta.yaml` (推荐)
- `ssot/mof/m3_unified.yaml` (备选)
- `l0/ssot/mof_bridge.py` (推荐)
- `l0/ssot/metamodel_v2.py` (备选)

---

## 10. 变更日志

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-07-06 | 初稿 PROPOSED | Crush (eCOS v6 M4 方案) |
