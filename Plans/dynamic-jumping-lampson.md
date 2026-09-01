# Tailscale 全面排查与恢复规划

## Context

Mac mini M4 不可达（T3-02 P3 mesh 服务化被阻塞）引发排查。结论：**tailscale 当前完全不可用**——tailscaled daemon 未运行，但网络层残留制造了"还活着"的假象。这是 2026-08-25 已发生过的同款病理（`projects/omlxc/docs/operations/2026-08-25-retrospective.md`："GUI 僵尸版与 brew 正主共存"），当时清了僵尸但**没建立防复发机制**，这次复发验证了"心跳在转但产出为真无人断言"的治理缺口。

## 诊断证据链

| # | 发现 | 证据 |
|---|------|------|
| 1 | daemon 死 | `tailscale status` → `failed to connect to local tailscaled... /var/run/tailscaled.socket: no such file or directory`（报 pid 590 但进程已不存在）|
| 2 | 服务未加载 | `brew services`: Running: false, Loaded: false |
| 3 | plist 在但没挂 | `/Library/LaunchDaemons/com.tailscale.brew.plist` 存在（KeepAlive=true）——launchd 从未加载它，KeepAlive 形同虚设 |
| 4 | **残留假象** | utun0 RUNNING + 路由 `100.64/10 → utun0` 仍在（daemon 死后未清理）——"接口活/路由在，数据流死" |
| 5 | 全节点失联 | Mac mini (100.99.210.78)、y7000p (100.64.43.36) 不可达；本机 ts IP 100.68.80.44 |
| 6 | 断链隐患 | `~/.config/omlxc/config.toml` 的 `[tailscale] executable = "/usr/local/bin/tailscale"` 是 symlink → `Cellar/tailscale/1.102.3/`（版本化路径，brew upgrade 即断；当前恰好有效）|
| 7 | 断言缺口 | omlxc 已有 `run_direct_doctor()`（`projects/omlxc/src/omlxc/diagnostics.py` 检查 tailscale identity），但无任何 cron/launchd 定期执行——死了没人知道 |

## 实施方案

### Phase 1 — 立即恢复（P0，~5 分钟）

```bash
# 1. 加载 daemon（需要 sudo，执行前向用户确认）
sudo launchctl load -w /Library/LaunchDaemons/com.tailscale.brew.plist
# 2. 恢复会话
tailscale up
# 3. 验证三连
tailscale status          # Mac mini/y7000p peers 应 Online
ping -c 3 100.99.210.78   # Mac mini 可达
ssh xiamingxing@100.99.210.78 'uptime'  # SSH 通（omlxc 文档既有运维通道）
```

失败分支：若 `tailscale up` 需要重新认证（浏览器登录），提示用户手动完成；若 plist load 报错，改用 `sudo brew services start tailscale`。

### Phase 2 — 防复发加固（P1）

1. **tailscale 心跳脚本** `bin/health/tailscale-heartbeat.sh`（新建，遵循 bin 配额 add1=del1）：
   - 每 10 分钟（launchd 或挂现有 resident/monitor 体系）跑 `tailscale status --json`
   - 失败 → 写 `.omo/state/tailscale-heartbeat.json`（`ok: false` + 错误摘要）+ 僵尸检测：daemon 死但 `utun0` 有 100.x 地址时额外标注 `zombie_interface: true`
   - 成功 → 记录 peers 数与 Mac mini 在线状态
2. **config.toml 断链修复**：`executable` 改为 `/opt/homebrew/bin/tailscale`（brew 稳定 symlink，upgrade 不断）
3. **巡检挂载**：omlxc `run_direct_doctor`（tailscale 检查已内建）纳入现有 gac 巡检链或 P74 compliance 体系，作为 weekly 检查项

### Phase 3 — 服务化联动（P2，依赖 Phase 1 成功）

1. Mac mini 在线后：跑 `ssh xiamingxing@100.99.210.78 'lms ps'` 确认 LM Studio 池活
2. 执行 **T3-02 P3**（挂账待办）：Mac mini 经 cluster_coordinator 注册 mesh 嵌入节点（bos://compute/omlxc/embed）
3. `mesh-telemetry.json` 恢复产出 → `cockpit spine status` 恢复数据面

## 验证清单

- [ ] `tailscale status` 显示 Mac mini + y7000p Online
- [ ] `ping 100.99.210.78` 通
- [ ] 心跳脚本首跑：`.omo/state/tailscale-heartbeat.json` 产出且 ok=true
- [ ] 僵尸接口检测逻辑：手工 kill daemon 后 10 分钟内心跳标注 `zombie_interface`（可选验证）
- [ ] `make gac-local-gate` PASS（bin 配额同步后）

## 涉及文件

| 文件 | 动作 |
|------|------|
| `/Library/LaunchDaemons/com.tailscale.brew.plist` | launchctl load（不改文件）|
| `~/.config/omlxc/config.toml` | `[tailscale] executable` 路径修正 |
| `bin/health/tailscale-heartbeat.sh` | 新建（配额：归档一个旧脚本抵扣）|
| `.omo/state/tailscale-heartbeat.json` | 心跳产物（运行时区，不入库）|
| `projects/omlxc/docs/operations/2026-09-01-tailscale-recurrence.md` | 复盘记录（复发病例入档）|

## 风险确认点

- `sudo launchctl load` 需要 root——执行前需用户确认
- `tailscale up` 若要求浏览器重新认证，需要用户手动介入
