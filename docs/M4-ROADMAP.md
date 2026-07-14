# M4 元模型路线图 (eCOS v6 L0/M0/MOF 统一)

> **配套 ADR**: [ADR-0132](../.omo/_knowledge/decisions/0132-l0-mof-m4-metamodel.md)
> **状态**: PROPOSED (2026-07-06)
> **周期**: 14 周 (2026-07-06 → 2026-10-12)
> **核心承诺**: 把 M3/M2/L0/M0 闭合到**单轨**,落地成可执行工程。

---

## 0. 路线图原则

1. **忽略历史包袱**: 但**保留历史** (v1 gitignored 永久保留)
2. **路径不过载**: P72+P74 双锁
3. **每阶段独立 PR**: 任何阶段失败不影响其他
4. **每阶段独立 ADR**: 切 ADR 才能 commit 进 main (5 阶段 5 个 ADR)
5. **派生面单源**: ADR-0129 范式兜底一切

---

## 1. 总览 (Executive View)

```
W1   W2   W3   W4   W5   W6   W7   W8   W9   W10  W11  W12  W13  W14
├────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┤
│ P1-S0 P1-S1 P1-S2 P1-S2 P1-S3 │ P2-S1 P2-S1 P2-S2 P2-S2 P2-S3 P2-S4 │ P3   │ P4   │
│ Loader  Constr  迁移/双轨  切 ADR │ M3-meta Schema  Bridge   M0-暴露  自反 │ 派生 │ 切+回归│
│  PR1  PR2  PR3  PR3  PR4   │  PR5            PR6     PR7    PR8     │ PR9  │ PR10 │
│ ←─ L0 ↔ M2 闭环 ──→ │   ←───── meta_model ↔ mof 闭环 ─────→    │ 单源  │ 验收  │
│                       │                                            │       │       │
└───────────────────────┴────────────────────────────────────────────┴───────┴───────┘
   Phase 1 (5 PR, L0 ↔ M2)         Phase 2 (4 PR, meta+mof)         P3(1PR) P4(1PR)
```

---

## 2. Phase 0: 基线快照 (✅ 已完成)

| ID | 任务 | 状态 | 产物 |
|----|------|------|------|
| P0-1 | worktree 隔离 claim | ✅ | `work/m4-metamodel-v1` from `e2f8f4d7` |
| P0-2 | mof-validate 基线 | ✅ | 1366 节点 / 1315 通过 / 70 错误 |
| P0-3 | mof-m2-coverage 基线 | ✅ | 49 schema |
| P0-4 | P74 compliance | ✅ | continue (run=56,event=454) |
| P0-5 | baseline snapshot | ✅ | `.omo/debt/m4-baseline-snapshot.md` |

---

## 3. Phase 1 (P1): L0 ↔ M2 闭环

**目标**: L0-constraints 1065 条进入 M3 闭环,mof-validate 通过率 96.27% → 99%+

### P1-S0: Loader bug 一行修复 (W1)

| ID | 任务 | 工时 | 产物 |
|----|------|------|------|
| P1-S0-1 | 修复 `bin/mof-validate.py` 大小写 loader | 0.5h | PR1 commit |
| P1-S0-2 | 复测 70 错误 | 1h | `mof-validate.py` 输出 |
| P1-S0-3 | 验证 8 个 M2 schema 加载 | 0.5h | grep test |
| P1-S0-4 | PR 提交 + review | — | PR1 merge |

**验收**:
- [ ] 70 错误 ≤ 10 (即 95% 修复)
- [ ] 8 个 schema 加载成功(AvailabilityCheck, ComputeEngine, ComputeNode, HardwareAsset, NetworkZone, QuotaDefinition, RoutingPolicy, VaultPath)
- [ ] `make gac-local-gate` PASS (非 subspace init 维度)

### P1-S1: 新 M2 ConstraintL0 schema (W2)

| ID | 任务 | 工时 | 产物 |
|----|------|------|------|
| P1-S1-1 | 设计 12 字段 schema | 4h | `constraint_l0.yaml` draft |
| P1-S1-2 | 写入 m3_parent/stateMachine/relationConstraints | 4h | 49+1 M2 schema |
| P1-S1-3 | mof-bootstrap check_3 自反 | 2h | 自反 PASS |
| P1-S1-4 | PR2 + review + merge | — | PR2 merge |

**验收**:
- [ ] `bin/mof/mof-bootstrap.py check_3` 全绿
- [ ] `bin/mof-schema-validate.py` 接受 constraint_l0 类型
- [ ] 132 GaC 规则未触(grep 验证)

