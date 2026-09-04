---
status: retired
lifecycle: contract
owner: governance-team
last_updated: 2026-08-20
title: Coordination Layer Recovery Runbook — BET-Y1Q1-T1-05A
type: doc
---
# Coordination Layer Recovery Runbook — BET-Y1Q1-T1-05A

> 适用对象: 共享运行时协调层 `~/agents/_shared/runtime/coordination.sqlite3`
> 状态: **退役** (BET-Y1Q3-T1-08, 2026-08-20) — 独立部署 clone 已退役, 备份与 daemon 全部改指权威 Workspace
> Owner: BET-Y1Q1-T1-05A · 详细分析: `docs/reports/2026-08-14-shared-runtime-coordination-gap.md`

## 1. 这层挂了会发生什么 (shadow 阶段)

| 组件 | 失效症状 | 影响 |
|------|---------|------|
| branch-claim 双写 | stderr 打 `[swarm-shadow] mirror claim failed` | **无** — 文件锁照常判定, 只是镜像缺行 |
| agent-tick 心跳 | stderr 打 `[tick-coordination] heartbeat mirror failed` | **无** — tick 巡检照常, agent_health 停更 |
| submit 时 token-check | exit 2 → submit **停止** | token 缺失也落 `token_missing_legacy`; 只有 verdict 成功记录后 shadow 才放行 |
| `status` / `snapshot()` | 报错退出 | 观察面不可用 |

判断口径: shadow 阶段 `shadow_events.write_fail` 计数增长 = 降级运行中, 不算事故;
**warning/fail 阶段**该口径反转 (见 §5)。

## 2. 损坏识别

```bash
# 快速三查
DB=~/agents/_shared/runtime/coordination.sqlite3
sqlite3 "$DB" "PRAGMA integrity_check;"        # 期望 ok
python3 bin/gac/swarm-discipline-cli.py status # 期望三段可读
ls -la ~/agents/_shared/runtime/                # 看备份轮转与 last-backup 戳
```

`Agent Health` 每行的 `rev=` / `code=` 是实际运行中 tick daemon 的版本指纹。JSON
中的 `runtime_root_digest` 是权威运行态 workspace 规范路径的 SHA-256，不暴露原始路径。若
`rev` 不等于准备部署的 checkout `git rev-parse HEAD`，或显示
`runtime=unattested`，说明 launchd 仍在跑旧代码；先修部署源，不要把新 checkout
的测试结果当成运行态已经升级。指纹只含 commit SHA、源码 SHA-256、运行态根摘要和
Python 版本，不记录本机路径、用户名或主机名。

integrity_check 非 `ok` / `status` 报 `CoordinationStoreError` / DB 文件大小为 0 → 走 §3 恢复。

## 3. 从备份恢复

```bash
DB=~/agents/_shared/runtime/coordination.sqlite3
cd ~/agents/_shared/runtime/
# 1. 坏库留证 (别删, 复盘要用)
mv coordination.sqlite3 "coordination.sqlite3.corrupt-$(date +%Y%m%dT%H%M%S)"
# 2. 取最新可用备份 (.bak.1 最新, .bak.2/.3 更旧; 逐个 integrity_check 找第一个 ok 的)
for f in coordination.sqlite3.bak.1 coordination.sqlite3.bak.2 coordination.sqlite3.bak.3; do
  [ -f "$f" ] || continue
  if [ "$(sqlite3 "$f" 'PRAGMA integrity_check;' 2>/dev/null)" = "ok" ]; then
    cp "$f" coordination.sqlite3 && echo "restored from $f" && break
  fi
done
# 3. 删 WAL/SHM 残留 (恢复的库带旧 wal 会错乱)
rm -f coordination.sqlite3-wal coordination.sqlite3-shm
# 4. 验证
python3 bin/gac/swarm-discipline-cli.py status
```

**丢失口径**: 备份是 `.backup` 热备, 恢复点 = 上次成功备份时刻。shadow 阶段丢失的
只是镜像/事件历史 (文件锁才是权威), **没有真实协调状态可丢**。warning/fail 阶段
此口径需重估。

## 4. 备份节奏与部署

### 4.1 Tick daemon：代码根与运行态根必须分离

> 2026-08-20 (BET-Y1Q3-T1-08): 独立部署 clone `~/agents/coordination-daemon/ws` 已退役。
> 代码根与运行态根统一为权威 Workspace; 旧的只读 clone 不再维护, 备份 cron 已改指 Workspace。

daemon 代码从 main 对齐的 Workspace 加载；`.omo`、MOS、journey 和 heartbeat 只写权威
Workspace。daemon 会在导入 OMO 前设置 `WORKSPACE_CODE_ROOT`；JourneyRunner 读取运行态
journey 数据时仍使用 `WORKSPACE_ROOT`，执行 `journey-runner.py` 时只使用代码根。

