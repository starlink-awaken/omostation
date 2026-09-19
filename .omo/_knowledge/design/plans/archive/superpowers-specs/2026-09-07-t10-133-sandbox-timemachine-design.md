---
schema_version: specification/v1
spec_version: 1.0.0
title: Git Worktree 物理沙箱秒级 CoW 快照克隆与试错安全回滚时光机
bet_id: BET-Y1Q4-T10-133
status: accepted
lifecycle: contract
last-reviewed: 2026-09-07
type: plan
owner: governance-team
last_updated: 2026-09-07
---

# Git Worktree 物理沙箱与时光机回滚规格 (BET-Y1Q4-T10-133)

## 动机

持久化 Agent 执行高危或未知探索任务时，直接在共享主工作区试错会污染他人工作：
- 门禁红灯、冲突 marker、误删文件等异常直接落在共享树上（2026-08-06 实测 HEAD 一小时变四次）
- 现有 `gac-worktree.sh claim` 是**手动**隔离，agent 不会为每次试错 claim/release
- bdsk-shadow-sandbox 是**静态扫描**（只读 diff 分析），不是物理执行沙箱

目标：为持久化 Agent 的高危/未知探索任务提供**秒级建立的隔离 worktree 物理沙箱**，异常时硬性时光机回滚自毁，绝对防止主工作区受污染。

## 变更

1. **`bin/gac/resident-sandbox-timemachine.sh`**（主仓，bash）:
   - `create <session> [--from <commit>]`: 基于 `git worktree add` 从指定 commit（默认当前 HEAD）
     秒级创建隔离沙箱 worktree（`.subtrees/` 之外独立命名 `ws-sandbox-<session>`），
     不碰主工作区文件；创建超时 > 5s 即报环境异常（circuit_breaker）
   - `run <session> -- <cmd...>`: 在沙箱 worktree 内执行命令（cd 沙箱 + 执行）
   - `rollback <session>`: 时光机回滚自毁 — `git worktree remove --force` + 删除沙箱分支
   - `--help`: 用法说明（verify 用）
   - 硬约束: 沙箱内禁止 `git push`/`git merge` 到 main（grep 校验命令串，拦截即 FAIL）
2. **`projects/omo/src/omo/resident/sandbox_driver.py`**（omo 子模块）:
   - `SandboxDriver` 类: `create()` → `run(cmd)` → `outcome()` 三阶段驱动
   - `outcome()`: 收集沙箱内 exit code + 门禁输出，判定 success/failure
   - failure → 自动调用 rollback（时光机自毁）；success → 保留沙箱供复核
   - 挂接 resident execute 通路（`ExecutionRequested` 事件高危任务可走沙箱执行）
3. **`tests/integration/test-sandbox-timemachine.sh`**（主仓集成测试）:
   - 创建沙箱 → 沙箱内制造失败（跑一个必失败命令）→ 断言回滚后主工作区 `git status` 干净
   - 创建沙箱 → 主工作区 git status 不受影响（隔离性断言）
   - `--help` exit 0

## 验收

- `bash bin/gac/resident-sandbox-timemachine.sh --help` → exit 0
- 沙箱创建 < 5s（超时即 circuit_breaker）
- 试错失败回滚后，主工作区 `git status` 干净度 100%
- 沙箱内禁止 push/merge main（违反即拦截）
- `bet-ledger.py lint` → exit 0

## 非目标

- 不允许沙箱绕过 gac-worktree 机制直接写主工作区
- 不在未经验收门禁全绿前将沙箱分支合入 main
- 不做 bdsk 静态扫描的替代（两者正交：静态扫描 + 物理沙箱）

## 风险

- worktree 与子模块交互（PASW 子模块共享）——沙箱用主仓 worktree，子模块指针沿用共享 .subtrees
- 并发 agent 清理 worktree（PASW_TTL）——沙箱命名带 `sandbox-` 前缀，cleanup 豁免需确认
- 失败回滚本身可能失败（worktree 含未提交改动）——rollback 用 `--force` 兜底

## circuit_breaker

沙箱创建超时 > 5s → 阻断试错任务，向指挥舱上报环境异常（不硬扛）。
