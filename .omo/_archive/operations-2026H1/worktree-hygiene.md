---
lifecycle: contract
owner: runtime-team
last_updated: 2026-07-31
review-state: metadata-only
metadata-migrated-at: 2026-07-31
title: Worktree 卫生（多 agent 栈落地后）
type: doc
---
# Worktree 卫生（多 agent 栈落地后）

## 何时清理

| 状态 | 动作 |
|------|------|
| PR 已 squash 合入 main，worktree **干净** | `git worktree remove --force <path>` + `git branch -D work/<session>` |
| PR 合入但 worktree **dirty** 仅为 runtime/cron/submodule mtime | 可 force remove（先 `git status` 确认无真改） |
| 仍有 **unique patch**（`git cherry origin/main` 含 `+`） | **保留**，先评估是否另开 PR |
| 进行中 session | 保留 |

## 推荐命令

```bash
# 列表
git worktree list
git branch -vv | grep 'work/'

# 补丁级是否已落地（squash 后 tip 不是 ancestor，用 cherry）
git cherry origin/main work/<session>   # 全为 - 表示已等价合入

# 释放
git worktree remove --force ../ws-<session>
git branch -D work/<session>
git fetch origin --prune
```

辅助脚本（只 dry-run 默认）：

```bash
bash bin/gac/gac-worktree-prune.sh          # 打印可删候选
bash bin/gac/gac-worktree-prune.sh --apply  # 真删 unique=0 且 dirty=0
```

## claim 注意

- 从 **已更新** 的仓库根跑 `bin/gac/gac-worktree.sh claim`（含 ADR-0204 默认 init）。  
  若本地 main 落后 origin，脚本本身可能是旧版 → 先 `git fetch` / 更新主仓指针或直接用 `origin/main` 上的脚本。
- 默认 init：`ecos scripts omo cockpit agora`。
- **Canonical root remote 解析**：`claim`/`submit`/`merge` 自动解析指向 `starlink-awaken/omostation` 的 remote，不再硬编码 `origin`；fetch 和 push URL 必须同时匹配，GitHub CLI 也显式绑定该仓库。解析顺序：`$OMOSTATION_ROOT_REMOTE` env → `omostation-root` named remote → URL 匹配 → fail closed。参见 `bin/gac/resolve-root-remote.sh`。

## 未 init 子模块的环境性 gate 失败（G9, 2026-08-24）

**症状**：本地 `gac-local-gate` / `verify` 报 CR-RESIDENT-BOS-01（缺
`bos-services.yaml`）、`omo-state-projection-guard`（缺 `.omo/state/runtime` 投影）、
`adr-link-validator` 等 FAIL，但改动本身与这些检查无关。

**根因**：worktree / clone 里 submodule 未 checkout（`git submodule update --init`
未跑或 SKIP_SUBMODULE_INIT=1）。gate 依赖子模块内的 registry/投影文件，未 init 即缺失。

**修复**：
```bash
cd <worktree>
git submodule update --init                 # 完整 init (ecos/omo/agora/cockpit 等)
# 或按需: git submodule update --init <sub>
# 然后重跑 gate: python3 bin/gac/gac-local-gate.py
```

**识别**：这是**环境性失败**，不是真实缺陷。先确认 `git submodule status` 是否有
`-` 前缀（未 init），再决定是否上报。上报环境性失败用 `--status blocked` + evidence
说明"submodule 未 checkout"。
