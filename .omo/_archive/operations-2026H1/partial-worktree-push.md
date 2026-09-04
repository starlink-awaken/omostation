---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: Partial Worktree Push 操作规范 (G2)
type: doc
---
# Partial Worktree Push 操作规范 (G2)

> **来源**: P79 pattern · #907 35+ iteration 实证 · 2026-08-04
> **场景**: 本地 partial worktree (子模块未全 init) 的 push 治理

## 0. 何时用本规范

本地 pre-push reachability gate (`bin/ssot/submodule-reachability-gate.py --fetch`)
在 partial worktree 下产生 **false-positive FAIL** (子模块未 init → `branch --contains` 找不到 SHA).
死磕 `git submodule update --init` (18 子模块超时 10min) 是死路.

**判断**: 若你的 worktree 子模块未全 init (PASW ISOLATED partial / 新建 worktree), 用本规范.

## 1. 判断矩阵

| 场景 | 用本地 push | 用 GitHub API (本规范) |
|------|------------|----------------------|
| 主仓子模块全 init (full checkout) | ✅ | 不必 |
| PASW partial worktree (ISOLATED) | ❌ false positive | ✅ |
| 新建 worktree 子模块空 | ❌ false positive | ✅ |
| 只改非 gitlink 文件 (gate.py/config/docs) | ❌ false positive | ✅ |

## 2. GitHub API 直改远程 (4 步)

```bash
REPO=starlink-awaken/omostation
MAIN_SHA=$(git rev-parse origin/main)

# 1. 创建工作分支 (基于 main)
gh api -X POST /repos/$REPO/git/refs \
  -f ref=refs/heads/work/<branch> -f sha=$MAIN_SHA --jq '.ref'

# 2. PUT 文件 (base64, 注意 -F vs -f)
for f in <path1> <path2>; do
  SHA=$(gh api "/repos/$REPO/contents/$f?ref=work/<branch>" --jq '.sha' 2>/dev/null || echo "")
  CONTENT=$(base64 -i "$f" | tr -d '\n')
  ARGS=(-f message="..." -f content="$CONTENT" -f branch=work/<branch>)
  [ -n "$SHA" ] && ARGS+=(-f sha="$SHA")
  gh api -X PUT "/repos/$REPO/contents/$f" "${ARGS[@]}" --jq '.commit.sha'
done

# 3. 开 PR
gh pr create --repo $REPO --base main --head work/<branch> --title "..." --body "..."

# 4. watch CI (CI full checkout = 真正守门员) + merge
gh pr checks <n> --watch
gh pr merge <n> --squash --delete-branch --admin
```

## 3. 关键注意

- **`-F force=true` (typed boolean)** 不是 `-f force=true` (string, HTTP 422) — 仅 PATCH ref 时
- **CI 是最终守门员**: GitHub Actions `submodules: recursive` full checkout, reachability gate 正常严格验证
- **新文件** (main 没有): PUT 不需要 `sha`; **已有文件**: 必须带 `sha` (GET 拿)
- **base64**: macOS `base64 -i file | tr -d '\n'`

## 4. 为什么安全

本地 partial gate FAIL 是 **false positive** (子模块未 init, 不是 gitlink 真坏).
GitHub API 绕过本地 hook, 但 **CI (full checkout) 会真实验证 gitlink 可达**.
若 gitlink 真坏, CI gac-gate FAIL → 拦 merge → 不会进 main.

## 5. 治本路径 (G1, 待推广)

G1 (PR #935): gate.py 加 partial 降级 — 子模块未 init 时本地 gate 也降级 warning 不 block.
G1 merge 后, 本规范适用于"未装 G1 的旧 gate" 或 "想完全绕本地 hook" 场景.

## 6. 关联

- [P79](../../.omo/_knowledge/patterns/p79-partial-worktree-reachability-false-positive.md) — 本规范的模式沉淀
- [ADR-0151](../../.omo/_knowledge/decisions/0151-submodule-hygiene-gate.md) — submodule hygiene gate
- `.githooks/pre-push` — line 75 硬跑 reachability gate
- `bin/ssot/submodule-reachability-gate.py` — gate 实现 (G1 降级点)
- #907 (ffce388ab) · #934 (e2b4235de) · #935 — 本规范实证 PR
