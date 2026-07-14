# 子模块 PR 策略 — Phase 2a-4 设计

> 状态: 📋 设计完成(方案 A' 推荐) · 2026-06-30 · 关联: [`docs/AGENT-ISOLATION-ROLLOUT.md`](AGENT-ISOLATION-ROLLOUT.md) §4 Phase 2

---

## 1. 问题

PR 工作流下主仓走 PR(`work/<session>` → main),但主仓 PR 含**子模块 pointer bump**。若子模块 commit 未到子模块远程,PR merge 后主仓 main 的 gitlink 指向子模块远程没有的 commit → CI `submodules: recursive` 拉不到("not our ref")→ 整条 CI 红。

即 Phase 2 的核心约束:**PR merge 后 gitlink 必须可达**。

## 2. 现状机制(已就绪)

`bin/ssot/sync-submodules-push.sh`(主仓 `.git/hooks/pre-push` 调用):
- 遍历 `.gitmodules` 17 个子模块
- 检测每个子模块"本地领先远程"的 commit(`@{u}..HEAD`)
- `git push --no-verify origin <branch>` direct push(跳子模块 pre-push,避免容器化 e2e 挂死)
- 任一失败 → exit 1 阻断主仓 push

在 direct-push 工作流下已验证治本(commit `治本 D`,2026-06-17 实测 14/18 悬空 → 修复)。

## 3. 方案 A'(推荐,KISS + YAGNI):主仓 PR + 子模块 direct push

| 仓库 | 策略 | 依据 |
|:---|:---|:---|
| **主仓 main** | branch protection(走 PR) | 多 agent 撞车主战场(GaC doctor/compliance/verify worktree-wide);17 域变更汇聚于此 |
| **子模块 main ×17** | **不保护**(保持 direct push) | 独立 repo,每个专注一域,撞车概率低;复用 sync-submodules 零改造 |

**决策依据**:
- Phase 1 验证 + commit 死循环治本都指向**主仓共享 worktree**是撞车根因,子模块非痛点
- `sync-submodules-push.sh` 天然处理子模块 direct push,PR 流程下继续工作(pre-push 在 worktree push 主仓 work/<session> 时照样触发)
- YAGNI:子模块撞车未成痛点前,不引入两段式 PR 的协调开销

## 4. worktree 子模块操作流程

```bash
# 1. 起 worktree
bash bin/gac/gac-worktree.sh claim fix-kairon-bug
cd ../ws-fix-kairon-bug

# 2. init 要改的子模块 (worktree 默认不 init, Phase 1 实证)
git submodule update --init projects/kairon

# 3. 子模块切 main 分支 (init 后默认 detached HEAD)
cd projects/kairon && git checkout main

# 4. 改子模块 + commit (子模块 .git 数据共享主仓)
# ... 改文件 ...
git add -A && git commit -m "fix(kairon): ..."

# 5. 回主仓 worktree, bump pointer + commit
cd ../..
git add projects/kairon  # bump pointer
git commit -m "chore: bump kairon — fix-kairon-bug"

# 6. submit (push 主仓 work/<session> → pre-push 触发 sync-submodules → 子模块 direct push origin/main)
bash bin/gac/gac-worktree.sh submit fix-kairon-bug

# 7. PR review + merge
bash bin/gac/gac-worktree.sh merge fix-kairon-bug
# → main 含 pointer bump + 子模块已 push → gitlink 可达
```

## 5. 方案 B(备选,未来升级):子模块也走 PR

子模块 main 也 branch protection,两段式 PR 串行:
1. 子模块仓 PR(`work/sm-<session>` → 子模块 main)合并
2. 主仓 PR(pointer bump)合并,gitlink 指向已合并的子模块 commit

**何时升级**:某子模块出现多 agent 并发改同一子模块的撞车(类似主仓 commit 死循环)。届时:
- 子模块独立 worktree(`gac-worktree.sh` 扩展子模块维度)
- 子模块 branch protection
- 两段式 PR 编排工具(子模块 merge 触发主仓 bump PR)

当前 YAGNI,不实现。

## 6. 验证(ISC)

- **ISC-SM-1**: worktree submit 后,`bin/ssot/submodule-reachability-gate.py --source head --fetch` PASS(gitlink 可达)
- **ISC-SM-2**: PR merge 后,CI `submodules: recursive` 不报 "not our ref"
- **ISC-SM-3**: `sync-submodules-push.sh --dry-run` 在 worktree 内正确检测领先子模块

## 7. 风险

| 风险 | 缓解 |
|:---|:---|
| worktree 里子模块 detached HEAD,push 错分支 | 流程 step 3 显式 `git checkout main`;sync-submodules 用 `@{u}` 检测兜底 |
| 子模块 direct push 认证失败 | sync-submodules exit 1 阻断,提示排查 |
| 多 agent 并发改同一子模块 | 方案 B 升级(未来);当前子模块撞车概率低 |

## 8. 关联

- 主 rollout: [`docs/AGENT-ISOLATION-ROLLOUT.md`](AGENT-ISOLATION-ROLLOUT.md) §4 Phase 2 (2a-4)
- 现有机制: `bin/ssot/sync-submodules-push.sh` + `bin/ssot/submodule-reachability-gate.py`
- 记忆: `scripts-submodule-bump`(子模块 bump 陷阱)
