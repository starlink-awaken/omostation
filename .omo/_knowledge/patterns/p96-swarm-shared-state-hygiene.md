---
id: P96
lifecycle: pattern
owner: governance-team
created: 2026-08-31
last_updated: 2026-08-31
related:
- ADR-0443
- CR-GIT-STAGE-SUBMODULE-PIN
origin_reports:
- docs/reports/2026-08-31-swarm-collaboration-retro.md
---

# P96: 多 agent 共享状态卫生（swarm shared-state hygiene）

## 陷阱表

| 陷阱 | 症状 | 对策 |
|------|------|------|
| 主树当工作台 | 分支被并行 agent 接管、index 混入他人 staged | 主树只读纪律：工作一律在专属 worktree；主树仅基线同步与运行时区 |
| add -A 全收 | 子仓 side-branch 指针混入 commit | CR-GIT-STAGE-SUBMODULE-PIN（add 具体路径 + 前置 `git diff --cached --submodule=short` 自检）|
| PR-分支连坐 | 关 PR 时分支被删，reopen 不可行、重建无 diff | 交付确认以 main 内容为准（`rg` 特征串验证），不以 PR 状态为准 |
| 全局 validate 卡人 | 他人未登记脚本阻塞我的 push | 顺手代登记（元数据占位，owner 后调）；根治靠 per-diff 模式（v8）|
| 基线手工漂移 | quota 基线落后活跃数反复报错 | 严格执行 SCRIPT-BASELINE-SYNC：登记与 bump 同一 commit |

## 纪律

1. **push 前在干净 worktree**：共享 index 下 pre-push staged 检查会被人卡——推送动作只在专属 worktree 执行。
2. **交付验证看 main**：PR MERGED、CLOSED、直推——三种终态都存在；唯一可信是 `git show origin/main:<file>` 内容特征验证。
3. **冲突即信号**：CONFLICTING 高频出现说明 main 速度超过你的分支年龄——小步快提（单事务单 PR）优于大批量。
4. **并行 agent 的产物是环境的一部分**：主树 staged/未跟踪文件不删不 restore，绕行（换 worktree）而非清理。

## 实证

六轮迭代 14 起事故全清单见 origin_reports。A 类（共享可变状态）占 6 起/最大损耗；
三层 gate（submodule-guard/pointer-drift/ancestry）拦下全部指针事故零污染——
**防护体系有效，但每次拦截都有 ~5min 处理成本，卫生习惯（本 pattern）才是零成本方案**。

## 反模式

- "被 gate 拦住就是 gate 的错"（gate 拦的是状态泄漏，状态卫生才是根因）
- 清理并行 agent 的文件求"干净"（破坏他人工作树=制造新事故）
- PR 状态当交付真相（多 agent 环境终态不唯一）
