---
type: ssot
---

# Git Hooks (主仓)

## pre-push — 子模块自动同步硬门

主仓 push 前自动把"本地领先远程"的子模块 push 上去,让 gitlink 可达,防 CI 悬空。子模块同步失败会阻断主仓 push。

**病根**:自动化 agent (OMC/autopilot) commit 子模块 + bump 主仓指针却不 push → 主仓 gitlink 指向子模块远程没有的 commit → CI `submodules: recursive` 拉不到 (`not our ref`) → 整条 CI 红。(2026-06-17 实测 14/18 子模块悬空)

## pre-commit — GaC / SSOT 本地硬门

commit 前依次运行:

- `bin/gac-hygiene-check.py` (advisory)
- `bin/gac-local-gate.py` (blocking)
- `bin/ssot-guardian.py` (blocking)

## commit-msg — chore(state) 禁止直连 main (T10-57)

分支保护会拒绝 main 直推，`chore(state)` 类提交留在本地 main 只会被 reset 成孤儿
（commit → push 拒 → reset 循环，2026-08-29 实测）。此 hook 在本地 main 上拦截
该类提交，引导走 worktree+PR（如 #2519）。逃生口: `SWARM_ESCAPE_ID=<id>` (D4)。

## pre-edit-architecture — 架构感知预编辑钩子 (Phase 8)

编辑架构相关文件前自动检查合规性:
- 场景卡生命周期 (5 级门控 + promotion_evidence)
- Journey 规范 (状态机 + initial_state)
- 架构标准一致性 (调用 architecture-check.py)
- Harness 策略合规 (调用 harness-compliance-check.py)

**触发条件**: 编辑 `docs/scene-cards/`, `docs/journey-specs/`, `.omo/standards/`, `bin/harness` 时

**逃生口**: `SKIP_PRE_EDIT_ARCH=1 git commit ...`

## 安装 (新 clone 必跑)

```bash
make install-hooks
```

从 `.githooks/` 复制所有 hook 到 `.git/hooks/` (包括 pre-edit-architecture)。

同步逻辑 SSOT：[`bin/ssot/sync-submodules-push.sh`](../bin/ssot/sync-submodules-push.sh)  
兼容入口：[`bin/sync-submodules-push.sh`](../bin/sync-submodules-push.sh)（薄 wrapper）。  
改 `.githooks/` 后须在本机重跑 `make install-hooks`（已安装 hook 不会自动更新）。

## prepare-commit-msg-commit-assist — LLM advisory (P76 Phase 9A)

`git commit` (无 -m, 无 -F) 触发:
- 调 `bin/commit-assist.py --no-llm` (heuristic tier, 立即返回)
- 写侧车 `.commit-suggestion` (gitignored)
- 在 commit msg 末尾追加 hint (developer 可手动 `git commit -F .commit-suggestion`)

**硬门 (P76-7-1)**: LLM 不能 auto-apply. developer 必须显式接受.

**跳过模式** (developer 已明确意图):
- `git commit -m "..."` → 跳过 (COMMIT_SOURCE=message)
- `git commit -F <file>` → 跳过 (developer 自选 source)
- amend / merge / squash → 跳过 (template mode)
