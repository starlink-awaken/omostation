---
schema: md/v1
status: completed
lifecycle: evidence
owner: laowang
last-reviewed: 2026-11-25
type: report
bet_id: BET-Y2Q4-T10-353
title: BET-Y2Q4-T10-353 closeout 回执 — done_when 在干净 worktree 实测
---

# BET-Y2Q4-T10-353 closeout 回执

生成时间：2026-11-25T09:55Z（UTC），在干净 worktree
`/Users/xiamingxing/ws-bet-t352-t353-done-transition`（base = origin/main@ae3e6aac58）
内实测；未复用 PR #5562 合并时的读数。

## 结论

本 BET 工程范围已由 squash 提交 `ae3e6aac58fbfacf7d0f71087de7029595b23839`
（PR #5562）合入 main。本回执只做 done-transition 复核，不改判定面代码。

## done_when 逐条实测

| 条款 | 命令 | 实测读数 | 判定 |
|---|---|---|---|
| services.yaml 8 服务 environment 块含 PATH, resident 6 服务含 outputs | `rg -n "PATH: /Users/xiamingxing/.local/bin" .omo/_truth/registry/services.yaml` + `rg -c "stdout: /Users/xiamingxing/.local/log/omostation/com.l4"` | 回填 8 处 PATH 在位（resident 6: L683/714/789/819/849/879 + zhixing L6119 + agent-brief L6524；另 L6305 为本 BET 之前既有的他服务 PATH，非本 BET 面）+ 6 处 resident outputs | 达成 |
| gen-service-configs.py --check 报 0 drift (78 launchd services) | `uv run --with pyyaml python bin/mof/gen-service-configs.py --check` | `✅ 0 drift (78 launchd services)` | 达成 |

## 授权依据

Principal 2026-11-25 会话原话「go」——8 服务镜像回填正式化。

## 回滚

revert squash 提交 `ae3e6aac58` 即可——纯声明回填 34 行，无运行时写面，
无数据迁移。

## 诚实边界

- 安装器 PATH 注入源头与声明生成器不同源（non_goals 留债）：本机安装平面
  重装可能再现 drift——语义对比的设计意图是如实报警，非误报。
- 治理占比 42.1%>40% 为 30d 滚动统计预存基线，waiver 见
  `.omo/_truth/governance-evidence/waiver-2026-11-25-t353-ratio.md`（PR #5562）。
