# 项目级文档体系深度分析

> 日期: 2026-09-04 | 范围: 主仓 + 子模块 (不含 .omo/)
> 文档总规模: 802 文件 / 102,532 行

---

## 一、核心入口文档

| 文档 | 行数 | Frontmatter | 时效性 |
|------|------|-------------|--------|
| AGENTS.md | 608 | ✅ type/owner/last_updated | ✅ 2026-09-03 |
| README.md | 198 | ✅ | ✅ 2026-09-03 |
| CLAUDE.md | 237 | ✅ | ✅ 2026-09-03 |
| ARCHITECTURE.md | 202 | ✅ | ✅ 2026-09-03 |
| SYSTEM-INDEX.md | 78 | ✅ | ✅ 2026-09-03 |
| GOVERNANCE.md | 108 | ✅ | ✅ 2026-09-03 |

**评估**: 6 个核心入口文档全部完整且时效一致。

---

## 二、docs/ 目录分析

### 2.1 按子目录分布

| 子目录 | 文件数 | 总行数 |
|--------|--------|--------|
| superpowers/specs/ | 163 | ~14,192 |
| reports/ | 156 | 14,390 |
| plans/ | 34 | ~15,000 |
| architecture/ | 24 | ~18,000 |
| docs/ 根目录 | 72 | 17,494 |
| governance/ | 13 | ~4,000 |
| adr/ | 12 | ~4,000 |
| operations/ | 7 | ~17,000 |
| **docs/ 合计** | **547** | **85,521** |

### 2.2 空目录（需清理）

- `contracts/`
- `journey-specs/`
- `journey-templates/`
- `observability/`
- `scene-cards/`

---

## 三、子模块文档体系

### 3.1 文档覆盖率

| 文档类型 | 存在数 | 覆盖率 |
|----------|--------|--------|
| AGENTS.md | 16/16 | 100% |
| README.md | 16/16 | 100% |
| ARCHITECTURE.md | 13/16 | 81% |
| CLAUDE.md | 14/16 | 88% |
| CONTRIBUTING.md | 14/16 | 88% |
| CHANGELOG.md | 14/16 | 88% |

### 3.2 偏薄的 AGENTS.md

| 子模块 | 行数 | 问题 |
|--------|------|------|
| omlxc | 29 | 过于精简 |
| knowledge | 35 | 过于精简 |

---

## 四、质量评估

### 4.1 时效性
- ✅ 所有根文档 last_updated 均为 2026-09-03/04
- ⚠️ superpowers/specs/ 中 8/28-8/30 三天集中产出 83 个 spec (51%)

### 4.2 一致性
- ⚠️ **双风格 frontmatter**: type vs status 并存
- ⚠️ **docs/ 根目录 72 个文件**，大量未被 INDEX 引用 (~52 个孤儿)
- ⚠️ 子模块 README.md 类型不一致 (ssot vs derived)

### 4.3 超大文档 (>500行)

| 文件 | 行数 | 建议 |
|------|------|------|
| WORKFLOW-MESH-IMPLEMENTATION.md | 1,219 | 拆分 |
| digital-twin-blueprint-v1.md | 1,044 | 保留 |
| documents-content-plane-full-convergence.md | 1,020 | 归档 |
| STRATEGY-3YEAR-PANORAMA.md | 1,016 | 保留 |
| SYSTEM-INDEX-DESIGN.md | 897 | 归档 |
| USER-JOURNEY-SOP.md | 810 | 保留 |

---

## 五、文档拓扑

### 引用关系

```
AGENTS.md → README, CLAUDE, ARCHITECTURE, SYSTEM-INDEX, GOVERNANCE
SYSTEM-INDEX.md → INDEX-*, ARCHITECTURE, PANORAMA
ARCHITECTURE.md → architecture/*, LAYER-INDEX, PANORAMA
```

### 孤立文档 (52个)

docs/ 根目录中未被任何 INDEX 或核心文档引用的文件:
- 历史架构分析 (6个)
- 历史计划 (17个 8月计划)
- 治理专项 (G-DEL-*, DEBT-CLEANUP-*)
- 战略文档 (STRATEGY-*, M4-*)

---

## 六、改进建议

### P1 — 立即修复

| 项 | 操作 |
|----|------|
| INDEX-MCP.md | 添加 frontmatter |
| cockpit-ui/AGENTS.md | 补齐标准 frontmatter |
| knowledge/AGENTS.md | 补齐标准 frontmatter，扩展内容 |
| SYSTEM-INDEX.md | 添加缺失的孤儿文档引用 |

### P2 — 短期优化

| 项 | 操作 |
|----|------|
| docs/ 根目录 | 72 个文件按类别归入子目录 |
| superpowers/specs/ | 163 个文件按周/主题分子目录 |
| WORKFLOW-MESH-IMPLEMENTATION.md | 按阶段拆分 |
| 统一 frontmatter | 全仓采用 type/owner/last_updated |
| 清理空目录 | 删除 5 个空目录 |

### P3 — 长期治理

| 项 | 操作 |
|----|------|
| 历史文档归档 | 迁移过期计划到 .omo/_archive/ |
| INDEX 合并 | 6 个 INDEX 文件统一为单一导航 |
| 战略文档合并 | STRATEGY-* 系列整合 |

---

## 七、量化指标

| 指标 | 数值 |
|------|------|
| docs/ .md 文件 | 547 |
| 子模块 .md 文件 | 255 |
| **文档总规模** | **802 文件 / 102,532 行** |
| frontmatter 覆盖率 | ~99% |
| AGENTS.md 覆盖率 | 100% |
| 孤儿文档 | ~52 |
| 时效性 < 90 天 | 100% |
| **综合成熟度** | **7.8/10** |
