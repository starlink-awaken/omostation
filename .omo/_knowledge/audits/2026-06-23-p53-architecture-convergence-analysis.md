---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史审计快照批量归档, 当前 governance 100 A+ 持续"
---
# P53 — 整体架构收敛分析报告

**日期**：2026-06-23
**作者**：governance-team (omostation P53)
**前序**：P52 ADR-0051 收口 + governance 99.3 (A+)
**目标**：对 `.omo/_knowledge/` 678 个文档做架构收敛分析，识别冗余/重复/漂移点

---

## 1. 现状全景摸底

### 1.1 知识面文件分布

| 平面 | 文件数 | 占比 | 评估 |
|------|-------:|-----:|------|
| `design/` | 217 | 32.0% | 🔴 超载（最大池） |
| `management/` | 142 | 20.9% | 🟡 大池 |
| `summaries/` (含 phase1-18) | 106 | 15.6% | 🟡 大池（含 18 个 phase 子目录） |
| `superpowers/` | 77 | 11.4% | 🟡 plans + specs 双子目录 |
| `audits/` | 41 | 6.0% | ✅ 合理 |
| `process/` | 26 | 3.8% | ✅ 合理 |
| `reference/` | 9 | 1.3% | ✅ 精简 |
| `decisions/` | 11 | 1.6% | ✅ 精简 |
| `governance/` | 7 | 1.0% | ✅ 精简 |
| `usage/` | 3 | 0.4% | ✅ 精简 |
| `vision-roadmap/` | 3 | 0.4% | ✅ 精简 |
| `architecture/` | **1** | 0.1% | 🔴 失载（应为核心承载） |
| `designs/` | **1** | 0.1% | 🔴 孤儿（应是设计面副本） |
| 其他 (drafts/patterns/analysis/retrospectives/plans-archive) | 8 | 1.2% | ✅ 边界清晰 |
| **合计** | **678** | 100% | — |

### 1.2 设计面 (`design/`) 内部结构（217 → 5 子目录）

| 子目录 | 文件数 | 性质 | 评估 |
|--------|-------:|------|------|
| `design/plans/` | **154** | 计划注册表 | 🔴 超载（含 `archive/dbo-archive/graphify-out`） |
| `design/` (根) | 33 | Phase 设计/治理蓝图 | 🟡 含 v1/v2/v3 历史多版本 |
| `design/history/` | 19 | 历史演进 | ✅ 合理 |
| `design/reviews/` | 6 | 评审记录 | ✅ 合理 |
| `design/diagrams/` | 4 | 架构图 | ✅ 精简 |

### 1.3 plans 子目录再细分（154 个文件）

| 子目录 | 文件数 | 评估 |
|--------|-------:|------|
| `plans/` 根 | TBD | 主计划区 |
| `plans/archive/` | TBD | 历史归档 |
| `plans/dbo-archive/` | TBD | DB-Only 历史 |
| `plans/dbo-archive/approved/` | TBD | 已批准 |
| `plans/dbo-archive/templates/` | TBD | 模板 |
| `plans/graphify-out/` | TBD | 图谱生成产物 |

---

## 2. 架构冗余点 (6 项)

### R-DUP-1：`architecture/` 失载

- **现状**：仅 1 个文件 `2026-06-15-unified-audit-architecture.md`
- **问题**：
  - 命名暗示承载"架构核心文档"，实际是审计架构（unified audit）
  - 真正的架构总览散落在 7+ 处：
    - `docs/PANORAMA.md` (334 行, 唯一权威)
    - `_knowledge/architecture-final-state-v1/v2/v3.md` (3 版本)
    - `_knowledge/management/5+3+1-layer-deep-architecture.md`
    - `_knowledge/designs/omostation-strategic-architecture-v2.md`
    - `_knowledge/design/system-design-baseline.md`
    - `_knowledge/management/architecture-complete-plan.md`
    - `_knowledge/management/architecture-pure-analysis.md`
    - `_knowledge/management/architecture-migration-playbook.md`