### P1-S2: L0-constraints 1065 条 v2 迁移 (W3-W4)

| ID | 任务 | 工时 | 产物 |
|----|------|------|------|
| P1-S2-1 | 写 `bin/l0-constraints-migrate.py` | 8h | ~200 行 |
| P1-S2-2 | 单条迁移 dry-run | 4h | sample.txt |
| P1-S2-3 | 全量迁移 1065 条 | 2h | `L0-constraints.v2.yaml`(gitignored) |
| P1-S2-4 | 写 migration report | 4h | `docs/generated/l0-constraints-migration-report.md` |
| P1-S2-5 | 双轨 1 周 (本阶段重叠 1 周) | 4×5d | monitor |
| P1-S2-6 | PR3 + review + merge | — | PR3 merge |

**迁移映射表**(简化版,完整见 PR3):

| v1 字段 | v2 字段 | 转换规则 |
|---------|---------|----------|
| `applies_to: [L0, L1]` | `applies_to: [L0, L1]` (不变) | 直接保留 |
| `dimension: X1` | `dimension: X1` (不变) | 直接保留 |
| `type: required` | `severity: high` | `required→high`,`preferred→medium`,`advisory→low` |
| `rule: "predicate"` | `rule_expr: {kind: predicate, args: "..."}` | 字符串模式 → 结构化 |
| `violation: "E-L0-001: ..."` | `violation_code: "E-L0-001"` + `violation_message: "..."` | 拆分 |
| `id: X1-C01` | `id: X1-C01` (不变) | 命名规则不动 |
| (新增) | `m3_parent: ConstraintL0` | 全 1065 条加 |
| (新增) | `half_life_days: 365` | 默认 |
| (新增) | `confidence: fact` | 默认 fact,75% |
| (新增) | `state: active` | 默认 |
| (新增) | `references: []` | 默认空 |
| (新增) | `examples: []` | 默认空 |

**验收**:
- [ ] 1065 条全部通过 ConstraintL0 校验
- [ ] 双轨 1 周无 L0-constraints 触发 bug
- [ ] 132 GaC 规则引用未变(grep `X1-C0` 命中数前后相等)

### P1-S3: 切 ADR (W5)

| ID | 任务 | 工时 | 产物 |
|----|------|------|------|
| P1-S3-1 | 监控 1 周 (前 4d 完成) | — | 监控 log |
| P1-S3-2 | 若 100% 绿,起草 ADR-0133 | 4h | `0133-l0-constraints-v2-cutover.md` |
| P1-S3-3 | PR4 (切 ADR) + review + merge | — | PR4 merge |
| P1-S3-4 | v1 yaml → gitignored,但文件保留 | 1h | `.gitignore` 加 |

**验收**:
- [ ] v2 schema 100% 绿(连续 5 日 mof-validate 9X% 通过率)
- [ ] v1 yaml 物理保留(可读可读,但不入仓)
- [ ] `make gac-local-gate` PASS
- [ ] `agent-workflow.py compliance` `decision: continue`

---

## 4. Phase 2 (P2): meta_model ↔ mof 闭环

**目标**: 8+4+4 MET 与 m3.yaml 单轨桥接,M0 引擎暴露为 M0Stage

### P2-S1: M3-meta schema (W6-W7)

| ID | 任务 | 工时 | 产物 |
|----|------|------|------|
| P2-S1-1 | 设计 8 MET-Entity → m3 Element 子类映射 | 8h | 映射表 |
| P2-S1-2 | 设计 4 MET-Relation → m3 关系类型映射 | 4h | 映射表 |
| P2-S1-3 | 设计 4 MetaConstraint → m3 Constraint 子类映射 | 4h | 映射表 |
| P2-S1-4 | 写 `m3-meta.yaml` | 12h | 新 schema |
| P2-S1-5 | check_4 自反 | 4h | check_4 PASS |
| P2-S1-6 | PR5 + review + merge | — | PR5 merge |

**8 MET-Entity → m3 Element 子类映射**(示例):

| meta_model.MetaType | m3-meta 锚点 | 描述 |
|---|---|---|
| DOMAIN | MetaDomain → Domain (继承 Entity) | 现实实体 |
| FACT | MetaFact → Assertion (继承 Artifact) | 可验证陈述 |
| INFERENCE | MetaInference → Deduction (继承 Process) | 推导 |
| STATE | MetaState → LifecycleState (继承 StateMachine) | 状态 |
| DOCUMENT | MetaDocument → Document (继承 Artifact) | 知识载体 |
| CONSTRAINT | MetaConstraint → Constraint (继承 GovernanceElement) | 门禁 |
| PROCESSOR | MetaProcessor → Processor (继承 Process) | 处理器 |
| RELATION | MetaRelation → Relation (继承 GovernanceElement) | 边 |

