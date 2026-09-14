---
title: 文档 ↔ L0 ↔ MOF 映射治理方案
status: active
lifecycle: pattern
owner: governance
last-reviewed: 2026-08-08
surface: L3
dimension: X1
type: ssot
---

# 文档 ↔ L0 ↔ MOF 映射治理方案

> SSOT 关联: 文档治理契约 = `.omo/standards/doc-ssot-contract.md` §L0/MOF 映射关联
> 验证工具: `bin/ssot/check-doc-l0-mapping.py`（PR #1246 落地）
> 状态: **已落地第一阶段（契约 + 验证工具 + lint 接线 + L0 生成器复活）; m3 元模型层经核实已存在（三元链完整）; 剩余: CI 门禁接线**

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
- ✅ **m3 元模型层存在**: `projects/ecos/src/ecos/ssot/mof/m3.yaml`（668 行, Element/Relation 类目, L187 Constraint）+ `m3-meta.yaml`; M2 层 `m2/constraint_l0.yaml` 定义 ConstraintL0 → m3_parent: Constraint（**三元链完整: L0 派生 m3_parent:ConstraintL0 → m2 ConstraintL0 → m3 Constraint**）
- ❌ **L0 派生生成器此前已归档**（`bin/_archive/l0-constraints-migrate.py`）— PR #1249 已复活为 `projects/ecos/bin/gen-l0-constraints.py`（双源合并 130 条）

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

### 2.3 抽象族映射表（2026-08-08, 136 治理规则 → 16 族 → L0 约束）

| 抽象族 | 治理规则前缀 | L0 维度 | L0 约束 | MOF 类目 |
|--------|-------------|---------|---------|----------|
| 分层边界 | CR-LAYER/CR-L0-L4/CR-BOUNDARY/CR-HARDCODED | X1 | X1-C01~C03 | omo_layer |
| 跨仓契约 | CR-CROSS/CR-INTERFACE/CR-CONTRACT | X1 | **X1-C04** | protocol |
| 提交纪律 | CR-COMMIT/CR-CHANGELANE/CR-PR/CR-REVIEW | X1 | **X1-C05** | process |
| SSOT/漂移 | CR-SSOT/CR-DRIFT/CR-SYNC/CR-POINTER/CR-SUBMODULE | X4 | **X4-C14** | specification |
| 元治理 | CR-META/CR-RULE/CR-EXECUTOR/CR-GATE/CR-BOOTSTRAP | X4 | **QG-C03** | constraint_mgmt |
| 基线/证据 | CR-BASELINE/CR-EVIDENCE/CR-AUDIT/CR-CLAIM | X4 | X4-C05~C13 | evidence |
| 流程/Agent | CR-P74/CR-P76/CR-P77/CR-P79/CR-WORKFLOW/CR-AGENT | X3 | X3-C01~C02 | process/agent |
| 债务/交付 | CR-DEBT/CR-REDLINE/CR-CADENCE/CR-DELIVERY | X3 | **X3-C03** | governance |
| 健康度/可观测 | CR-HEALTH/CR-SCORE/CR-METRIC/CR-UPTIME | X2 | **X2-C06** | predictive_governance |
| 代码卫生 | CR-GOD/CR-ORPHAN/CR-DEAD/CR-MODULE | X2 | **X2-C07** | component |
| 安全 | CR-SEC/CR-PERMISSION/CR-SECRET/CR-CREDENTIAL | QG | **QG-C04** | governance |
| 文档/ADR | CR-DOC/CR-FRONTMATTER/CR-FRESHNESS/CR-ADR | X3 | QG-C01~C02 | artifact |
| MCP工具 | CR-MCPTOOL | X1 | X1-C02 | mcptool |
| 索引/注册表 | CR-INDEX/CR-REGISTRY/CR-INVENTORY | X2 | X2-C01~C05 | entity |
| 环境/端口 | CR-PORT/CR-ENV-VAR | X1 | X5-C01 | protocol |
| BOS 域 | CR-BOS/CR-URI | X5/X6/X7 | X5/X6/X7-C01 | bosroute |

**加粗 = 2026-08-08 新增 8 条**（覆盖 16 族中 L0 原缺的 8 个语义族）。
L0 v3: 28 → 36 约束；派生面重新生成 137 条。

## 3. 三轨路线图（按 老王 偏好: 立即解锁 + 正确架构 + 理想）

### 🟢 立即（已完成）— 契约 + 验证工具 + 生成器
- [x] 契约映射小节（PR #1246）
- [x] `check-doc-l0-mapping.py`（PR #1246）+ doc-ssot-lint 接线（PR #1248）
- [x] L0 派生生成器复活 `projects/ecos/bin/gen-l0-constraints.py`（PR #1249, 双源合并 130 条）
- [x] dimension 值域对齐 X1-X7（PR #1249）

### 🟡 长期（正确架构）— 断链已补, 待接线
1. **m3 元模型层**: ✅ **已存在**（m3.yaml 668 行 + m2/constraint_l0.yaml, 三元链完整）— 无需新建
2. **L0 派生生成器**: ✅ **已复活**（PR #1249）— 自动从双源生成 130 条派生面
3. **doc-ssot-lint 接线**: ✅ 已完成（PR #1248）
4. **CI 门禁**: 将 `check-doc-l0-mapping` + `mof-drift` 纳入 phase-gate（待办）

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
