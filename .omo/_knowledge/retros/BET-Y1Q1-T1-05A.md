# Retro — BET-Y1Q1-T1-05A 共享运行时协调层 (shadow)

> 状态: shadow 窗口进行中 (窗口起点 2026-08-14T12:56:00Z, 7d)
> 本文档随窗口收口补全; Q3/Q5 留 warning/fail 阶段接手 agent.

## Q1 实际耗时 vs appetite？

- appetite 2 weeks = 实现 ≤3d + shadow 窗口 7d (grill Q5 裁定)
- 实现: 2026-08-14 一天内完成 (store + 5 挂点 + 测试 + 文档 + 台账)
- 窗口: 2026-08-14 → 2026-08-21 (跑满后由 human_gate 确认置 done)
- **待窗口收口回填**

## Q2 done_when 是否全部通过？

| 条目 | 状态 | 证据 |
|------|------|------|
| 共享 SQLite WAL 四表 | ✅ | ensure_ready 懒初始化 + user_version=1 |
| 原子认领并发测试 | ✅ | 20/20 rounds exactly one winner |
| 心跳 5min + fencing token | ✅ | agent-tick --once 落 6 agent; fencing suite PASS |
| token-check in submit | ✅ | claim 文件持久化 coordination_token; exit 2 fail-closed |
| status CLI 三段可读 | ✅ | 人类可读 + --json |
| 双写 acquire/release 对称 | ✅ | E2E 冷启动验证 |
| 备份双层 + runbook | ✅ | crontab 条目 + maybe_backup 时间戳兜底 + 恢复演练 ok |
| shadow 窗口跑满 | ⏳ | 窗口结束用 status --json 导出快照贴此处 |

## Q3 过程中发现的与 plan 不符的事实？

1. **台账存量 25 个 lint error** (T6-06~10 缺字段 + T6-04 dict) — 与本 bet 无关,
   留给人类决定归属 (不在本 bet write_surfaces 语义内修复).
2. **agent-claim 需要 affected-hash** — claim-check 输出的流程没提, 实际
   `agent-workflow.py claim` 强制要求 (affected-graph.py 计算), AGENT-BRIEF §2.4
   与实际行为有一步未文档化的 gap.
3. **engineering-agent 无权跑 governance-state-mutation** — 必须 governance-agent,
   AGENT-BRIEF 的 claim-check 输出 profile 提示与 profile 实际权限矩阵不一致.
4. **token 写死 0 的自纠** — 初版 submit 挂点用 `--token 0` 会让每次 submit 误报
   stale; 改为 claim 文件持久化 `coordination_token` 字段, submit 读文件.

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？

- 新增: coordination_store.py (~430 行) + test_coordination_layer.py (~160 行)
  + 缺口报告 + runbook + retro (本文件)
- 修改: swarm_discipline.py (+~60 行) + swarm-discipline-cli.py (+~110 行)
  + agent-tick-daemon.py (+~28 行) + gac-worktree.sh (+~20 行)
  + swarm-coordination.yaml (+24 行) + 3y-bet-ledger.yaml (+~90 行)
- **净增**: 文件 +5, 行数 ~860 (shadow 阶段换掉的是未来 D2/D3/D5 退役时的
  删除面, 见 T1-05 done_when "表面积净减" 条目 — 本 bet 是先增后减的前置)
- GaC 规则: 0 新增 (未加 governance-checks) · ADR: 0 (bet 条目即决策记录)

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. **warning/fail 阶段翻开关的位置**: `gac-worktree.sh` submit 段 (token-check
   exit 1) + `swarm_discipline.py::_shadow_mirror_claim` (失败改拒绝) +
   `swarm-discipline-cli.py::cmd_token_check` (shadow 注释处).
2. **messages 表已建未接流** — a2a-adapter 双写是 warning 阶段第一件事.
3. **跨机协调是 non_goal** — 访问层 coordination_store.py 单点封装就是为
   daemon 化预留的, 未来替换 `_connect()` 为 socket 客户端即可.
4. **真实共享 DB 已在跑** — `~/agents/_shared/runtime/coordination.sqlite3`,
   launchd tick 每 5min 自动心跳; 观察: `swarm-discipline-cli.py status`.
5. **crontab 日备需人工装载** — 条目在 runbook §4, 机器本地配置不进 git.

## Shadow 窗口收口快照 (待窗口跑满后填)

```
# python3 bin/gac/swarm-discipline-cli.py status --json 的导出贴这里
```
