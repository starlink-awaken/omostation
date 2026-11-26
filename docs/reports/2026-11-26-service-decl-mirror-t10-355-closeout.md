---
type: report
bet_id: BET-Y2Q4-T10-355
schema_version: closeout-receipt/v1
created: 2026-11-26
last-reviewed: 2026-11-26
lifecycle: history
owner: engineering-agent
---

# Closeout 回执 — BET-Y2Q4-T10-355

refresh 服务声明镜像回填（services.yaml ↔ 实测 plist）+ capability-sync 主仓直提债立案。

**读数前置条件**：本回执全部命令在**干净 worktree** `/Users/xiamingxing/ws-t10355`（基线 `2b1cfc577`，`origin/main` 落后 0）内执行；规范主检出 `~/Workspace` 未同步（其 `projects/omo` pin 仍为旧值），属 principal 动作，本 BET 不动主检出。

## diff

工程腿随 PR #5620 落 main，squash commit `7cc33c14e205abd3ad4c8d20763117c438b9638e`（`git merge-base --is-ancestor` 对 `origin/main` 为真）。

```
.omo/_knowledge/retros/BET-Y2Q4-T10-355.md         | 61 +++++++++++++++
.omo/_truth/governance-evidence/waiver-2026-11-26-t355-ratio.md | 39 +++++++++
.omo/_truth/registry/debt.yaml                     |  1 +
.omo/_truth/registry/services.yaml                 | 12 ++--
.omo/debt/items/CRON-CAPABILITY-SYNC-MAIN-DIRECT-COMMIT.yaml | 55 +++++++++
docs/plans/3y-bet-ledger.yaml                      | 54 ++++++++++-
docs/superpowers/specs/2026-11-26-refresh-decl-mirror-bet-t10-355.md | 70 +++++++++
```

声明侧改动集中在 `omostation.zhixing-dashboard-refresh` 一个服务块的 `program.args` 与 `outputs` 两处，其余为债条目与台账绑定。

## 受控测试

### 判据 1 — 声明 vs 实测 plist 逐字段一致（done_when #1）

实测源：`plutil -p ~/Library/LaunchAgents/com.omostation.zhixing-dashboard-refresh.plist`

| 字段 | plist 实测值 | services.yaml 声明值 | 一致 |
|---|---|---|---|
| `ProgramArguments[0]` | `/opt/homebrew/bin/python3` | `program.interpreter: /opt/homebrew/bin/python3` | ✅ |
| `ProgramArguments[1]` | `-B` | `program.entrypoint: -B` | ✅ |
| `ProgramArguments[2]` | `/Users/xiamingxing/.local/share/zhixing-dashboard/current/orchestrator.py` | `program.args[0]: …/current/orchestrator.py` | ✅ |
| `StandardOutPath` | `/Users/xiamingxing/.local/log/com.omostation.zhixing-dashboard-refresh.out.log` | `outputs.stdout: 同值` | ✅ |
| `StandardErrorPath` | `/Users/xiamingxing/.local/log/com.omostation.zhixing-dashboard-refresh.err.log` | `outputs.stderr: 同值` | ✅ |
| `RunAtLoad` | `true` | `run_at_load: true` | ✅ |
| `Label` | `com.omostation.zhixing-dashboard-refresh` | `label: 同值` | ✅ |
| `StartInterval` | `300` | `scheduler: launchd` / `trigger: interval`（间隔由 plist 承载，未在声明面重复） | ✅ |

修正前两处过期：① `program.args` 指向宿主根孤儿 `orchestrator.py`（19294B，10-08 后未更新），实际执行 `current/orchestrator.py`（42340B release 真身）；② `outputs` 指向 10 月初停更的 `launchd-refresh.log`，实际已搬至 `~/.local/log/` 且 out/err 分离。**「日志断流 8 周」是声明视角假象，服务全程健康**（见 operational 轴 live_canary）。

### 判据 2 — 生成器自证（done_when #2）

```
$ uv run --with pyyaml python bin/mof/gen-service-configs.py --validate
{
  "ok": true,
  "violation_count": 0,
  "violations": []
}

$ uv run --with pyyaml python bin/mof/gen-service-configs.py --check
✅ 0 drift (78 launchd services)
```

### 判据 3 — 债闭环节律（done_when #3）

```
$ python3 bin/gac/check-debt-closure-discipline.py
  gate_level 分布: {'none': 113, 'watchlist': 13, 'gate': 2}
✅ 债务闭环节律合规 (扫描 136 项, 终态 93)
```

无新红。债条目 `CRON-CAPABILITY-SYNC-MAIN-DIRECT-COMMIT` 随 #5620 落盘，指向「主仓直提设计不修则每天复发」的结构病（2026-11-26 当日 cron 失败滞留曾造成主仓 main 分叉 31 提交，已现场处置：tag 存档 + soft reset 对齐）。

## operational-轴

**live_canary**：服务在跑且日志持续写入，非声明视角推断——

```
out.log mtime=Nov 26 20:28:38 2026 size=622383
err.log mtime=Nov 26 20:28:38 2026 size=2034916
取样时刻=2026-11-26T12:29:20Z（= 本机 20:29:20）
err 尾两行:
  2026-11-26 20:28:38,428 WARNING Schema validation warnings: ['documents: expected dict, got list']
  2026-11-26 20:28:38,795 INFO Refresh complete in 23.6s with 30 sources
```

最近一次 refresh 完成于取样前 42 秒，30 个源、failed=0，输出路径与声明的 `outputs.stdout/stderr` 逐字相同 → 声明面与运行面同源可证。

**fresh_receipt**：本文件即回执本体（判据 1/2/3 的命令原始输出在上方，未做任何剪裁改写）。

**cleanup**：本 BET 未产生临时态——只改两份已跟踪声明文件 + 落一个债条目；无 worktree 残留、无 launchd 改写（本机 plist 由宿主维护，`generate: false`，声明侧只做镜像）、无后台进程遗留。

## rollback

- **声明侧回滚**：`git revert 7cc33c14e205abd3ad4c8d20763117c438b9638e`（或将 `omostation.zhixing-dashboard-refresh` 块的 `program.args` / `outputs` 还原为旧值两行）即可完全复原；该块由 `gen-service-configs.py --check` 覆盖，回滚后需重跑 `--check` 确认 drift 回到基线。
- **债条目侧**：回滚即删除 `.omo/debt/items/CRON-CAPABILITY-SYNC-MAIN-DIRECT-COMMIT.yaml` 与 `.omo/_truth/registry/debt.yaml` 对应行（登记面随 #5620 一并回退）。
- **回滚不触碰运行面**：plist 与 launchd 状态未被本 BET 改动，回滚声明不会导致服务断流。

## 未执行动作 / 边界

- 未清理宿主根孤儿 `orchestrator.py` 残骸（部署根文件，属 dashboard 运维面，non_goals 明列）。
- 未改 ADR-0373 sentinel 设计（1970 时间戳为有意设计，生成器自证）。
- 未把 cron 直提重构为 worktree PR 模式（已立债留后续）。
- 未动 `~/Workspace` 规范主检出（其 `projects/omo` pin 仍为旧值；本回执读数面为隔离 worktree）。
