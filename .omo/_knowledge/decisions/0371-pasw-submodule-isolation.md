---
id: ADR-0371
title: PASW — Per-Agent Submodule Worktree 隔离
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last-reviewed: 2026-08-04
related:
  - 0220-swarm-coordination-discipline-m1-gate.md
  - 0106-gac-governance-as-code.md
  - ../patterns/p74-workflow-solidification-pattern.md
supersedes: []
type: ssot
---

# ADR-0371: PASW — Per-Agent Submodule Worktree 隔离

> **背景**: 编号 0371。本 ADR 固化 PASW (Per-Agent Submodule Worktree) 机制，
> 修复此前对 ADR-0355 的错误引用。**ADR-0355 实为 Workflow Mesh 评测 manifest
> 材料化**，PASW 的机制此前仅散落在 `swarm-coordination.yaml::d5_pasw_submodule_isolation`
> 与工具注释中，无独立 ADR 归档。

## Context and Problem Statement

多 agent 并行（ADR-0220）下，高冲突子模块（gbrain / cockpit / agora）存在两类撞车：

1. **主仓 worktree 隔离不足**：per-session worktree 只隔离主仓文件，子模块仍是共享的
   `projects/<sub>` gitlink。并发 agent 同时修改同一子模块 → gitlink 指针互相覆盖。
2. **root 直接 stage gitlink**：agent 在共享 main worktree 直接 `git add projects/<sub>`，
   bypass 了主仓的 worktree 隔离，D3 claim-check 无法覆盖子模块内部文件。

此前 `gac-worktree.sh` 注释将机制指向 ADR-0355，但 0355 实际是
`workflow-evaluation-manifest-materialization.md`（Workflow Mesh 评测 manifest），
SSOT 引用断裂。需要独立 ADR 固化 PASW 的决策、机制与边界。

## Decision

对 **高冲突子模块**（按冲突频率排序：gbrain、cockpit、agora）实施
**Per-Agent Submodule Worktree (PASW)** 隔离：

### 机制

1. **claim 时创建隔离 worktree**：`gac-worktree.sh claim <session>` 在
   `.subtrees/<sub>/` 为每个高冲突子模块创建独立 worktree，分支为
   `agent/<session>-<sub>`，基于当前子模块 HEAD。
2. **子模块修改必须在 `.subtrees/` 内完成**：agent 只能在
   `.subtrees/<sub>` 中改子模块文件并 commit。
3. **主仓 bump 指针**：用 `gac-worktree.sh bump-pointer <session> <sub>` 或
   `bin/ssot/submodule-pointer-transaction.sh` 更新主仓 gitlink。
4. **pre-commit submodule-guard 强制**：root 直接 stage
   `projects/<sub>` gitlink → 拒绝；且 staged SHA 必须等于
   `.subtrees/<sub>` worktree HEAD，确保指针改动确实来自隔离 worktree。
5. **release 时清理**：`gac-worktree.sh release` / `merge` 调 `pasw_cleanup`
   移除 `.subtrees/` worktree 与 `agent/<session>-<sub>` 分支。

### 边界

- **隔离子模块集**（`PASW_ISOLATED_SUBS`）：`projects/gbrain projects/cockpit projects/agora`。
  其他子模块（如 ecos、kairon）不强制 PASW，仍可 direct push。
- **TTL**：`.subtrees/` worktree TTL 24h（与 lock TTL 一致），
  过期由 `bin/gac/gac-worktree-cleanup.sh` 清理。
- **`.subtrees/` 不入主仓**：gitignore 排除，禁止 commit 到 root。

### 与 D1-D4 的关系

PASW 是 D1-D4 之外的**物理隔离层**，解决"共享树 + 共享子模块"的双重撞车：
- D3（claim-check）管主仓 staged 文件；PASW submodule-guard 管子模块 gitlink。
- D4（escape-hatch）仍适用于 PASW（`--no-verify` 需 `SWARM_ESCAPE_ID`）。
- CI reachability gate 兜底：验证主仓 gitlink SHA 在子模块 remote 可达
  （即使本地 PASW 被绕过，CI 全量 checkout 仍会拦截不可达指针）。

## Consequences

- ✅ 高冲突子模块的并发修改被物理隔离，gitlink 不再互相覆盖。
- ✅ submodule-guard 提供 fail-closed 强制，不依赖 agent 自觉。
- ⚠️ 增加操作成本：改 gbrain/cockpit/agora 必须走 `.subtrees/` worktree + bump-pointer。
- ⚠️ `.subtrees/` worktree 需 TTL 清理，避免残留（gac-worktree-cleanup.sh 负责）。
- ⚠️ 仅覆盖 3 个高冲突子模块，其他子模块仍共享（冲突频率低，可接受）。

## Implementation

- 核心实现：`lib/pasw-core.sh`（`pasw_create` / `pasw_cleanup` / `pasw_claim_*`）
- 入口：`bin/gac/gac-worktree.sh`（claim / bump-pointer / release / merge）
- 强制：`.githooks/pre-commit`（submodule-guard）+ CI reachability gate
- 清理：`bin/gac/gac-worktree-cleanup.sh`
- SSOT：`.omo/_truth/registry/swarm-coordination.yaml::d5_pasw_submodule_isolation`
