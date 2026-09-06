# Git Hooks (主仓) — 机制 22c 统一框架

本目录是 canonical hooks 来源。机制 22c (2026-09) 引入统一安装/校验框架：

- **canonical** (本目录): hooks 生产源，唯一编辑点
- `bin/gac/hook-runner.sh`: manifest 驱动的统一 hook runner (分派到各 hook)
- `bin/gac/hook-installer.sh`: 安装器，向真实 `git-dir/hooks` 写 `.version`/`.content-hash` 元数据
- `.omo/_truth/registry/hook-manifest.yaml`: hook 段位/脚本/超时清单 (SSOT)
- `bin/gac/hook-health-check.py`: 版本/hash/缺失/孤儿健康检查

> **core.hooksPath**: 本仓配置 `core.hooksPath=.githooks`，hooks 直接从 canonical 生效
> (不复制到 `.git/hooks`)。installer 只负责维护 `git-dir/hooks` 下的版本/内容指纹元数据，
> 供 health-check 与版本自检使用。

## hook 清单

### pre-commit — GaC / SSOT 本地硬门

commit 前运行 (blocking 失败即 exit 1)，委托 `hook-runner.sh --hook pre-commit`:

- 克隆守卫 (`agent-clone.py guard`)
- 分支前缀策略 (`check-branch-naming.py`)
- 冲突标记 (`check-conflict-markers.py`)
- 大量删除守卫 (`mass-deletion-gate.py --staged`)
- 运行时产物黑名单 (`check-runtime-artifacts.py --staged`)
- 债务文件守卫 (`debt-directory-guard.py`)
- 子模块 fast-forward (`submodule-guard.py --staged`)
- 目录卫生 advisory (`gac-hygiene-check.py`)

完整检查清单 (脚本/超时/blocking) 见 [`hook-manifest.yaml`](../.omo/_truth/registry/hook-manifest.yaml) (SSOT)。

### pre-push — 子模块自动同步硬门

主仓 push 前自动把"本地领先远程"的子模块 push 上去,让 gitlink 可达,防 CI 悬空。子模块同步失败会阻断主仓 push。委托 `hook-runner.sh --hook pre-push`，另执行 分支命名 / 直推 main 守卫 / reachability / gitlink 祖先 / 远程卫生 等检查（完整清单见 `hook-manifest.yaml`）。

**病根**:自动化 agent (OMC/autopilot) commit 子模块 + bump 主仓指针却不 push → 主仓 gitlink 指向子模块远程没有的 commit → CI `submodules: recursive` 拉不到 (`not our ref`) → 整条 CI 红。(2026-06-17 实测 14/18 子模块悬空)

同步逻辑 SSOT：[`bin/ssot/sync-submodules-push.sh`](../bin/ssot/sync-submodules-push.sh)  
兼容入口：[`bin/sync-submodules-push.sh`](../bin/sync-submodules-push.sh)（薄 wrapper）。

### commit-msg — chore(state) 禁止直连 main (T10-57)

分支保护会拒绝 main 直推，`chore(state)` 类提交留在本地 main 只会被 reset 成孤儿
（commit → push 拒 → reset 循环，2026-08-29 实测）。此 hook 在本地 main 上拦截
该类提交，引导走 worktree+PR（如 #2519）。逃生口: `SWARM_ESCAPE_ID=<id>` (D4)。

### post-checkout — 分支检出后命名合规

`git checkout` / `git switch` / `git worktree add` (flag=1 分支切换) 触发:

- `bin/gac/check-branch-naming.py --branch $BRANCH --policy ...` (blocking)

委托 `hook-runner.sh --hook post-checkout` 执行。新分支命名不合规会阻断检出。

### post-merge — 合并后检查

`.githooks/post-merge` (canonical 内联实现, advisory only):
子模块指针变更通知 + 文档自动同步 (`post-commit-sync-check.py`) + state-stale 检查
(`state-stale-emit.py --source post-merge`)。完整清单见 `hook-manifest.yaml`。

### pre-merge-commit — 合并前校验

`.githooks/pre-merge-commit` (canonical 内联实现, blocking):
`git merge` 生成提交前校验:

- `bin/gac/submodule-guard.py --merge` (blocking)
- `bin/gac/check-conflict-markers.py` (blocking)
- `bin/gac/mass-deletion-gate.py --staged` (blocking)

### pre-rebase — 危险 rebase 拦截

`.githooks/pre-rebase` (canonical 内联实现, blocking):
拒绝 rebase onto main，拒绝 base 非 HEAD 祖先的重写式 rebase。含 `SWARM_ESCAPE_ID` 逃生口。

### pre-edit-architecture — 架构感知预编辑钩子 (Phase 8)

编辑架构相关文件前自动检查合规性:
- 场景卡生命周期 (5 级门控 + promotion_evidence)
- Journey 规范 (状态机 + initial_state)
- 架构标准一致性 (调用 architecture-check.py)
- Harness 策略合规 (调用 harness-compliance-check.py)

**触发条件**: 编辑 `docs/scene-cards/`, `docs/journey-specs/`, `.omo/standards/`, `bin/harness` 时

**逃生口**: `SKIP_PRE_EDIT_ARCH=1 git commit ...`

### prepare-commit-msg-commit-assist — LLM advisory (P76 Phase 9A)

`git commit` (无 -m, 无 -F) 触发:
- 调 `bin/commit-assist.py --no-llm` (heuristic tier, 立即返回)
- 写侧车 `.commit-suggestion` (gitignored)
- 在 commit msg 末尾追加 hint (developer 可手动 `git commit -F .commit-suggestion`)

**硬门 (P76-7-1)**: LLM 不能 auto-apply. developer 必须显式接受.

**跳过模式** (developer 已明确意图):
- `git commit -m "..."` → 跳过 (COMMIT_SOURCE=message)
- `git commit -F <file>` → 跳过 (developer 自选 source)
- amend / merge / squash → 跳过 (template mode)

## 安装 (新 clone 必跑)

```bash
make install-hooks
```

等价于 `bash bin/gac/hook-installer.sh`：
- 校验 canonical 与安装元数据一致
- 向 `$(git rev-parse --git-common-dir)/hooks` 写 `.version` + `.content-hash`（worktree 下指向共享主仓 `.git`，元数据单点）
- (兼容) 额外生成 `pre-edit-architecture` 旧名副本

改 `.githooks/` 后须在本机重跑 `make install-hooks` (已安装元数据不会自动更新)。

## 校验

```bash
python3 bin/gac/hook-health-check.py          # 版本/hash/缺失/孤儿
python3 bin/gac/hook-health-check.py --json   # JSON 输出
```

健康检查从真实 `git-dir/hooks` 读 `.version`/`.content-hash`，per-hook 生效判断
遵循 `core.hooksPath` (指向 canonical 时视为已生效)。
