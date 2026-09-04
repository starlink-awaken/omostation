---
lifecycle: history
owner: governance-team
last_updated: 2026-08-09
title: BET-Y1Q1-T1-02 复盘
type: retro
---
# BET-Y1Q1-T1-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 3 days。随 #1233 一次提交落地（含 gap-clearance），实际 1-2 天，未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| git status --short 无 M/m 子模块条目 | ✅ 存量清零后通过 |
| 每个子模块本地 HEAD == 根仓 gitlink SHA | ✅ |
| 18 个 rewind 存量清零, CR-SUBMODULE-REWIND 干净通过 | ✅ |
| CI 增加 submodule-pointer-drift 门禁, 漂移则失败 | ✅ check-submodule-pointer-drift + CI 接线 |
| 新门禁上线规程: 存量未清零前只能 warning 上线 | ✅ 本 bet 即按此规程落地 |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **E5 门禁先于存量清理 = 主干锁死**: 702e5ee71 落地 CR-SUBMODULE-REWIND 后立刻检出 18 个子模块指针回退，与本次变更无关的提交也被拦，主干进入「任何人提交不了」状态。顺序应反: 先清存量、后上 fail 门禁。
2. **18 个 rewind 根因是 PASW 覆盖缺口**（ADR-0371 只隔离 3 个子模块），与并发 agent 行为同源，不是子模块本身漂移。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增:
- check-submodule-pointer-drift（子模块指针漂移检测）
- .github/workflows 门禁接线
- AGENTS.md §6.1 worktree 常见踩坑诊断表
- ADR-0380（submodule rewind 门禁）

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **新门禁三段式**: shadow（只记录 1 周）→ warning（给清理期限）→ fail（存量清零后）。跳过前两段直接 fail 会锁死主干（E5 实证）。
2. 子模块指针漂移用 `bin/ssot/submodule-pointer-transaction.sh` 提交，避免手工 update-index 拷贝短 hash。
3. CR-SUBMODULE-REWIND 在 submodule-freshness-gatekeeper.yml 执行。
