---
id: ADR-0344
title: PASW — Per-Agent Submodule Worktree 子模块隔离
status: accepted
date: 2026-08-03
deciders: architecture-governance
supersedes: []
related:
  - 0106-agent-isolation-worktree.md
  - 0220-swarm-coordination.md
  - 0294-knowledge-gateway-decoupling.md
---

# ADR-0344: PASW — Per-Agent Submodule Worktree 子模块隔离

## Context

omostation 多 agent (最多 10 个) 并行开发, 共享 `/Users/xiamingxing/Workspace` 仓库.
当前 worktree 隔离方案 (ADR-0106) 隔离了 root repo 的 working tree, **但未隔离子模块**.
10 个 agent 同时修改 `projects/gbrain` / `projects/cockpit` / `projects/agora` 时,
共享的 submodule working directory 导致频繁的指针冲突、detached HEAD、push race.

### 冲突频率 (2026-07 起)

| 指标 | 数据 |
|------|------|
| 子模块相关 commit | 331 个 |
| 冲突相关 commit | 51 个 |
| 每次主要 PR 周期 | ≥ 1 个 "sync submodule pointer" 修复 commit |
| 最活跃冲突子模块 | gbrain > cockpit > agora |

### 根因链

1. **Worktree 不隔离子模块** — root worktree 隔离但 `projects/xxx/` 共享
2. **Squash merge 丢指针** — 多个 pointer bump 被压缩, 丢失中间状态
3. **Detached HEAD 泛滥** — worktree init 产生 detached HEAD, commit 在浮动 HEAD 上
4. **Pre-push 同步竞争** — 多 agent 同时 push 同一子模块
5. **无子模块级锁** — G-CONV.7 D1-D4 全是 root 级, 子模块无锁

## Decision

采用 **PASW (Per-Agent Submodule Worktree)**: 对 TOP 3 冲突子模块
(`gbrain` / `cockpit` / `agora`) 创建 per-agent 独立 worktree.

### 核心机制

```
ws-agent-A/
  .subtrees/gbrain/   ← Agent A 的 gbrain worktree (branch: agent/a-gbrain)
  .subtrees/cockpit/  ← Agent A 的 cockpit worktree (branch: agent/a-cockpit)
  projects/gbrain/     ← 共享 (保持原 gitlink commit, 不修改)
  projects/cockpit/    ← 共享 (保持原 gitlink commit, 不修改)

ws-agent-B/
  .subtrees/gbrain/   ← Agent B 的 gbrain worktree (branch: agent/b-gbrain)
  projects/gbrain/     ← 共享 (同上)
```

### 设计原则

1. **隔离写入, 共享读取** — 子模块 working directory 只读共享, 写入在 `.subtrees/` 内隔离
2. **指针指向 main** — root 指针必须指向 submodule `origin/main` (agent 分支合并后删除)
3. **CI fail fast** — 指针不可达时 CI checkout 立即失败, 不等 gate
4. **TTL 自动回收** — 超过 24h 的过期 worktree 自动清理

## Implementation

### 1. gac-worktree.sh 扩展

| 命令 | 功能 |
|------|------|
| `claim <session>` | 创建 root worktree + 子模块隔离 worktree |
| `bump-pointer <session> <sub>` | 更新 root 指针到子模块 worktree HEAD |
| `release <session>` | 清理子模块 worktree + root worktree |
| `cleanup` | TTL 回收过期 worktree |

### 2. 子模块 worktree 创建 (pasw_create)

```
对 ISOLATED_SUBS 中每个子模块:
  1. 检查是否已 init, 否则 git submodule update --init
  2. 从当前 HEAD 创建 agent/<session>-<sub> 分支
  3. git worktree add .subtrees/<sub> agent/<session>-<sub>
```

### 3. 指针更新 (bump-pointer)

```
1. 获取 .subtrees/<sub>/ 的 HEAD SHA
2. 验证 SHA 在 submodule origin/main 上 (CI 可达)
3. git update-index --cacheinfo 160000,<sha>,projects/<sub>
```

### 4. 强制约束

| 约束 | 机制 |
|------|------|
| 不允许 root 直接 `git add projects/<sub>` | pre-commit hook 拦截 |
| 指针必须指向 submodule origin/main | bump-pointer 验证 |
| `.subtrees/` 不入 root 仓库 | .gitignore + pre-commit hook |
| 子模块 commit 必须先 push | sync-submodules-push.sh PASW 适配 |
| CI 指针不可达 fail fast | checkout 无 continue-on-error |

### 5. 定时回收

`gac-worktree-cleanup.sh` — cron 每 6h 执行, TTL 24h:
- 扫描 `ws-*` 目录
- 超期 → 清理子模块 worktree → 移除 root worktree
- 支持 `--dry-run` 预览

## Consequences

### Positive

- **根除子模块冲突** — 无共享写状态, 冲突不可能发生 (by construction)
- **完全并行** — 各 agent 独立修改同一子模块, 零序列化
- **Git native** — 使用 `git worktree` 原生能力, 无 hack
- **磁盘可控** — worktree 共享 object DB, 仅 working tree 文件重复

### Negative

- **磁盘占用** — 10 agent × 3 sub × ~40MB = ~1.2GB (可接受)
- **流程变化** — agent 需适应 `.subtrees/` 内 commit + bump-pointer 两步
- **子模块 PR 依赖** — 子模块需先合并到 main, 才能 bump root 指针

### Risks

| 风险 | 缓解 |
|------|------|
| Agent 忘了 push 子模块就 bump | pre-commit + bump-pointer 双重验证 |
| Squash merge 丢指针 | CI reachability gate fail fast |
| 子模块 worktree 泄漏 | TTL cleanup + release 自动清理 |
| 隔离子模块间的依赖 | Agent 在自己的 worktree 里跑完整测试 |

## Compliance

- 所有 agent 必须通过 `gac-worktree.sh claim` 创建 worktree
- 子模块修改必须在 `.subtrees/` 内完成
- 指针更新必须通过 `gac-worktree.sh bump-pointer`
- CI 验证: reachability gate + checkout fail fast
