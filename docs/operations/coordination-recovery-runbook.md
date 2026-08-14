# Coordination Layer Recovery Runbook — BET-Y1Q1-T1-05A

> 适用对象: 共享运行时协调层 `~/agents/_shared/runtime/coordination.sqlite3`
> 状态: shadow 灰度 (D2/D3 文件锁仍是权威判定源; 本 DB 挂了不影响现有纪律)
> Owner: BET-Y1Q1-T1-05A · 详细分析: `docs/reports/2026-08-14-shared-runtime-coordination-gap.md`

## 1. 这层挂了会发生什么 (shadow 阶段)

| 组件 | 失效症状 | 影响 |
|------|---------|------|
| branch-claim 双写 | stderr 打 `[swarm-shadow] mirror claim failed` | **无** — 文件锁照常判定, 只是镜像缺行 |
| agent-tick 心跳 | stderr 打 `[tick-coordination] heartbeat mirror failed` | **无** — tick 巡检照常, agent_health 停更 |
| submit 时 token-check | exit 2 → submit **停止** | 唯一 fail-closed 点 (防在坏 DB 上做 fencing 判定) |
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

两层 (grill Q9 裁定):

1. **crontab 日备 (主)** — 机器本地配置不进 git, 新机器要手工装:

```cron
# 协调层日备 (BET-Y1Q1-T1-05A): integrity + backup + 轮转
30 8 * * * cd "$HOME/Workspace" && python3 bin/gac/coordination_store.py --backup >> runtime/logs/coordination-backup.log 2>&1
```

2. **`maybe_backup()` 时间戳兜底 (自动)** — 任何 store 访问若发现 `coordination.last-backup`
   超 24h 会顺带备份, 覆盖 crontab 没部署的机器。

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
