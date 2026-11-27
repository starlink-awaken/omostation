---
schema: md/v1
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-11-27
type: ssot
title: T10-356/357 cron 首跑 canary 回执 —— 断根模式首夜双绿 + T356/357 done-transition 入账
bet_id: BET-Y2Q4-T10-360
created: 2026-11-27
---

# cron 首跑 canary 回执 (2026-11-27)

> T356 (PR #5622) 与 T357 (PR #5625) 把 capability-registry-sync-daily 与
> mcptool-drift-report-daily 从主仓直提改为「worktree + 自动 PR」模式。
> 交付时 operational 轴诚实停在 NOT_PROVEN (done 门要求 canary), 本回执
> 为首夜 (2026-11-27) 实测记录 —— done_when 最后一条「首跑 canary 通过」
> 的入账凭据。

## 1. 首跑实测 (全部 2026-11-27 晨实测)

| job | 首跑时刻 | 日志终态 | 主仓工作区 |
|---|---|---|---|
| capability-registry-sync-daily (04:05) | mtime 04:06:22 | `✅ 产物无漂移, 跳过发布 (2026-11-27)` | 零污染 (生成文件面无 M) |
| mcptool-drift-report-daily (05:45) | mtime 05:46:36 | `✅ 产物无漂移, 跳过发布 (2026-11-27)` | 零污染 |

判据说明: 两 job 均走 `--publish` 新链 (临时 worktree 生成 → 无漂移即弃),
**主仓工作区零接触** —— `git status` 生成文件面 (docs/generated/
capability-registry.yaml, docs/INDEX-MCP.md, docs/CLI-REFERENCE.md,
mcptool-drift-report.yaml) 无任何 M。这是断根的核心承诺: 旧直提链在该
场景会在主仓留 commit, push 失败即分叉 (11-26 事故形态)。

mcptool 日志中 7 条 `[report] 无变化` 是 worktree 内 `--report` 跑探针的
正常输出 (cmd_nonzero_ok 语义, T357 设计), 非错误。

## 2. fullrefresh 活性 (复活后跨夜续跑)

`.fullrefresh.lock` 服务 2026-11-26 复活 (T359) 后持续运行:
2026-11-27T00:14:41Z `publish_ok` (23.4s) —— 复活次日仍按 180s 周期打点,
无锁竞争 / revision 抖动 (circuit_breaker 未触发)。

## 3. done_when 复测结论

| BET | done_when | 本次实测 |
|---|---|---|
| T10-356 | cron 首跑 canary 通过 | ✅ 04:06 首跑绿, 零污染 |
| T10-356 | crontab 新链装载且旧直提行消亡 | ✅ 昨日 T356 收尾实测 (crontab 唯一新链) |
| T10-357 | mcptool 05:45 首跑 canary 通过 | ✅ 05:46 首跑绿, 零污染 |
| T10-357 | crontab 装载 + 旧直提行被签名替换 | ✅ 昨日 T357 收尾实测 (装重判例) |

operational 四证 (两 BET 同源, 本回执):
- live_canary: 首跑日志终态原文 (本回执 §1)
- fresh_receipt: 首跑时刻 mtime (04:06:22 / 05:46:36) 即新鲜回执
- replay: 首跑 = 新链在真实 cron 环境的重放 (launchd/cron 实环境)
- cleanup: 无漂移即弃路径实测走通 (worktree 自清理, 残留=0 昨日实测)
