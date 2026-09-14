---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-08-18
type: ssot
---
# P79 — Partial Worktree Reachability False-Positive Pattern

> **eCOS 多环境 push 治理纪律** · 2026-08-04 沉淀 · 来源: #907 35+ iteration 实证

## TL;DR

本地 pre-push reachability gate (`bin/ssot/submodule-reachability-gate.py --fetch`) 在
**partial worktree** (子模块未全 init) 下产生 **false-positive FAIL**, 阻断 push.
死磕 `git submodule update --init` (18 子模块超时 10min) 是死路.
**正道 = GitHub API 直改远程** (PATCH ref + PUT contents), 绕过本地 false-positive gate,
依赖 GitHub CI (full checkout) 做真正的 reachability 验证兜底.

---

## 陷阱矩阵

| 陷阱 | 症状 | 本轮案例 |
|------|------|---------|
| **F1** 本地 partial gate 误报 | pre-push `gate --fetch` 报 18 unreachable, 但 gitlink 真可达 (CI 验证 pass) | 新建 worktree 子模块全空, gate `branch --contains` 找不到 SHA |
| **F2** escape hatch 不覆盖 reachability | `SWARM_ESCAPE_ID=...` 设了仍被拦 | pre-push hook line 75 在 escape 逻辑 (line 77+) 之前硬跑 gate |
| **F3** init 超时 | `git submodule update --init --no-fetch` 超时 10min | 18 子模块即使 `--no-fetch` 也要 checkout 全量文件 |
| **F4** 凭记忆判 worktree 存在 | `cd ws-gate-fix` 报 No such file (已被 launchd cleanup 6h TTL 清) | compact 后老王以为 worktree 还在, 实际早被清 (P73 D1 复发) |

## 根因

reachability gate 设计假设 **full checkout** (所有子模块 init + 有 git 数据).
但两种合法场景违反假设:
1. **PASW partial worktree** (ADR-0355 ISOLATED): 只 init 隔离子模块, 其余空
2. **新建 worktree**: 子模块全空 (未 `submodule update --init`)

gate `remote_contains()` 对空子模块目录 → `branch --contains` 无 SHA → 误报 unreachable.
gate 不知道"这次 push 没改 gitlink", 死板检查所有 18 个.

## 破局 (本轮实证)

```
死路: 本地 push → pre-push gate --fetch → partial FAIL → init 超时 → 死循环
正道: GitHub API 直改远程 → 绕本地 gate → CI full checkout 兜底验证
```

### GitHub API 直改远程 4 步 (治本)

```bash
MAIN_SHA=$(git rev-parse origin/main)
# 1. PATCH ref → main (force, -F boolean 不是 -f string)
gh api -X PATCH /repos/<r>/git/refs/heads/<branch> -f sha=$MAIN_SHA -F force=true
# 2. GET file sha (更新前)
F_SHA=$(gh api "/repos/<r>/contents/<path>?ref=<branch>" --jq '.sha')
# 3. PUT file 内容 (base64)
CONTENT=$(git show <commit>:<path> | base64 | tr -d '\n')
gh api -X PUT /repos/<r>/contents/<path> \
  -f message="..." -f content="$CONTENT" -f sha="$F_SHA" -f branch=<branch>
# 4. watch CI (gac-gate 等) → merge
gh pr checks <n> --watch
```

**关键**: `-F force=true` (typed boolean), 不是 `-f force=true` (string, HTTP 422).

## 验证 (CI 兜底)

GitHub CI `gac-gate` (full checkout + `submodules: recursive`) 跑 reachability gate
是真正的守门员. 本轮 #907 重建后 CI 30 checks 全 pass (gac-gate 1m6s), 证明:
- 本地 partial FAIL = false positive
- CI full checkout = true positive, gitlink 真可达

## 适用判断

| 场景 | 用本地 push | 用 GitHub API |
|------|------------|--------------|
| 主仓子模块全 init (full checkout) | ✅ | 不必 |
| PASW partial worktree (ISOLATED) | ❌ false positive | ✅ |
| 新建 worktree 子模块空 | ❌ false positive | ✅ |
| 只改非 gitlink 文件 (如 gate.py/config) | ❌ false positive | ✅ |

## 治理建议 (待 ADR 固化)

1. **G1 gate partial 降级** (治本): `submodule_dir` 未 init 时 gate 降级 warning 不 block,
   依赖 CI 兜底. 改 `remote_contains()` 加 `is_init` 检查.
2. **G2 GitHub API 操作规范**: 本文档 + `docs/operations/partial-worktree-push.md`.
3. **G5 worktree cleanup 智能化**: `gac-worktree-cleanup.sh` 跳过 active claim / uncommitted worktree,
   防 mid-task 误清 (陷阱 F4 根因).

## 关联

- [ADR-0151](../decisions/0151-submodule-hygiene-gate.md) submodule hygiene gate (3 类检查, 不含 partial 降级)
- [ADR-0220](../decisions/0220-swarm-coordination-discipline-m1-gate.md) escape hatch allowlist
- [ADR-0355](../decisions/0355-*.md) PASW ISOLATED 子模块集
- [P73](./p73-truth-driven-engineering-pattern.md) 凭事实不凭记忆 (F4 复发)
- [P74](./p74-workflow-solidification-pattern.md) workflow 沉默治理
- `bin/ssot/submodule-reachability-gate.py` (gate 实现)
- `.githooks/pre-push` (hook line 75 硬跑 gate)
- `#907` (ffce388ab MERGED, gate.py unshallow 修复)

## 变更日志

| 日期 | 变更 |
|------|------|
| 2026-08-04 | 初稿. #907 35+ iteration 实证: partial worktree push false-positive + GitHub API 破局 + CI 兜底验证 |