```bash
CODE_ROOT="$HOME/Workspace"
RUNTIME_ROOT="$HOME/Workspace"

# 发布前单次受控验证：代码从 CODE_ROOT 加载，运行态写 RUNTIME_ROOT
python3 "$CODE_ROOT/bin/ssot/agent-tick-daemon.py" \
  --once --workspace-root "$RUNTIME_ROOT"
```

LaunchAgent 的 `ProgramArguments` 必须使用同一绑定：

```text
/opt/homebrew/bin/python3
$HOME/Workspace/bin/ssot/agent-tick-daemon.py
--run
--interval
300
--workspace-root
$HOME/Workspace
```

并在 plist 的 `EnvironmentVariables` 设置 `PYTHONDONTWRITEBYTECODE=1`，防止运行进程
向只读部署目录写 `__pycache__`。

切换后以 `swarm-discipline-cli.py status --json` 的 `workspace_revision`、
`code_sha256` 和 `runtime_root_digest` 为准；至少观察三个 5min 心跳周期。只看到进程存在
或 LaunchAgent loaded 不算部署成功。

**部署同步 SOP**（2026-08-15 ops 轮补充，实测踩坑后固化；2026-08-20 改为 Workspace 同步）：

```bash
CODE_ROOT="$HOME/Workspace"
# 1. 同步 (必须 ff-only; 若无法 ff 说明本地分支被污染, 停下排查, 不要强推)
git -C "$CODE_ROOT" fetch origin main && git -C "$CODE_ROOT" merge --ff-only origin/main
# 2. 重启加载新代码 (常驻进程不重启就还在跑旧代码)
launchctl kickstart -k "gui/$(id -u)/com.omostation.agent-tick-daemon"
# 3. 验证: 观察 status --json 的 code_sha256 变化 + 三个心跳周期内 last_seen 持续更新
python3 "$CODE_ROOT/bin/gac/swarm-discipline-cli.py" status --json | head -5
```

### 4.2 备份

两层 (grill Q9 裁定):

1. **crontab 日备 (主)** — 机器本地配置不进 git, 新机器要手工装:

```cron
# 协调层日备 (BET-Y1Q1-T1-05A; 2026-08-20 改指 Workspace): integrity + backup + 轮转
30 8 * * * cd "$HOME/Workspace" && python3 bin/gac/coordination_store.py --backup >> "$HOME/Workspace/runtime/logs/coordination-backup.log" 2>&1
```

2. **24h 时间戳兜底 (自动)** — 任何 store 访问若发现
   `coordination.sqlite3.last-backup` 超 24h，会在进程锁内复查完整性并用当前连接
   执行非递归 SQLite 热备，覆盖 crontab 没部署的机器。自动兜底失败在 shadow
   阶段只写 stderr，不反噬 claim/heartbeat；显式 `--backup` 仍会失败退出。

## 5. warning/fail 阶段的口径变化 (预告, 本 bet 不实施)

- `token-check` 从 exit 0 (只记录) 改 exit 1 (阻断 submit)
- branch-claim 双写失败从"落事件继续"改"拒绝认领" (fail-closed)
- DB 故障从降级运行升级为**事故** — 恢复 RTO 目标 TBD

## 6. 常见故障速查

| 症状 | 原因 | 处置 |
|------|------|------|
| `schema version N > supported 1` | 有新版 writer 先升级了 schema | 升级调用方代码; 不要手动降 user_version |
| `unable to open database file` | 目录权限/只读 FS | `ls -ld ~/agents/_shared/runtime/` 查权限 |
| submit 停在 "fail-closed (T1-05A)" | token-check exit 2 = DB 打不开 | 走 §2 → §3; 或 `SWARM_ESCAPE_ID=emergency-human-hotfix` 人工放行 |
| `write_fail` 事件暴涨 | DB 所在盘满 / busy 超时 | `df -h` 检查盘; WAL 模式下偶发 busy 是正常 |
| 备份静默断流（`.bak.1` mtime 超 24h 且 backup_ok 停更） | cron 指向的代码根停在 feature 分支/缺 store 文件（2026-08-15 实测: 主仓 checkout 被 human 切到 feature 分支, `coordination_store.py` 不在工作树） | `tail runtime/logs/coordination-backup.log` 确认; cron cd 路径指向 `~/Workspace`（§4.2 条目）; 手动 `--backup` 验证 |
| 心跳 code_sha256 落后 origin/main | 部署 clone 无自动更新机制 | 走 §4.1 维护 SOP: fetch + ff-only + kickstart + 三心跳观察 |