- **收敛建议**：
  - 选项 A（推荐）：`architecture/` 改名为 `audit-architectures/`（仅留审计类），明确单一职责
  - 选项 B：`architecture/` 升级为唯一架构总览目录，把 PANORAMA.md 内容片段化收录
  - 选项 C：保持现状但加 README 说明 "本目录仅审计架构总览，全局架构以 PANORAMA.md 为准"

### R-DUP-2：`designs/` 孤儿单文件

- **现状**：仅 1 个文件 `2026-06-13-memtheta-operators.md`
- **问题**：与 `design/` (单数) 命名冲突，无 README/INDEX
- **收敛建议**：
  - 选项 A（推荐）：迁移到 `design/specs/memtheta-operators.md` 或 `superpowers/specs/`（更适合算子设计）
  - 选项 B：删目录，把文件挪走

### R-DUP-3：`design/plans/` 154 个超载

- **现状**：154 个文件，含 3 层嵌套 archive
- **问题**：
  - 计划 / 历史计划 / DB-only / 已批准 / 模板 / 图谱产物混在一起
  - 检索成本高
  - 多数计划已 ARCHIVED 或 REFERENCE 状态
- **收敛建议**：
  - 选项 A（推荐）：保留 `design/plans/` 当前活跃，迁移 `dbo-archive/` 整个子树到 `_archive/`（已存在归档面），`graphify-out/` 是产物可独立到 `data/` 或 `runtime/`
  - 选项 B：拆分 plans 为 `plans/active/` + `plans/archived/`（双层）
  - 选项 C：保持现状加 INDEX 表格（轻量）

### R-DUP-4：summaries 18 个 phase 子目录 + retro 混淆

- **现状**：
  - `summaries/` 根目录 37 个（多数 `retro-*`/`p*-retrospective`）
  - `summaries/phase1-phase18/` 18 个子目录 69 个文件
  - `summaries/audits/` 9 个
- **问题**：
  - 根目录 retro 文件应归 `process/retrospectives/` 或 `retrospectives/`（已存在空目录）
  - `retrospectives/` (根) 只有 1 个文件（空目录）
  - 18 个 phase 子目录覆盖不全（缺 phase4/19-24/25+）
- **收敛建议**：
  - 选项 A（推荐）：把所有 `retro-*` / `RETRO-*` 移动到 `process/retrospectives/`（已有 20 个）
  - 选项 B：保持 phase 子目录，根目录按内容分类（summary/retro/audit）

### R-DUP-5：superpowers/ 双子目录

- **现状**：`superpowers/plans/` (39) + `superpowers/specs/` (38) = 77
- **问题**：plans 与 specs 是设计/实现对应关系，但分散两目录难配对
- **收敛建议**：
  - 选项 A：保持双子目录（plan-spec 是标准配对，符合软件工程实践）
  - 选项 B（推荐）：合到 `superpowers/{topic}/` 按主题聚合（每个 topic 含 plan + spec + 实现记录）

### R-DUP-6：management/ 142 个文档池

- **现状**：142 个文件，含 5+3+1/治理机制/工作流/能力映射/历史复盘
- **问题**：
  - 与 `governance/` (7 个) 边界模糊
  - 与 `process/` (26 个) 流程类重叠
  - 多数是"流程指南"，应归 `process/` 或独立 `guides/`
- **收敛建议**：
  - 选项 A（推荐）：保留 management 作为"流程管理/方法论"，governance 作为"治理规则"，process 作为"操作流程"
  - 选项 B：拆 management 为 `workflows/` + `playbooks/` + `guides/` 三类

---

## 3. 架构漂移点 (3 项)

### R-DRIFT-1：架构版本多份并存

- `architecture-final-state-v1.md` / `v2.md` / `v3.md` (3 个版本)
- `architecture-remediation-plan.md` / `v2.md`
- `ARCH-AUDIT-2026-05.md` / `ARCH-AUDIT-v2.md`
- `MASTER-BLUEPRINT.md` / `system-design-baseline.md` / `omostation-strategic-architecture-v2.md`

