---
id: ADR-0394
title: scripts/ 子模块镜像债治理 — 已退役并迁移到 root bin/
status: superseded
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-22
superseded_by: 迁移已完成 (PR #1839 + scripts PR #27/#28)
type: ssot
---

# ADR-0394 Decision: scripts/ 子模块镜像债治理 — 已退役

> **状态**: 已退役 (2026-08-22)。scripts 仓库工具已迁移到 root `bin/`，
> 仓库已 archive。本 ADR 保留作为历史记录。

## 一、原始根因 (2026-08-08)

`scripts/` 是 `omostation-scripts` 子模块 (`.gitmodules: scripts.url`),
但**实际内容是主仓的镜像** (含 `AGENTS.md / bin/ / docs/ / .gitmodules` 等),
不是独立的脚本仓. 这是历史演化的副产物 (scripts 仓曾用于独立脚本,
后合并/同步进主仓, 但子模块指针没拆).

**原始后果**:
- sgf-policy 引用 `scripts/check-doc-ssot-snapshots.py` (实际 `bin/ssot/doc-governance-check.py`)
- workflow paths filter 引用 `scripts/check-*.py` / `scripts/opc_*.py` (永不存在)
- Makefile 引用 `scripts/sync_omo_state.py` / `omo_task_schema.py` / `check-index-coverage.py` (永不存在)
- mof-capabilities 登记 3 个 capability 的 entrypoint 指向 `scripts/omo` / `scripts/sync_omo_state.py` / `scripts/cost_track-org.py` (永不存在)

## 二、最终决策 (2026-08-22)

按 ADR-0389 减法方向，执行 **scripts 仓库退役**：

### 决策 1: 工具迁移到 root
- 57 个 scripts 独有工具 → root `bin/` (按类别迁移到 gac/, ssot/, delivery/, mof/)
- 95 个重叠文件 → root 版本全部更新，无需改动
- 47 个低价值脚本 → `_archive/` (满足 subtraction-quota 基线 420)

### 决策 2: scripts 仓库 archive
- 删除镜像结构 (`projects/`, `protocols/`, `runtime/`)
- 删除嵌套子模块 (`scripts/scripts/`)
- 禁用所有 CI workflow (`on: []`)
- 更新 README 标记为 ARCHIVED
- 清理 `.gitmodules` 和 `.git/config` 子模块条目

### 决策 3: Root 仓库清理
- 更新 AGENTS.md 标记 scripts 为 ARCHIVED
- 更新 capability-registry (新增迁移工具条目)
- 更新 convergence-manifest (移除归档脚本)
- 更新 scripts 子模块指针到最终 commit

## 三、效果 (实测)

| 维度 | 前 → 后 |
|------|--------|
| scripts 仓库 CI | 5 个恒红 workflow → 全部禁用 |
| `make gac-local-gate` | 46/46 checks → 46/46 ALL GREEN |
| scripts 仓库活跃度 | 镜像结构 + 嵌套子模块 → 已清理 archive |
| 工具可发现性 | scripts/bin/ 难以发现 → root bin/ 统一入口 |
| 能力注册表漂移 | 迁移工具未注册 → 已同步 |

## 四、关联 PR

- Root #1839: feat: migrate scripts repo tools to root bin/ + archive scripts repo
- scripts #27: fix(ci): remove 5 misplaced root-repo workflows
- scripts #28: ch: cleanup scripts repo for archive
- Root #1822: fix(runtime): bump runtime pointer — fix hermes scripts test

## 五、与既有 ADR 关系

- ADR-0389: 减法方向 (本 ADR 严格执行 — 删 dead refs + 退役仓库)
- ADR-0393: god-module 治本路径登记 (本 ADR 是同精神: 删 dead ref, 不加豁免)
- ADR-0394 (本): scripts/ 子模块镜像债清理 — 已退役
