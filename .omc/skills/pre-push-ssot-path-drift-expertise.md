---
type: ssot
name: pre-push-ssot-path-drift-expertise
description: 主仓 pre-push 仍调用 bin/sync-submodules-push.sh，脚本已迁 bin/ssot/ 时的诊断与临时绕过
triggers:
  - sync-submodules-push.sh
  - No such file or directory
  - pre-push
  - bin/ssot/
  - failed to push some refs
  - CI_LOCAL_SKIP
  - git push --no-verify

last-reviewed: 2026-08-26
owner: governance-team
---

# pre-push 脚本路径漂移（bin rationalization）

## The Insight

omostation **主仓 pre-push hook 与仓库内脚本路径可以漂移**：hook 装在  
`$GIT_DIR/hooks/pre-push`（shared by all worktrees），内容写死：

```bash
ROOT="$(git rev-parse --show-toplevel)"
"$ROOT/bin/sync-submodules-push.sh"
```

而 bin rationalization 后真实文件在：

```text
bin/ssot/sync-submodules-push.sh
```

**原则：push 失败先区分「策略拒绝 main」vs「hook 引用幽灵路径」；后者是安装态/路径 SSOT 问题，不是你的 commit 坏了。**

## Why This Matters

2026-07-15 复盘 PR 在 worktree `ws-stack-retro` 上：

```text
[pre-push] .../bin/sync-submodules-push.sh: No such file or directory
error: failed to push some refs
```

文档-only 分支因此被拦。`ls bin/ssot/sync-submodules-push.sh` 存在，  
`bin/sync-submodules-push.sh` 不存在。与「子模块未推」类 reachability 失败不同。

## Recognition Pattern

- 错误含 **`bin/sync-submodules-push.sh: No such file`**
- worktree 或主仓 `ls bin/sync-submodules-push.sh` 失败，但 `bin/ssot/` 下有同名
- 同时可能叠加：`submodule-reachability`、`ci-local-fast`
- 改的是 docs-only / 无 gitlink 变更仍被 pre-push 拦

## The Approach

1. **诊断**（在当前 worktree root）：
   ```bash
   ls -la bin/sync-submodules-push.sh bin/ssot/sync-submodules-push.sh
   sed -n '55,70p' "$(git rev-parse --git-common-dir)/hooks/pre-push"
   ```
2. **临时推进（已知路径漂移、变更无子模块）**：
   ```bash
   # 文档 / 无 submodule pointer：可 --no-verify（P72 既有约定）
   git push -u origin HEAD --no-verify
   ```
   或仅跳预检：`CI_LOCAL_SKIP=1 git push`（若只卡 ci-local-fast、脚本路径仍在则仍失败）。
3. **治本（另开 PR，勿与功能 PR 搅在一起）**：
   - 改 **hook 安装源**（`.githooks/pre-push` 或 `make install-hooks` 模板）→  
     `"$ROOT/bin/ssot/sync-submodules-push.sh"`
   - 或恢复 `bin/sync-submodules-push.sh` 为薄 wrapper 转调 `bin/ssot/`
   - 改完后在各机器重跑 hook 安装；**只改仓库文件不会自动修已安装 hook**
4. **不要** 为了过 hook 去删/改无关 dirty 文件或 force 推 main。
5. 与 **submodule not-our-ref** 区分：那种要先 push 子模块 tip 再 bump 主仓 gitlink；路径缺失是 hook 引用错误。

## Example

```bash
# 本次复盘 PR #370
git push   # FAIL: bin/sync-submodules-push.sh missing
ls bin/ssot/sync-submodules-push.sh   # exists
git push --no-verify                  # docs-only OK；CI 仍会跑完整检查
```

相关：`AGENTS.md` §6.1.1 worktree 踩坑；`bin/ssot/sync-submodules-push.sh`。
