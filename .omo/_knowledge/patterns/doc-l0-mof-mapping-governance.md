---
title: 文档 ↔ L0 ↔ MOF 映射治理方案
status: active
lifecycle: pattern
owner: governance
last-reviewed: 2026-08-08
surface: L3
dimension: X1
---

# 文档 ↔ L0 ↔ MOF 映射治理方案

> SSOT 关联: 文档治理契约 = `.omo/standards/doc-ssot-contract.md` §L0/MOF 映射关联
> 验证工具: `bin/ssot/check-doc-l0-mapping.py`（PR #1246 落地）
> 状态: **已落地第一阶段（契约 + 验证工具），m3 元模型层待补齐**

## 1. 现状（2026-08-08 实测）

### 1.1 文档 SSOT 已建立
| 组件 | 位置 | 状态 |
|------|------|------|
| 契约 | `.omo/standards/doc-ssot-contract.md`（8 节） | ✅ 含 L0/MOF 映射小节 |
| 执行门禁 | `doc-ssot-lint.py` | ✅ 157 files 0 conflicts |
| 注册表 | `docs/project-registry.yaml` + `gen-project-registry.py` | ✅ 双面齐 |
| workflow 挂载 | `agent-workflows/_root.yaml` doc_contract + project-doc-change | ✅ 已接线 |

### 1.2 L0 约束（源 + 派生）
- **源**（SSOT）: `projects/ecos/src/ecos/l0/`（Python 代码）
- **派生**: `projects/ecos/.omo/_derived/l0-constraints.v2.yaml`
  - v2.0.0, ADR-0132, **77 条约束**
  - 每条带 `m3_parent: ConstraintL0` + `m2_type: ConstraintL0` + `violation_code: E-L0-001` → **L0→MOF 映射字段已内建**
  - dimension 值域: X1-X4；applies_to 值域: I0/L0/L1/L2/L3/L4/meta

### 1.3 MOF 工具链
- ✅ `mof-drift`（实测可跑，MOF/L0 漂移检测）
- ✅ `m2-ssot-inventory.py` / `m4-health-score.py` / `check-mof-capabilities-drift.py` / `check-doc-claims.py`
- ❌ **m3.yaml / meta_model 层缺失**（ecos 只有 m0/snapshot.yaml）
- ❌ **L0 派生生成器已归档**（`bin/_archive/l0-constraints-migrate.py`）

## 2. 已落地（第一阶段, PR #1246）

### 2.1 契约增强 `doc-ssot-contract.md`
- L57: L0 约束 SSOT 路径更新 → 派生面 v2 ← 源 `src/ecos/l0/`
- 新增 **L0/MOF 映射关联** 小节:
  | 文档 frontmatter | L0 字段 | MOF 字段 |
  |------------------|---------|----------|
  | `dimension` (X1-X4) | `dimension` | `m3_parent: ConstraintL0` |
  | `surface` (I0/L0-L4/meta) | `applies_to` | `m2_type: ConstraintL0` |
  | `owner` | `references` | — |
  | `status` | `state` | — |

### 2.2 验证工具 `bin/ssot/check-doc-l0-mapping.py`
4 条规则:
1. 文档 `dimension` ∈ L0 值域 (X1-X4)
2. 文档 `surface` ∈ applies_to 值域 (I0/L0-L4/meta)
3. 每条 L0 约束带 `m3_parent: ConstraintL0`（MOF 映射完整性）
4. L0 源目录存在（自动更新闭环可验证）

实测: `--json` → ok:true（77 约束），EXIT=0

## 3. 三轨路线图（按 老王 偏好: 立即解锁 + 正确架构 + 理想）

### 🟢 立即（已完成）— 契约 + 验证工具
- [x] 契约映射小节（PR #1246）
- [x] `check-doc-l0-mapping.py`（PR #1246）
- [ ] 挂 doc-ssot-lint 或独立 workflow（一行接线）

### 🟡 长期（正确架构）— 补齐断链
1. **m3 元模型层落地**: 在 `projects/ecos/src/ecos/ssot/mof/` 建 `m3/` 层
   - 定义 `ConstraintL0` 元模型节点（m3_parent 指向）
   - `mof-drift` 消费 m3 层做完整漂移检测
2. **L0 派生生成器复活**: `bin/_archive/l0-constraints-migrate.py` → `projects/ecos/bin/gen-l0-constraints.py`（正式工具）
   - 自动从 `src/ecos/l0/` 源重新生成 `_derived/l0-constraints.v2.yaml`
   - 闭环: 源变更 → 生成派生 → `mof-drift` 验证 → 提交
3. **doc-ssot-lint 接线**: `check-doc-l0-mapping.py` 挂进现有 lint 链（rules 追加）

### 🔵 理想（演进）— 全自动治理闭环
1. **文档 frontmatter 自动标注**: `doc-governance-migrate.py` 扩展, 按文档所在层级自动补 `dimension`/`surface`
2. **约束消费文档声明**: L0 约束的 `references` 反向索引对应标准文档（双向映射）
3. **CI 门禁**: `check-doc-l0-mapping` + `mof-drift` 双门禁进 phase-gate
4. **漂移告警**: 文档 dimension 与 L0 约束 dimension 漂移 → PR 检查时提示

## 4. 验证与自动更新机制

```
源 (src/ecos/l0/) ──生成──▶ 派生 (l0-constraints.v2.yaml) ──消费──▶ 文档契约映射
     │                              │                              │
     └── mof-drift 漂移检测 ◀────────┘                              │
                                   ┌───────────────────────────────┘
                                   ▼
                        check-doc-l0-mapping.py (4 规则)
                                   │
                                   └── doc-ssot-lint 接线 → phase-gate
```

- **验证**: `python3 bin/ssot/check-doc-l0-mapping.py`（本地 + CI）
- **自动更新**: 源变更 → gen-l0-constraints → mof-drift 确认 → 提交（闭环）
- **防回归**: 工具进 lint 链 + phase-gate

## 5. 相关引用
- 契约: `.omo/standards/doc-ssot-contract.md`
- L0 派生: `projects/ecos/.omo/_derived/l0-constraints.v2.yaml`
- L0 源: `projects/ecos/src/ecos/l0/`
- 验证工具: `bin/ssot/check-doc-l0-mapping.py`
- ADR-0132（L0 v2 cutover）: `.omo/_knowledge/decisions/0132-l0-constraints-v2-cutover.md`
