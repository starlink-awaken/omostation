---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-26
---

# 多 Agent 共享工作区协作标准 (Multi-Agent Worktree Collaboration)

> 源自 omlxc 运维提案 v0.1 (2026-08-25/26 四起互踩事故实证) 收编,
> 经 PR #2208-#2253 系列实战验证后升格为正式标准。事故数据与
> 完整验尸见 omlxc `docs/operations/2026-08-26-multi-agent-collaboration-protocol-proposal.md`。

## 问题

多个 agent (Claude/Codex/自动化) 共享同一主 worktree 时, 三类互踩事故
实测造成 ~15-20% 工时损耗:
- **checkout 拖回**: 主 worktree HEAD 被切到旧提交, 当日提交被绕过 (4 起)
- **文件回写拉锯**: 双方互覆写同一文件, staged 内容也会被冲 (3 起)
- **分支漂移断档**: 运行时脚本文件消失, 常驻任务空转 (mail-daemon 8h 实锤)

## 契约

### 1. 共享区改动一律 worktree 隔离 (硬规则)

凡对 `bin/`, `docs/`, `.omo/` 等共享可变区的修改, **禁止**在主 worktree
直接编辑提交, 必须走四步流程:

```bash
# ① 隔离建区 (基于最新 origin/main)
git fetch origin main && git worktree add .claude/worktrees/<name> -b <branch> origin/main
# ② 区内改 + commit + 验证 (并行 agent 物理隔离)
# ③ push + PR + merge (远端 main 为正朔)
# ④ 主区磁盘同步(运行时生效) + 稳定副本同步 + worktree 清理
```

实证: 2026-08-25 当日 bin/ssot 三脚本+spec+7卡被整体回冲(staged 亦失守),
原地重打 2 轮失败; 切 worktree 后一次通过 (PR #2209 起全程零拉锯)。

### 2. 常驻运行时与工作区解耦

一切 launchd/cron 常驻任务**不得**直接指向共享主 worktree 内文件,
必须指向稳定副本 (`runtime/ssot-stable/`) 或安装产物 (uv tools)。
同步纪律: 变更里程碑后跑 `bash runtime/ssot-stable/sync-stable.sh`。

### 3. 防线体系 (六道, 全部已落地)

| 防线 | 载体 | 实战战果 |
|---|---|---|
| worktree 隔离 | 本标准 §1 四步流程 | PR #2209+ 零拉锯 |
| 正朔裁决 | 远端 main PR 流 | 11 PR 合并零丢失 |
| checkout 哨兵 | watchdog detached HEAD 5min 巡检 | 第四次互踩全程告警, 10min 复原 |
| 运行时固化 | runtime/ssot-stable + sync 脚本(11 文件清单) | 断档未复发 |
| git 身份 | 全局身份修复 + per-commit 标识 | test@test 污染止损(108 commit) |
| 产出断言 | mail-daemon 零产出告警 / probe streak | 探测病 15min 内可发现 |

### 4. Agent 身份标识

并行 agent 提交需可追溯: 会话固定 identity 或 per-commit
`git -c user.name="xxx-agent"`; **禁止**改全局/仓库级 config 冒充他人。

## 未裁决项 (悬置)

- **活跃区登记**(提案条款 A): mtime 冲突检测或 .omo/state/ owner 登记 —
  违规成本为零依赖自觉, 待更高频协作场景出现再裁决。

## 违例处置

发现互踩事故: ① watchdog 告警为第一响应 ② `git checkout main` 复原
(main 从未被移动, 零丢失) ③ 事故入 omlxc ops 文档 ④ 本标准迭代。