**收敛建议**：建立单一权威指针表，明确每个文件的"现状/历史/废弃"标签，废弃文件 `status: archived` frontmatter 标记（沿用 P45 规范）

### R-DRIFT-2：ADR INDEX 与文件不一致

- ADR-0051 文件已存在 (P52) 但 INDEX 索引表未列出 → governance 扣分 (99.3 vs 100)
- **已修复** (P53 R1)

### R-DRIFT-3：convergence.yaml 历史漂移

- `last_updated: 2026-05-30` 但内容描述 phase1-2，与当前 P52 状态不符
- 文件无 frontmatter，难判 lifecycle
- **收敛建议**：加 `status: archived` frontmatter（已是历史快照）

---

## 4. 收敛优先级矩阵

| 建议 | 影响范围 | 工作量 | 风险 | 价值 | 优先级 |
|------|---------|------:|-----:|-----:|------:|
| **C-1**: ADR-0051 INDEX 补齐 | 1 文件 | 1 行 | 0 | 高 (governance → 100) | ✅ P53 R1 (DONE) |
| **C-2**: `designs/` 孤儿清理 | 1 文件 | 迁移 | 低 | 中 | 🟡 P53 R2 |
| **C-3**: `summaries/` retro 归位 | ~30 文件 | 移动+链接 | 中 | 中 | 🟡 P53 R2 |
| **C-4**: `design/plans/dbo-archive/` 归档 | ~30 文件 | 迁移 | 低 | 中 | 🟡 P53 R2 |
| **C-5**: 架构版本多份 `status: archived` 标记 | ~10 文件 | 加 frontmatter | 低 | 高 | ✅ P53 R2 |
| **C-6**: `convergence.yaml` archived 标记 | 1 文件 | 加 frontmatter | 0 | 低 | ✅ P53 R2 |
| **C-7**: `architecture/` README 明确职责 | 1 文件 | 加 README | 0 | 中 | ✅ P53 R2 |
| **C-8**: `management/` 拆分为 3 类 | ~142 文件 | 大重构 | 高 | 待评估 | 🔵 后续 P54+ |

---

## 5. 收敛原则（沿用 P45 框架）

### 5.1 SSOT 不复制
- 单一事实不在多处写（沿用 CLAUDE.md SSOT 铁律）
- 历史快照 → 加 `status: archived` frontmatter，不删内容

### 5.2 软分层
- 物理目录可以共存（业界 CNCF/Linux kernel 共识）
- 关键是元数据 (frontmatter) + 状态机驱动

### 5.3 不动路径原则
- 沿用 P45 决策：保留现状目录结构
- 仅清理内容（frontmatter + README），不删/移文件除非必要

---

## 6. 下一步 (P53 R2+)

- **R1** (DONE): ADR-0051 INDEX 补齐 → governance 99.3 → 100
- **R2** (本报告后): 6 项轻量收敛 (C-2 ~ C-7)
- **R3**: 收口报告 + mof-version v0.0.40 → v0.0.41

C-8 (management 大重构) 留待 P54+ 评估，需先做深度访谈。

---

## 7. 附录：governance 历史

| P 阶段 | governance 评分 | 关键 |
|--------|----------------|------|
| P44 R7 | 100 A+ | 87 lint → 0 |
| P45 R8 | 100 A+ | doc-lifecycle 落地 |
| P46 R2 | 100 A+ | 11 PLANNED + 3 mof |
| P47 R3 | 100 A+ | 12/12 mof |
| P48 R3 | 100 A+ | 17 项目 lint |
| P49 R3 | 100 A+ | PLANNED 清零 |
| P50 R3 | 100 A+ | mof-drift v4 |
| P51 R3 | 100 A+ | drafts 清零 |
| P52 R3 | 100 A+ | mof-drift v5 |
| **P53 R1** | **100 A+** | **ADR-0051 INDEX 修复** |

---

*P53 R1 完成: 2026-06-23 · governance 100 A+ 恢复*