**验收**:
- [ ] 8+4+4 = 16 映射 100%
- [ ] `bin/mof/mof-bootstrap.py check_4` 全绿
- [ ] m3.yaml **未触**(git diff 验证)

### P2-S2: mof_bridge.py 桥接器 (W8-W9)

| ID | 任务 | 工时 | 产物 |
|----|------|------|------|
| P2-S2-1 | 设计 M3MetaLoader API | 4h | API doc |
| P2-S2-2 | 实现 loader | 16h | ~400 行 |
| P2-S2-3 | 实现 check_meta_relation_allowed | 8h | ~100 行 |
| P2-S2-4 | 实现 compute_meta_confidence | 8h | ~80 行 |
| P2-S2-5 | 24 个单测 | 16h | `tests/l0/test_mof_bridge.py` |
| P2-S2-6 | PR6 + review + merge | — | PR6 merge |

**API 示例**:

```python
from ecos.l0.ssot.mof_bridge import M3MetaLoader

loader = M3MetaLoader(
    m3_path="ssot/mof/m3.yaml",
    m3_meta_path="ssot/mof/m3-meta.yaml",
    m2_dir="ssot/mof/m2/",
)

# 查询 MetaType → m3 anchor
anchor = loader.meta_type_to_m3(MetaType.FACT)  # → "MetaFact"

# 校验元关系
allowed = loader.check_meta_relation_allowed(
    source=MetaType.DOMAIN,
    target=MetaType.FACT,
    relation=MetaRelationType.DERIVE,
)  # → True (继承自元模型 _RELATION_MATRIX)

# 置信度聚合
score = loader.compute_meta_confidence(
    entities=[Entity(confidence=Confidence.FACT), ...]
)  # → 加权平均
```

**验收**:
- [ ] 24 个单测全绿
- [ ] meta_model.py 现有 8+4+4 enum 输出 API 兼容
- [ ] m3.yaml **未触**

### P2-S3: M0 引擎暴露 (W10)

| ID | 任务 | 工时 | 产物 |
|----|------|------|------|
| P2-S3-1 | 设计 mof-driven.py API | 4h | API doc |
| P2-S3-2 | 把 model-driven 7 阶段映射为 M0Snapshot 实例 | 16h | ~150 行 |
| P2-S3-3 | 写 M0 Stage schema | 4h | `m0/mof-driven.yaml` |
| P2-S3-4 | mof-audit 验证 | 4h | m0 snapshot 含 7 阶段 |
| P2-S3-5 | PR7 + review + merge | — | PR7 merge |

**7 阶段 → m3 MetaProcess 子类**:

| model-driven LifecycleStage | m3 锚点 |
|---|---|
| INCEPTION | Stage.Inception |
| ELABORATION | Stage.Elaboration |
| CONSTRUCTION | Stage.Construction |
| TRANSITION | Stage.Transition |
| OPERATION | Stage.Operation |
| RETIREMENT | Stage.Retirement |
| DECOMMISSION | Stage.Decommission |

**验收**:
- [ ] mof-audit.py 含 7 阶段节点
- [ ] model-driven/lifecycle.py **未触**
- [ ] M0 snapshot.yaml gitignored

### P2-S4: 自反校验 (W11)

| ID | 任务 | 工时 | 产物 |
|----|------|------|------|
| P2-S4-1 | 增强 `bin/mof/mof-bootstrap.py` 加 check_3 + check_4 | 8h | ~200 行 |
| P2-S4-2 | 写 check_3 自反 (49 M2 schema × m3 锚点) | 8h | check_3 |
| P2-S4-3 | 写 check_4 自反 (m3-meta 自反) | 8h | check_4 |
| P2-S4-4 | PR8 + review + merge | — | PR8 merge |

**验收**:
- [ ] 49 + 1 = 50 M2 schema 自反 100%
- [ ] m3-meta.yaml 自反 100%
- [ ] check_3 / check_4 输出 PASS

---

## 5. Phase 3 (P3): 派生面统一 (W12)

**目标**: 把 `.omo/_derived/` 路径统一收口,符合 ADR-0129 投影面范式

| ID | 任务 | 工时 | 产物 |
|----|------|------|------|
| P3-1 | 审计所有 `.omo/_derived/` 现有产物 | 4h | audit log |
| P3-2 | 写 `bin/gac/omo-state-cleanup.py` | 8h | ~200 行 |
| P3-3 | 更新 `.gitignore` | 1h | `.gitignore` +1 行 |
| P3-4 | 36 仓 24 个 .omo/_derived/ 路径收口 | 8h | 24 path |

