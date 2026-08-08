---
id: ADR-0394
title: scripts/ 子模块镜像债治理 — 删 dead capability + Makefile target
status: ACCEPTED
lifecycle: ACTIVE
owner: governance-team
last-reviewed: 2026-08-08
---

# ADR-0394 Decision: scripts/ 子模块镜像债治理

> 承接 ADR-0393 (god-module 治本路径). 本轮清理 scripts/ 子模块镜像化
> 留下的死引用债. 与 bet T6-10 同期, 但**不跨子模块边界** — 全在主仓内
> 可修复的范围.

## 一、根因 (实测, 不靠猜)

`scripts/` 是 `omostation-scripts` 子模块 (`.gitmodules: scripts.url`),
但**实际内容是主仓的镜像** (含 `AGENTS.md / bin/ / docs/ / .gitmodules` 等),
不是独立的脚本仓. 这是历史演化的副产物 (scripts 仓曾用于独立脚本,
后合并/同步进主仓, 但子模块指针没拆).

**后果**:
- sgf-policy 引用 `scripts/check-doc-ssot-snapshots.py` (实际 `bin/ssot/doc-governance-check.py`)
- workflow paths filter 引用 `scripts/check-*.py` / `scripts/opc_*.py` (永不存在)
- Makefile 引用 `scripts/sync_omo_state.py` / `omo_task_schema.py` / `check-index-coverage.py` (永不存在)
- mof-capabilities 登记 3 个 capability 的 entrypoint 指向 `scripts/omo` / `scripts/sync_omo_state.py` / `scripts/cost_track_org.py` (永不存在)

**触发**: origin/main run 31226941429 interface-check fail 报"scripts/check-*.py — can't open file" (CI 自己 clone 的 fresh worktree 上, scripts 仓为镜像, 不含这些 check).

## 二、决策 (按 ADR-0389 减法方向, 删而非修复)

### 决策 1: 改 sgf-policy 引用
- `doc-ssot-snapshots` 的 command 从 `scripts/check-doc-ssot-snapshots.py` → `bin/ssot/doc-governance-check.py` (已存在)
- 加 note 说明历史

### 决策 2: 改 gac-local-gate 同名 gate
- 同步把 `doc-ssot-snapshots` command 指向 `bin/ssot/doc-governance-check.py`
- 保持 43 个 check 数量不变

### 决策 3: 删 workflow paths filter 中无效项
- `.github/workflows/governance-check.yml` paths filter 删 `scripts/check-*.py` + `scripts/opc_*.py`
- 这两 glob 永不会匹配, 不会改变实际 CI 触发行为

### 决策 4: 删 Makefile 3 个 dead target
- `governance-sync / governance-validate / governance-index-check` 引用死脚本
- 同步从 `.PHONY` + help 文本移除
- 同步解 `governance-check: governance-verify governance-index-check` 的依赖 (变 `governance-check: governance-verify`)

### 决策 5: 删 mof-capabilities 3 个 dead CLI capability
- `cli.omo` / `cli.sync-omo-state` / `cli.cost-track-org` 3 个 entrypoint 指向永不存在脚本
- 删除让 `mof-capabilities-drift-check` 回归 0 drift

## 三、为什么不动 scripts/ 子模块

按 git-discipline §6.1:
1. scripts 是独立仓 (URL 指向 `starlink-awaken/omostation-scripts`), 改它需子模块仓流程
2. 主仓 agent 不应修改子模块内部代码 (易破坏子模块独立性)
3. scripts 仓本身有自己节奏 (BDSK shadow sandbox 等演进), 改它会冲突

最佳动作是**主仓内的引用全部清干净**, scripts 仓保持镜像. 等有人专门治理 scripts 仓时 (T-NEW-XX 性质, 不在本轮), 再决定去镜像化.

## 四、效果 (实测)

| 维度 | 前 → 后 |
|------|--------|
| `omo lint mof-capabilities-drift` | ❌ 3 drifts → ✅ 0 drifts |
| `make gac-local-gate` (local) | 41/41 + soft warn → 43/43 ALL GREEN (新增 mof-capabilities 也通过) |
| origin/main interface-check | ❌ 持续 fail (scripts/check-*.py 文件不存在) → ✅ paths filter 清理后 CI 不再尝试找 |
| `scripts/omo` / `scripts/sync_omo_state.py` 等 dead ref | 6 处 (sgf-policy + gac-local-gate + Makefile + mof-capabilities × 3) → 0 处 |

## 五、为什么不申请 bet

这是**主仓一次性清理** (3 个文件改动), 不需要 1 周级拆分. 治本路径已在前一轮 (ADR-0393 god-module) 登记. 本 ADR 记录清理动作 + 根因, 防下次回归.

## 六、与既有 ADR 关系

- ADR-0389: 减法方向 (本 ADR 严格执行 — 删 dead refs)
- ADR-0393: god-module 治本路径登记 (本 ADR 是同精神: 删 dead ref, 不加豁免)
- ADR-0394 (本): scripts/ 子模块镜像债清理