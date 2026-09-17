---
id: P106
status: active
lifecycle: pattern
owner: governance-team
created: 2026-09-17
last-reviewed: 2026-09-17
related:
- p96-swarm-shared-state-hygiene.md
- p73-truth-driven-engineering-pattern.md
origin_reports:
- .omo/_knowledge/retros/BET-Y1Q4-T10-146.md
type: ssot
---

# P106: Main-Branch Edit Clobbering by Concurrent Agents

> **2026-09-17 沉淀** · 来源: 本会话 4 次实证（generate-brief.py / Makefile / AGENTS.md 编辑被覆盖 + pattern 文件被 reset 清除）
> 适用: 多 agent 共享主树环境, 任何直接在 main 上的文件编辑

## TL;DR

在裸 main 分支上编辑文件, 并发 agent 的 commit + push 会**静默覆盖**你的未提交改动。你以为自己在改代码, 其实是在跟一群抢座位的人打架。**永远先切分支再编辑**, 哪怕只是一行。

## 陷阱表

| 陷阱 | 症状 | 对策 |
|------|------|------|
| 裸 main 编辑 | 文件改完没 commit, 并发 agent push 新版本, 你的改动消失 | 任何编辑前先 `git checkout -b`, 哪怕只改一行 |
| stash 被覆盖 | stash 后 concurrent agent 提交了新版本, pop 时冲突 | stash 前先 `git fetch`, 检查有没有新提交 |
| 工作树脏了想 reset | `git reset --hard` 被用户/规则拒绝 | 用非破坏性替代: `git stash push` + `git checkout --ours` + `git add` |
| agent-workflow 在脏 main 跑 | `verify --from-diff` 扫到无关文件, 拒绝执行 | 必须在干净分支上跑 workflow |
| reset --hard 被别人跑 | 你 stage 的文件被 concurrent agent 的 `git reset --hard origin/main` 清空 | 切分支后立即 commit, 不要长时间 stage 不提交 |

## 纪律

1. **main 是只读基线**: 主树只用于 `git fetch` + `git pull`, 不用于编辑
2. **编辑 = 切分支**: `git checkout -b agent/<task>-<date>` 是成本最低的安全网
3. **stash 不是长期存储**: stash 前先 fetch, 检查新提交
4. **冲突即信号**: 频繁冲突说明 main 速度快, 小步快提优于大批量
5. **stage 后立即 commit**: 不要长时间把改动留在暂存区, 并发 agent 随时可能 reset

## 实证

本会话 4 次事故:
- generate-brief.py 编辑被覆盖（DECISION_CHECKLIST_PATH 常量删除被回滚）
- Makefile 重复 target 改名被覆盖
- AGENTS.md meta-doctor 命令修正被覆盖
- pattern 新文件被 `git reset --hard origin/main` 清空（stage 后未及时 commit）

## 与 P96 的关系

P96 聚焦**共享状态文件**（system.yaml / BRIEF.md）的读写纪律。
P106 聚焦**任意文件编辑**的文件级并发冲突。两者互补: P96 管"什么文件", P106 管"在哪里编辑"。