**验收**:
- [ ] `git status` 不再产生 .omo/_derived/ 噪声
- [ ] `make gac-local-gate` clean checkout PASS

---

## 6. Phase 4 (P4): 切 ADR + 38 回归测试 (W13-W14)

| ID | 任务 | 工时 | 产物 |
|----|------|------|------|
| P4-1 | 起草 ADR-0135 (派生面统一) | 4h | `0135-derived-plane-unification.md` |
| P4-2 | 起草 ADR-0134 (M3-meta ACCEPTED) | 4h | `0134-m3-meta-cutover.md` |
| P4-3 | 写 38 回归测试 | 40h | `tests/integration/m4_metamodel/` |
| P4-4 | PR9 (派生面) + PR10 (切 ADR) | — | merge |
| P4-5 | 监控 1 周 | 5d | monitor log |
| P4-6 | 关闭 ADR-0132 | 1h | status → CLOSED |

**38 回归测试分类**:
- 8 个 mof-validate 修复验证 (P1-S0)
- 5 个 m2 schema 验证 (P1-S1)
- 8 个 L0-constraints 迁移验证 (P1-S2)
- 3 个切 ADR 验证 (P1-S3)
- 5 个 m3-meta 映射验证 (P2-S1)
- 5 个 mof_bridge 单测 (P2-S2)
- 4 个 M0 暴露验证 (P2-S3)

**验收**:
- [ ] `make test-integration` 全绿
- [ ] P74 compliance `decision: continue` 持续 4 周
- [ ] mof-validate.py 通过率 ≥99%
- [ ] ADR-0132 + 0133 + 0134 + 0135 全部 ACCEPTED

---

## 7. 风险与缓解 (P72 框架)

### 7.1 高风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Loader bug 修复触发 132 GaC 规则变体 | 中 | 高 | PR1 原子单 commit |
| m3-meta 自反失败 | 中 | 中 | check_4 强制 PASS |
| meta_model.py 8 类 API 破坏 | 低 | 极高 | 24 单测兜底 |
| 跨仓 caller schema 升级 | 中 | 中 | 仅读不改 |

### 7.2 中风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 派生面 gitignore 漏掉文件 | 中 | 中 | P3 全量审计 |
| 7 阶段映射不准确 | 中 | 中 | P2-S3 mof-audit 验证 |

### 7.3 低风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| ADR review 反复 | 中 | 低 | 5 开关默认值兜底 |

---

## 8. 里程碑日历

| 周 | 起始 | 结束 | 关键交付 |
|----|------|------|----------|
| W1 | 2026-07-06 | 2026-07-12 | P1-S0 (loader fix) |
| W2 | 2026-07-13 | 2026-07-19 | P1-S1 (ConstraintL0) |
| W3 | 2026-07-20 | 2026-07-26 | P1-S2 (migrate.py) |
| W4 | 2026-07-27 | 2026-08-02 | P1-S2 (迁移) |
| W5 | 2026-08-03 | 2026-08-09 | P1-S3 (切 ADR-0133) |
| W6 | 2026-08-10 | 2026-08-16 | P2-S1 (m3-meta schema) |
| W7 | 2026-08-17 | 2026-08-23 | P2-S1 收尾 |
| W8 | 2026-08-24 | 2026-08-30 | P2-S2 (mof_bridge) |
| W9 | 2026-08-31 | 2026-09-06 | P2-S2 收尾 |
| W10 | 2026-09-07 | 2026-09-13 | P2-S3 (M0 暴露) |
| W11 | 2026-09-14 | 2026-09-20 | P2-S4 (自反) |
| W12 | 2026-09-21 | 2026-09-27 | P3 (派生面) |
| W13 | 2026-09-28 | 2026-10-04 | P4 (回归测试) |
| W14 | 2026-10-05 | 2026-10-12 | P4 (切 ADR + 监控) |

---

## 9. 关联

- [ADR-0132](../.omo/_knowledge/decisions/0132-l0-mof-m4-metamodel.md) (主决策, PROPOSED)
- [ADR-0133] (P1 切 v2, 未来)
- [ADR-0134] (M3-meta 切, 未来)
- [ADR-0135] (派生面统一, 未来)
- [ADR-0128] (state generation concurrency)
- [ADR-0129] (state projection plane)
- [ADR-0130] (P74 workflow solidification)
- [`.omo/debt/m4-baseline-snapshot.md`](../.omo/debt/m4-baseline-snapshot.md)

---

## 10. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 PROPOSED |
