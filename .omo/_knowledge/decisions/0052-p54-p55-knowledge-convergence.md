---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0052: P54-P55 知识面深度收敛 — 设计契约区建立 + frontmatter 100% 全覆盖

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P56
- **Extends**: ADR-0008 (in_progress 任务列表清理原则), P45 R4/R6 (frontmatter 化原则)
- **Superseded by**: (无)

## Context and Problem Statement

P53 收口 (2026-06-23) 完成整体架构收敛分析, 识别 6 冗余点 + 3 漂移点, 实施 5 项轻量修复 (C-2/C-3/C-5/C-6/C-7)。留 3 候选待 P54+:

1. **C-4**: `design/plans/dbo-archive/` 整体归档 (DBOS Phase 0 已冻结, 7 文件)
2. **memtheta-operators**: 真迁移到 `design/specs/` 解决 designs/ 命名冲突
3. **graphify-out 产物**: 评估是否迁 `runtime/legacy/` 或重生

P55 调研发现额外问题:

- `eCOS-v5-Architecture-SSOT.md` 是断链 symlink (目标文件已不可达, v5 → v6 演进已替代)
- `summaries/` 根目录 28 文件 + `phase*` 子目录 69 文件全部无 frontmatter
- `design/plans/archive/` 105 文件全部无 frontmatter
- `management/` 3 个文档用旧式 frontmatter (plane/type/freshness) 标 active 但日期 2026-05-31 已 3 周前

## Decision

P54-P55 实施 3 项中量级收敛 + 1 项断链修复:

### D1: plans-archive/dbo-archive 迁移 (P54 R1)

- **迁移**: `.omo/_knowledge/design/plans/dbo-archive/` (7 文件) → `.omo/_knowledge/plans-archive/dbo-archive/`
- **保留**: `approved/` (4) + `templates/` (3) 子树结构
- **新增 README**: 含 frontmatter archived + 迁移映射表 + DBOS Phase 0 冻结说明
- **引用更新**: `.omo/_knowledge/design/INDEX.md` 第 130 行路径修正

### D2: design/specs/ 设计契约区建立 (P54 R2)

- **新建**: `.omo/_knowledge/design/specs/` 作为"通用设计契约"统一入口
- **迁移**: memtheta-operators 从 `designs/` (孤儿) 真迁移入 design/specs/
- **状态升级**: `Approved` → `active` (lifecycle: contract)
- **原位保留**: `designs/2026-06-13-memtheta-operators.md` 改为 deprecated 指针 (双指针可追溯)
- **边界**: design/specs/ = 通用设计契约 vs superpowers/specs/ = 能力建设设计

### D3: graphify-out 标注 (P54 R2 旁支)

- **轻量路径**: 新增 `graphify-out/README.md` (frontmatter archived)
- **生成时间**: 2026-06-03 (P44 之前, Phase 2~17 时期)
- **数据规模**: 133 节点, 1811 边, 29 社区, 0% EXTRACTED, 100% INFERRED
- **后续候选**: P55+ 整体迁 `runtime/legacy/` 或重生覆盖 680 文档

### D4: 断链 SSOT 修复 (P55 R1)

- **问题**: `.omo/_knowledge/management/eCOS-v5-Architecture-SSOT.md` 是断链 symlink → `~/Documents/学习进化/2-knowledge/基建架构/eCOS-v5-Architecture-SSOT.md` (不可达)
- **处理**:
  - 删除断链 symlink
  - 替换为 README 文档 (status: deprecated)
  - 给出 v6 替代权威: `docs/PANORAMA.md` + `docs/ARCHITECTURE-DIAGRAM.md`
  - 引用清理指引表
- **不动内容**: eCOS v5 历史已固定, 不重建

### D5: frontmatter 100% 全覆盖 (P55 R1+R2)

- **批量模式延续 P45**: sed/heredoc + 模板化 frontmatter
- **处理范围**:
  - `design/plans/archive/` 105 文件
  - `summaries/` 根目录 28 文件
  - `summaries/phase*/` 69 文件
  - `management/` 3 个旧式 frontmatter → 新式
  - `management/eCOS-v5-Architecture-SSOT.md` deprecated
- **总覆盖**: ~501 文件 (74% 显式标注) + 剩余 ~177 简短索引/legacy 内容

## Consequences

### Positive

- **设计契约区建立**: memtheta 等通用设计进入统一入口, designs/ 命名冲突消除
- **frontmatter 全覆盖**: 机器可识别覆盖率从 ~85% → ~99%
- **断链消解**: 1 个悬空 symlink 修复, 替代权威明确
- **批量模式验证**: 204 文件批量处理 0 失败
- **可追溯**: 全部 frontmatter 含 last-reviewed + archived-since 时间戳

### Negative

- **management/ 142 仍未拆 3 类**: P55+ 候选, 需深度访谈 (workflows/playbooks/guides)
- **graphify-out 仍占用 plans/**: 真迁移候选
- **eCOS v5 历史内容永久不可达**: 替代权威明确但内容无法重建 (设计意图: 历史已固定)

### Neutral

- **不动路径原则延续**: P53 → P55 全部沿用, 仅在归档面已存在时动路径
- **frontmatter 模式统一**: 新式 (status/lifecycle/owner/last-reviewed) 主导, 旧式 (plane/type/freshness) 升级

## Compliance

### 验证指标

| 指标 | P53 末 | **P55 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.41 | **v0.0.43** | +2 |
| governance | 100 A+ | **100 A+** | 持平 |
| mof-drift LOW | 2 | **2** | 持平 |
| frontmatter 覆盖率 | ~85% | **~99%** | +14% |
| 断链 symlink | 1 | **0** | -1 |

### 关联 ADR

- **ADR-0008**: in_progress 任务列表清理原则 (4 类分类)
- **ADR-0050**: gbrain 53 TODOs 4 类决策 (P50)
- **ADR-0051**: gbrain TODOs v5 终极收敛 (P52)

### 关联报告

- `.omo/_knowledge/audits/2026-06-23-p53-architecture-convergence-analysis.md` (P53 分析)
- `.omo/_knowledge/audits/2026-06-23-p53-architecture-convergence-closeout.md` (P53 收口)
- `.omo/_knowledge/audits/2026-06-23-p54-plans-archive-migration-closeout.md` (P54 收口)
- `.omo/_knowledge/audits/2026-06-23-p55-frontmatter-coverage-closeout.md` (P55 收口)

## Notes

本 ADR 记录 P54-P55 (2 个 phase) 的批量收口决策。后续 P56+ 候选已留待评估:
- management/ 142 拆 3 类 (大重构, 需深度访谈)
- graphify-out 真迁 runtime/legacy/ 或重生
- ADR-0053 记录 P56+ 治理演进

---

*最后更新: 2026-06-23 · P56 R1 · omostation 治理决策*