---
status: active
lifecycle: standard
owner: governance-team
last-reviewed: 2026-07-02
---

# bin/ 工具命名规范 (P3-1 ADR-0115 Phase 1)

> SSOT: `bin/README.md` 是工具目录, 本文档是命名规范.
> 治理规则: CR-META-BIN-NAMING (命名守), CR-META-BIN-ORPHAN (工具未接守).

## 命名空间

`bin/` 工具按域归类, 同类工具共享**单前缀**:

| 域 | 前缀 | 数量 (2026-07-02) |
|----|------|-------------------|
| GaC 治理即代码 | `gac-` | 17 |
| ADR 治理 | `adr-` | 6 |
| 治理全景/路线图 | `governance-` | 6 (避免 `gov-` 短前缀) |
| 治理历史/趋势 | `governance-` | (与上面同空间) |
| Dashboard 渲染 | `governance-dashboard-` (待统一, P3-1 Phase 4) | 4 |
| Doc SSOT | `doc-` | 3 |
| SSOT 守护 | `ssot-` | 2 |
| OMO 治理 | `omo-` | 2 |
| X2 抗熵 | `x2-` | 3 |
| Auto-merge | `auto-merge-` | 2 |
| Submodule | `submodule-` | 2 |
| MOF | `mof-` | 2 |
| God-module | `god-module-` | 2 |
| 杂类 (单点) | 无前缀 | 30+ |

## 反模式 (禁止)

- ❌ 短前缀 `gov-` 代替 `governance-` (歧义, 一律 `governance-`)
- ❌ 同类工具分散在多个前缀 (`check-` 与 `verify-` 混用, 选定 `check-` 后同类不另起)
- ❌ 工具存在但 0 caller 且未在 gac-local-gate.py::CHECKS 注册 (落入"声明/执行鸿沟")
- ❌ 工具命名与 description 不符 (如 `dashboard-ui-render` 实际是数据汇总不是 UI 渲染)

## 命名迁移 (ADR-0115 Phase 2 待执行)

- `gov-history-stats.py` → `governance-history-stats.py`
- `gov-trend-report.py` → `governance-trend-report.py`

## 工具接入 gate 规范 (ADR-0115 Phase 3 待执行)

每个 `bin/*.py` 工具应:
1. 有 caller (Makefile / workflow / pre-commit / 文档 或 gac-local-gate.py::CHECKS 之一)
2. 描述清晰 (description 与实际行为一致)
3. 退出码语义化 (0 = ok, 1 = drift, 2 = 错误)
4. **未接 caller 的工具 → 标 `bin/_archive/` 或加进 gac-local-gate CHECKS**

`bin/_archive/` 不存在时, 先建空目录 + 写 `bin/_archive/README.md` 说明归档规则.

## 治理规则

- `CR-META-BIN-NAMING` (X4 一致性, 守命名空间一致)
- `CR-META-BIN-ORPHAN` (X1 审计, 守"工具未接 caller" drift)

## 周期性检查

`gac-drift` / `gac-executor` 周期跑, 检测:
- 新增 bin/*.py 但无 caller (drift)
- 工具改名但 caller 未同步 (drift)
- 工具声称 description 与实际行为不符 (需要手动 review)
