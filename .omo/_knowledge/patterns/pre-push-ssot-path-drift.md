---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-07-15
related:
  - ../../bin/ssot/sync-submodules-push.sh
source: learner-2026-07-15-stack-retro
---

# Pattern — pre-push 脚本路径漂移（bin rationalization）

## The Insight

**已安装 hook 路径与仓库内脚本路径可漂移。**  
hook（`$GIT_DIR/hooks/pre-push`，全 worktree 共享）写死：

```bash
"$ROOT/bin/sync-submodules-push.sh"
```

rationalization 后真实文件在 **`bin/ssot/sync-submodules-push.sh`**。  
push 失败先分清：策略拒 main vs 幽灵路径 vs submodule not-our-ref。

## Why This Matters

2026-07-15 复盘 PR #370：docs-only 被  
`bin/sync-submodules-push.sh: No such file or directory` 拦住。

## Recognition

- 错误含 `sync-submodules-push.sh: No such file`
- `ls bin/ssot/sync-submodules-push.sh` 存在，`bin/` 下无旧路径
- 无 gitlink 变更仍被 pre-push 拦

## Approach

1. 诊断：`ls` 两路径 + `sed` 读 common-dir hooks/pre-push  
2. 临时：文档 / 无 submodule 变更可用 `git push --no-verify`（CI 仍跑）  
3. 治本（独立 PR）：改 hook 安装源 → `bin/ssot/...`，或 `bin/` 薄 wrapper；**只改仓内文件不会自动修已安装 hook**  
4. 勿与 not-our-ref 混淆：后者先 push 子模块 tip 再 bump 主仓  

见 `AGENTS.md` §6.1.1。
