---
lifecycle: history
owner: governance-team
last_updated: 2026-08-09
title: BET-Y1Q1-T7-02 复盘
type: retro
---
# BET-Y1Q1-T7-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 1 week。v10 失落产物重建（journey-runner/scene-card-lifecycle/v2 卡）约 3-4 天，未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| bin/ssot/journey-runner.py 重建且 git tracked | ✅ git ls-files 通过 |
| bin/ssot/scene-card-lifecycle.py 重建且 git tracked | ✅ git ls-files 通过 |
| scene-card v2 schema 与三张卡重建且 git tracked | ✅ docs/scene-cards/ 全部 tracked |
| 全部通过 D0 检查 | ✅ |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **产物丢失根因是并发 git 破坏**: 2026-08-06 `git clean -fd` 删未入库文件、`git reset --hard` 连暂存区一起摧毁、共享分支 rebase 挤出提交（49d3ffed5）→ journey-runner.py(601 行) 等永久丢失。本 bet 是 T1-00 D0 铁律的补建产物侧。
2. **重建不是重写**: 通过 git show 游离提交取回内容（`git show <sha>:<path>`），不是从零重写，保证语义一致。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（重建 + 入库）:
- bin/ssot/journey-runner.py (~600 行, 四面一脊执行引擎)
- bin/ssot/scene-card-lifecycle.py
- docs/scene-cards/ v2 卡片
- 无新增 GaC 规则

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. 交付物必须入库 + tag（D0 铁律），否则 git clean/reset/rebase 可永久销毁。
2. 丢失产物优先 `git show <sha>:<path>` 从游离提交取回，而非重写（保语义）。
3. journey-runner.py 是执行脊柱：scene-card 校验 → journey 状态机 → signal 轮询 → outcome 记录闭环。
