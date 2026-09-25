---
schema: session-retro/v1
status: final
owner: main-session-agent
date: 2026-09-25
type: closeout
scope: scripts-repo cleanup + dashboard + CI 全链路 + 架构审视
---

# 2026-09-25 主仓清理与会话收口复盘

## 1. 本轮交付（已合并/落地）

| PR / 动作 | 结果 | 合并 commit |
|-----------|------|------------|
| PR #4308 feat(panorama): Bento Grid + dashboard skills + workflow | 合并 | `24abb5482` |
| PR #4330 fix(tests): clone-lifecycle hermetic 6 测试 | 合并 | `7444a2d18` |
| 分支卫生：9,606 误跟踪文件退跟踪（.kilo/node_modules, .ruff_cache, .omc, wip-snapshots, kairon/.venv, __pycache__） | 直接合入 #4308 | — |
| BET 门禁修复：7 spec frontmatter 契约 + meta.total_bets 471 对齐 + T10-TOOLING track | 合入 #4330 | — |
| capability-registry 全子模块口径（tools 293→566→643） | 合入 #4308 后续 push | — |
| aetherforge DIVERGED 回退 c1d2f585→6d8d7caf（对齐 origin/main） | 合入 #4308 | — |
| aetherforge PR #83 关闭 | 已关闭 | — |
| 43910 sunset：旧 panorama-dashboard 移除，sunset-redirector 部署 + launchd 持久化 | 本地落地 | — |
| domain-kems 确认为废弃 | 调查结论 | — |
| 共享树 main 同步 origin/main | HEAD=7444a2d18 | — |

## 2. 关键决策

- **junk 回流防护**：并发 agent (Kilo) 在共享树二次 merge 时把全部 junk 重新提交（ab77c84b8）。直接合并会回流 5,322 文件。改用隔离 worktree cherry-pick 到远端最新基底，junk 零回流。
- **sunset-redirector 分端口**：默认监听 43910（旧 Panorama 静态），非 43191。43191 是新的知行 dashboard，不在 sunset 范围。
- **aetherforge alias 修复不入主仓**：c1d2f58 未合入子仓 origin/main，主仓指针回退对齐；修复经子仓自身 PR 落地后由 auto-bump 带入。

## 3. 踩坑（不再踩）

### 3.1 并发 agent 共享分支推拉冲突
- **现象**：同一分支被多个 agent 交替 push/重放，每次 push 被拒（non-fast-forward），需反复 fetch + 合并。
- **解法**：争议改动在隔离 worktree 完成，cherry-pick 到远端最新 tip 后 push。不要在原共享分支上直接 merge 对方的重放提交。
- **固定**：见 §4 AGENTS.md 更新。

### 3.2 生成物口径 CI ≠ 本地
- **现象**：`gen-capability-registry.py --check` 本地通过但 CI 漂移。根因：本地 worktree 只 init 了 6 个相关子模块，CI 递归检出全部，11 个 kairon 包 MCP server exists 标记不同。
- **解法**：对 CI 生成物用 `git clone --recurse-submodule` 做 fresh 复刻验证，确认双环境逐字节一致后再 push。
- **固定**：见 §4 AGENTS.md 更新。

### 3.3 hermetic 测试泄漏 host 状态
- **现象**：开发机 authority broker 进入 shadow-active 后，6 个 clone-lifecycle 测试从绿变红（subprocess 调用真实 broker / 读取真实 store）。CI 无此 store 故绿，属环境类假绿。
- **解法**：testability seam —— agent-clone.py 认 `CLAIMS_AUTHORITY_HERMETIC_UNACTIVATED=1`，autouse fixture 钉 activation_mode=unactivated + 设同名 env。生产路径零变更，shadow-active 语义的测试仍显式自行 patch。
- **固定**：PR #4330 已合入 main。

### 3.4 submodule 指针不能直接 amend
- **现象**：尝试 `git commit --amend` 修复 submodule 指针回退时报 "is in submodule"。
- **解法**：在主仓 reset/checkout 子模块指针后 `git add <submodule>` 再 commit；子模块内部改动走子模块自己的 commit → push → 主仓指针 bump 三步走。

## 4. 固化到 AGENTS.md / 协议层

- 新增「生成物 CI 口径」指引：所有生成物（registry / drift / ledger）的 `--check` 验证必须在完整子模块复刻环境下通过。
- 新增「并发分支隔离」指引：多 agent 同时操作同一分支时，用隔离 worktree 做干净室合并，禁止在原共享分支上 merge 对方的重放提交。
- 新增「hermetic 测试」指引：fixture 测试不得依赖 host 运行时状态（broker/store/网络），必须通过 env seam 切断。

## 5. 遗留（非阻塞）

- `DEBT-20260925-SEDIMENT-TRACKED`：`.omo/debt` 下 1,447 个历史快照仍被跟踪，debt-guard 禁止 git 级删除，待 omo debt 通道处理。
- aetherforge alias 修复（c1d2f58）待子仓 PR 合入后由 auto-bump 带入主仓。
- Dashboard 深度审计（渲染异常 / 数据缺失 / persona-guidance-bar / 可视化易读性）—— 本轮主线但未完成，作为下一阶段入口。

## 6. 一句话总结

> 生成物要在 CI 口径复刻验证；并发分支用隔离 worktree 干净室合并；hermetic 测试必须切断 host 状态。
