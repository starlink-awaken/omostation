---
lifecycle: history
owner: governance-team
last_updated: 2026-08-09
title: BET-Y1Q1-T1-00 复盘
type: retro
---
# BET-Y1Q1-T1-00 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 2 days。从 2026-08-06 实测损失到 08-07 落地共享主树只读 + PASW 强制，约 2 天，未超出。
主要耗时在 6 个 evidence（E1/E2/E4/E6/E16/E17）的归因确认，其中 E16（sandbox 无删除权限）推翻了 E1 的部分结论。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| 所有 agent 在 gac-worktree claim 出的隔离树内工作, 共享 main 树只读 | ✅ gac-worktree claim + branch protection (AGENTS.md §6.1) |
| git clean / reset --hard / stash -u 在 hook 层要求 SWARM_ESCAPE_ID | ✅ T1-07 PATH shim 强制收口 |
| AGENTS.md 记录"共享主树只读"红线 | ✅ AGENTS.md §1.6.2 |
| claim 写锁改为原子或失败回滚 | ✅ lock file 原子写 |
| 锁文件记录 last_heartbeat, 提供 stale-lock 检测与一键清理 | ✅ agent-workflow prune-locks |
| claim 被拒报错区分活锁/僵尸锁 | ✅ |
| raw git commit/push --no-verify 被 hook 层拦截 | ✅ git-shim 拦截 |
| 共享分支 rewrite 前检查丢弃他人提交 / 禁止共享分支 rebase/reset | ✅ main branch protection + worktree PR 流程 |
| D0 铁律: commit 后须打 tag 或推独立分支 | ✅ AGENTS.md §1.6.2 D0 铁律 |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **E16 归因错误**: 2026-08-06 全天把 sandbox 无删除权限导致的僵尸 index.lock 误判为「并发 agent 删文件」，据此写了 E1 部分结论。D0 三段式仍成立（E6 独立支持），但「文件被清理 4 次」中至少 2 次实为本因。
2. **E17 CI 内联脚本盲区**: `.github/workflows/agora-ci.yml` 两侧语法合法但一侧跑不了（多行缩进 python 的 IndentationError），yamllint 全过。语法检查验「能否解析」不是「能否跑」。
3. **E6 commit 非持久化**: 49d3ffed5 提交成功后因共享分支被 rebase 脱离历史，工作树内容消失。commit 只是「暂时安全」。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增:
- AGENTS.md §1.6.2 D0 铁律 + 逃生口机制
- gac-worktree.sh / git-shim / swarm-git 强制 wrapper
- 无新增 GaC 规则；ADR-0371/0380/0387 相关

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **逃生口唯一入口**: `SWARM_ESCAPE_ID=<白名单id> bin/gac/swarm-git ...`。raw `git --no-verify` 被 PATH shim 拦截。
2. **工具能力边界会伪装成环境问题**: agent 报告「环境有并发干扰」时，先验证自己工具链在该环境下的完整性（E16）。
3. **D0 持久化下限**: 交付物必须 git add → commit → tag（或独立远端分支），仅 commit 不算。
4. **内联脚本必须真执行验证**: YAML 合法 ≠ 脚本能跑（E17）。
