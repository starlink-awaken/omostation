# 全节点运维监控面板（SwiftBar 集成）— 实施计划

> 2026-11-04 · 基于 fleet-ops 复活升级（避免重复造轮子）· 混合 pull/push 架构

## Context

需求：全部机器（云+本地 25 台级）的 流量/CPU/内存/磁盘/网络/负载/温度 实时监控，可视化，集成 SwiftBar。

探索结论（三轮并行侦察 + 双 Explore agent + Plan agent 验证）：
- **fleet-ops 体系已存在且活着**——mini(hub, id=control-01) 每 ~5min ssh 拉取 22 台 → `state.json` → 60s rsync → 各机；SwiftBar 插件 `fleet.1m.py` 完整存在但被禁用。这是 80% 的答案，**复活而非新写**。
- 指标缺口：CPU%、温度、网络速率、swap（已有 load/mem%/disk%/uptime/v6/probe_ms）；无历史时序。
- **P0 坑（Plan agent 实测发现）**：hub→lab 网段无路由，bot-01~08/vm-*/exec-host 共 8+ 台现在全是 `skipped`（"22 台监控"名不副实）。
- 机器清单漂移：缺 unit-studio-01、compute-i9-01、bot-06~08；mini 就是 control-01（无需加）。
- Clash 系 `fleet-metrics.sh` 是死的重复系统（cron 已消失、停更 1 天）→ 退役。
- 用户拍板：温度 ansible 统一部署；lab 接入采用 **push agent 混合架构**（用户提出，业内标准形态——跨 NAT 监控的正解）。

## 架构（混合 pull/push）

```
macOS 主力(MBP/双Studio/mini) + 可达VPS(bwg2/tencent等)   lab/bot 集群(NAT后 8+台)
        │ ssh pull（现状不动，零部署）                          │ push agent
        ▼                                                       ▼
   mini(hub) collect.py ──state.json──┐              bot-01 接收器(公网:8018 + tailnet)
                                      │                        │ 聚合转发(tailnet)
                                      ▼                        ▼
                              state.json（mini，唯一聚合点）◄──
                                      │ 60s rsync（com.fleetops.sync）
                                      ▼
                    SwiftBar fleet.1m.py（激活+升级：CPU/温度/网速列 + sparkline）
```

关键复用：**PROBE 探针单一真源**——pull（hub ssh 拉进来跑）与 push（本机 systemd timer 自己跑）执行同一段 `collect.py` 里的 PROBE 代码，指标语义永远一致。

## 实施步骤（顺序=依赖序）

### Step 1 · bot-01 网关化（lab 接入的锚点）
- bot-01 装 tailscale 入网（需用户在管理台批准或给 auth key）+ 简易接收器（~40 行 python http.server：`POST /report`，token 鉴权，写 `lab-state.json` + 每 60s 聚合推 mini tailnet 地址）
- systemd 部署经 ansible（与 Step 6 合并一次 run）

### Step 2 · inventory/hosts.toml 清单对齐 → `inventory_gen.py --write`
- 新增：unit-studio-01、compute-i9-01、bot-06/07/08（`status="unregistered"` 先登记）
- `muse` optional→unregistered（自述"任何机器都登不进"）；embp2014/aly 保持 optional
- lab 机（bot-01~08/vm-*/exec-host）改 `reach="push"`，target 指 bot-01:8018

### Step 3 · collect.py PROBE 扩展（Plan agent 已给可粘贴代码，sh -n 验证过）
- Linux：CPU%（/proc/stat 探针内 sleep 1 差分）、swap%、net rx/tx 字节（/proc/net/dev 去 lo）、温度（sensors -u 取最大 _input，未装则空）
- macOS：CPU%（`/usr/bin/top -l 2 -n 0 -s 1` 取末行——**绝对路径防 procs 遮蔽，实测坑**）、swap%（vm.swapusage）、net（`/usr/sbin/netstat -ib` 只计 `<Link#>` 行）、`temp_c=` 留空
- 约束：全程 POSIX sh（远端可能是 dash）

### Step 4 · collect.py 差分速率 + history.jsonl
- main() 保留 prev state（hosts+ts）；up 分支内：dt≥60 且 uptime 未回退 → `net_rx/tx_kbps = Δbytes×8/dt/1000`；首轮无基线自然缺省
- 每轮 append `history.jsonl`（~1KB/行，logrotate max_mb=5/keep=3 ≈ 45 天）
- 顺手修 `--only` 会把 state 缩成单机的现有缺陷（merge prev 一行）

### Step 5 · 阈值 + 同步 + 插件
- thresholds.toml：cpu_used_pct(90/99——crit 99 挡住 Studio 满载推理 push)、temp_c(75/85)、swap_used_pct(60/90)
- sync_state.sh 文件列表加 history.jsonl（非 hub 机的 sparkline 数据源；保持全量 rsync 不改 --append）
- fleet.1m.py：机器行加 `C{cpu}`/`{temp}°`；up 主机子菜单（↑↓速率/swap/probe + CPU sparkline——history 尾读 64KB 容忍半行）

### Step 6 · ansible 统一部署（用户拍板项合并）
- lab 全体：lm-sensors（Debian 装完即出数）+ push agent（PROBE 提取成独立文件分发 + systemd timer 每 5min curl POST bot-01 + token）

### Step 7 · 激活插件 + Clash 系退役
- `mv ~/.config/swiftbar-plugins/.disabled/fleet.1m.py ~/.config/swiftbar-plugins/`（软链已存在）
- 删 fleet-metrics.sh/proxy-fleet.30s.sh（dotfiles 原位留注释指向 fleet-ops）

## 关键文件
- `~/Project/fleet-ops/tools/collect.py`（PROBE/parse_probe/diff/history）
- `~/Project/fleet-ops/swiftbar/fleet.1m.py`（渲染升级）
- `~/Project/fleet-ops/inventory/hosts.toml` + `tools/inventory_gen.py`
- `~/Project/fleet-ops/tools/sync_state.sh`、`config/thresholds.toml`、`ansible/`（新增 push agent role）
- 新增：`~/Project/fleet-ops/tools/lab_receiver.py`（bot-01 接收器）

## 坑清单（Plan agent 12 条的要点）
P0：POSIX sh（禁 [[ ]]）、hub→lab 路由（本方案 push 解）；P1：macOS top/netstat 绝对路径、CPU 单采样失真（差分已内嵌）、--only 缩 state（顺手修）；P2：计数器回绕容忍、y7000p 维持 skipped（可 ping-only）、新告警首启噪声（cooldown 已有）；P3：sync 漏 history、轮转半行容错。

## 验证
1. 单测：parse_probe 双分支（含 temp 空）、速率差分三 guard、sparkline 尾读容错（unittest，现有 8 文件风格）
2. 探针单机：hub 上 `FLEET_OPS_STATE=$(mktemp -d) collect.py --only <id>` 跑两次，第二轮 kbps 出值且量级合理
3. 双分支真机矩阵：mini(macOS)/bwg2(Linux 无 sensors)/bot-01(lab)/MBP
4. 端到端：激活后 menubar 出 fleet 图标，2 周期后 CPU/速率/sparkline 有值；MBP 侧 history.jsonl 已 sync
5. lab push 链：bot-02 agent → bot-01 接收器 → mini state.json → 面板可见
6. 回归：现有 8 个测试全绿；Clash 侧 mfind 确认清

## 分期（如需收敛范围）
- 第一波（今天）：Step 2-5+7（pull 面全升级 + 插件激活）≈ 2h
- 第二波（等 tailscale 批准）：Step 1+6（lab push 链 + ansible）≈ 1h
