---
schema_version: specification/v1
spec_version: 1.0.0
title: Git 子模块稳定性与 remote 配置完整性防护设计
bet_id: BET-Y1Q4-T10-161
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-12
value_indicator_policy: false
---

# T10-161 — Gitlink Freshness & Remote Integrity Guard 设计

## 1. 实证问题（两类事故, 本 workspace 均已发生）

1. **gitlink 陈旧回退**：worktree 创建后子模块未 init / main 前进后未同步,
   agent 在陈旧子模块 HEAD 上工作并把旧 gitlink 提交进主仓——gitlink-ancestry
   hook 以"指针回退"拒绝 push。本 session 实证 2 次 cockpit-ui 指针回退;
   T7-04 交付期间又发生 4 次（family-hub/omo/cockpit-ui/aetherforge 轮番）,
   每次都要人工 fetch+merge 对齐。
2. **remote 配置污染**：主 checkout 的 `origin` URL 被并发会话改写成子仓
   URL（omostation → omostation-cockpit-ui）。此后 `git fetch origin main`
   拉到外来 commit、`git show origin/main:<path>` 对一切路径报不存在——
   所有基于 origin/main 的验证静默失效（T8-24D 收账排查耗时 ~2h）。
   现有工具链无任何检查覆盖此类污染。

## 2. 现状缺口

- `gac-worktree.sh claim` 已有全量 submodule init（PASW），但
  `SKIP_SUBMODULE_INIT=1` 快速路径完全跳过且无补偿检查。
- `.githooks/post-checkout` 只做分支命名合规委托, 不检查子模块新鲜度
  与 remote 完整性——`git worktree add` 绕过 claim 脚本时零防护。
- remote URL 与 `.gitmodules` 的偏离无人观测。

## 3. 设计

### 3.1 post-checkout 内联守卫（`.githooks/post-checkout`）

在既有 hook-runner 委托**之前**追加自包含守卫（不新增文件, 遵守写面约束）：

- **gitlink 新鲜度**：`git submodule status` 找出 `+`/`-` 前缀条目
  （checkout 的 pin ≠ 子模块工作树 HEAD / 未 init）。对本地已含 pin 对象的
  子模块执行 `git submodule update --no-fetch <path>` 原地修复（纯工作树
  对齐, 不改根指针——circuit breaker 安全）; 本地缺对象时打印精确修复命令。
- **remote 完整性**：解析 `.gitmodules` 得到各子模块规范 URL; 检查主仓
  各 remote URL 是否落入"子仓 URL 集合"（污染特征）。命中只告警 +
  打印修复命令, **绝不改写 URL**（non_goals）。
- 守卫恒 exit 0（advisory, 不阻断任何 checkout 流程）; 环境变量
  `GAC_SKIP_POST_CHEKOUT_GUARD=1` 可跳过（供测试/特殊流程）。
- 子模块内部 checkout 时无 `.gitmodules` 上下文, 直接跳过（幂等安全）。

### 3.2 claim 快速路径补偿（`bin/gac/gac-worktree.sh`）

`SKIP_SUBMODULE_INIT=1` 分支追加同样的两项检查（告警 + 修复命令提示）;
正常路径在 init 完成后追加 remote 完整性检查（一次性, 成本可忽略）。

### 3.3 协议固化（`AGENTS.md` §6）

新增一小节: worktree 子模块与 remote 完整性协议——守卫行为说明、
两类污染的判定特征与手工修复命令（`git submodule update --init <sub>` /
`git remote set-url origin <主仓>`）。

## 4. 完成判据映射

| done_when | 落点 |
|---|---|
| root aetherforge gitlink = 79842ed0… | 已由 #3664 满足, 本 PR 内核验记录 |
| SHA 在 omostation-aetherforge origin/main 可达 | PR 内 merge-base 核验 |
| gates 在指针 bump PR 上通过 | 本 PR CI + 本地 gac-local-gate 实测 |

## 5. 风险与回滚

- 守卫恒 exit 0, 最坏情况是多两行输出——不阻断任何现有流程。
- 不新增文件、不改 remote、不动根指针; 回滚 = revert 单 PR。
- hook 每次额外开销目标 < 300ms（submodule status + config 读取, 无网络）。
