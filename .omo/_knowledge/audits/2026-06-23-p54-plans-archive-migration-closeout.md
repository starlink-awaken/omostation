---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史审计快照批量归档, 当前 governance 100 A+ 持续"
---
# P54 — plans-archive/迁移与 design/specs/契约区收口报告

**日期**：2026-06-23
**阶段**：P54 R1-R3 (3 commits)
**目标**：完成 P53 遗留候选 — C-4 (dbo-archive 归档) + memtheta 真迁移 + graphify-out 标注

---

## 1. 治理全景 (P54 完成)

| 指标 | P53 末 | **P54 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.41 | **v0.0.42** | +1 |
| governance | 100.0 A+ | **100.0 A+** | 持平 |
| mof-drift LOW | 2 | **2** | 持平 |
| plans 总文件 | 154 | **154** | 持平 |
| plans/dbo-archive | 7 | **0** (已迁出) | -7 |
| plans-archive/dbo-archive | 0 | **8** (7 + README) | +8 |
| design/specs/ | 0 | **1** (memtheta) | +1 |
| design/plans/graphify-out | 9 + 0 README | **9 + 1 README** | +1 |

---

## 2. 完整落地清单 (3 commits)

### R1: dbo-archive 整体迁移
- **迁移**: `.omo/_knowledge/design/plans/dbo-archive/` → `.omo/_knowledge/plans-archive/dbo-archive/`
- **保留结构**: `approved/` (4) + `templates/` (3) = 7 文件
- **新增 README**: `.omo/_knowledge/plans-archive/dbo-archive/README.md` (frontmatter archived + 迁移说明)
- **引用更新**: `.omo/_knowledge/design/INDEX.md` 第 130 行路径修正
- **理由**: DBOS Phase 0 已冻结 (2026-05-14), 与当前 eCOS v6 架构有结构性差异

### R2: memtheta-operators 真迁移
- **迁移**: `.omo/_knowledge/designs/2026-06-13-memtheta-operators.md` → `.omo/_knowledge/design/specs/memtheta-operators.md`
- **状态升级**: `Approved (Phase 1.2)` → `active` (lifecycle: contract)
- **原位指针**: 保留为 deprecated 文件, 含 `migrated-to` frontmatter
- **理由**: designs/ 命名冲突消除, memtheta 进入统一设计契约区

### R2 旁支: graphify-out 标注
- **新增**: `.omo/_knowledge/design/plans/graphify-out/README.md`
- **状态**: `archived` (生成产物, 非活跃计划)
- **后续候选**: P55+ 可考虑整体迁移到 `runtime/legacy/` 或重新生成图谱

### R3: 收口
- mof-version v0.0.41 → v0.0.42
- 本收口报告

---

## 3. 设计/plans/拓扑变化 (Before → After)

```
BEFORE (P53 末):
.omo/_knowledge/design/plans/
├── (138 active plans)
├── archive/                    (106 historical)
├── dbo-archive/                (7 DBOS frozen)
│   ├── approved/   (4)
│   └── templates/  (3)
└── graphify-out/               (9 graph artifacts)

AFTER (P54 末):
.omo/_knowledge/design/plans/
├── (138 active plans)
├── archive/                    (106 historical)
└── graphify-out/               (9 + README 标注为生成产物)

.omo/_knowledge/plans-archive/
├── root-plan/                  (1 historical)
└── dbo-archive/                (8: 7 + README, 历史 DBOS 归档)
    ├── approved/   (4)
    ├── templates/  (3)
    └── README.md

.omo/_knowledge/design/
├── (33 active design docs)
└── specs/                      (NEW: 1 contract)
    └── memtheta-operators.md

.omo/_knowledge/designs/
└── README.md                   (DEPRECATED, 历史可追溯)
    └── 2026-06-13-memtheta-operators.md  (DEPRECATED, 指针)
```

---

## 4. 关键决策

### D-P54-1: plans-archive 接受 DBOS 迁移
- 既有 plans-archive/ 仅 1 文件 (P26-W2-CLEANUP), 接受 dbo-archive (7) 形成"历史归档主入口"
- 与既有 plans/archive/ 区别: plans-archive 是 Phase 级 (DBOS/P26), plans/archive 是设计级

### D-P54-2: memtheta 进入 design/specs/ 而非 superpowers/specs/
- **design/specs/**: 通用设计契约 (lifecycle: contract)
- **superpowers/specs/**: 能力建设设计 (debt/omo governance)
- memtheta 是"记忆算子体系"接口规范, 属通用设计契约

### D-P54-3: graphify-out 不迁移
- 轻量路径: README 标注 + 沿用 P53 不动路径原则
- 候选: P55+ 整体迁 `runtime/legacy/` 或重新生成

---

## 5. 后续候选 (P55+)

| 建议 | 工作量 | 风险 | 价值 | 时机 |
|------|------:|-----:|-----:|------|
| graphify-out 整体迁移 runtime/legacy/ | 低 | 低 | 中 | P55 |
| management/ 142 拆 3 类 (workflows/playbooks/guides) | 大 | 高 | 待评估 | P55+ 需深度访谈 |
| 重新生成 graphify 图谱 (覆盖当前 680 文档) | 中 | 中 | 中 | P56 验证架构健康 |
| ADR-0052 记录 P54 设计契约区建立 | 低 | 0 | 中 | P55 |

---

## 6. mof-version 历史

| 版本 | 日期 | 关键 |
|------|------|------|
| v0.0.40 | 2026-06-23 | P52 R3: mof-drift v5 终极 |
| v0.0.41 | 2026-06-23 | P53 R1-R3: 整体架构收敛 (6 项轻量 + ADR-0051 INDEX) |
| **v0.0.42** | **2026-06-23** | **P54 R1-R3: plans-archive/dbo-archive 迁移 + memtheta 真迁移 + graphify-out 标注** |

---

## 7. 总结

P54 完成了 P53 遗留的"中量级"收敛：
- **迁移面**: dbo-archive 7 文件 + memtheta 1 文件 = 8 文件真迁移
- **标注面**: graphify-out 9 文件 README 化 (轻量)
- **结构面**: plans-archive 从 1 → 9 文件, design/specs 从 0 → 1 文件
- **可追溯**: 全部迁移带 frontmatter, 原位保留指针 (双指针)

**核心方法论演进**: P53 是"不动路径 + 元数据驱动", P54 升级为"动路径 + 双指针可追溯"。当归档面已存在 (plans-archive) 且目标明确 (DBOS Phase 0 已冻结) 时, 真迁移比 frontmatter 更清晰。

---

*P54 R1-R3 完成: 2026-06-23 · governance 100 A+ 持续 · mof-version v0.0.42 · mof-drift 0 LOW 持续*