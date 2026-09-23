---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-23
---
# Clash 节点架构 · 全量文档

> 最后更新: 2026-09-23 (下午, 探测改造后) · SSOT 真源: `SharedConf/ClashConfig` (iCloud git 仓库)
> 本文件为知识层快照; 运行时事实以 SSOT 为准, 勿在此硬编码会漂移的值。

## 1. 内核与运行时

| 项 | 值 |
|----|-----|
| 内核 | **ClashX Meta** (mihomo v1.19.31, app v1.4.45) |
| 迁移 | 2026-09-22 自原版 ClashX (core 停更 2021) 迁移; 原版保留为回退路径(降级版配置) |
| 配置真身 | **双写**: `~/.config/clash.meta/config.yaml` + iCloud 容器 `iCloud~com~metacubex~ClashX/Documents/config.yaml` (Meta `kUserEnableiCloud=1`, 读容器) |
| 端口 | mixed 7890 · external-controller 9090 (secret 见 conf; 注: Meta 运行时剥离配置内 secret 字段, 安全边界=127.0.0.1 绑定) |
| 切换 | 菜单栏"配置"子菜单 (config/work/travel); 脚本化用 `clash-profile.sh` (osascript 点菜单) |

## 2. SSOT 架构 (声明≠执行防线)

```
SharedConf/ClashConfig/          ← iCloud git 仓库, 全机同步
├── ssot/                        ← 唯一真源 (nodes/groups/settings/rules)
├── dist/                        ← build.py 产物 (home/work/travel)
├── deployed/                    ← 运行时快照存档
├── scripts/                     ← 16 文件: 15 运维脚本 + 共享 conf
│                                  (~/.local/bin/clash-*.sh 均为软链至此)
├── build.py                     ← 生成器 + lint 门禁 (死规则/引用完整性/MATCH)
├── bootstrap-mac.sh             ← 新 Mac 一键部署
└── DERP-MAP.md                  ← 自建中继接入配置
```

- 部署: `uv run --with pyyaml python build.py --deploy` (home 双写本机+iCloud容器)
- 校验: `--check` 只读 diff; lint 0 err 才允许 deploy
- 回退: 原版 ClashX 路径由降级版覆盖 (剔除 vless, 2021 老内核不认 Reality)

## 3. 节点资产 (2026-09-23, 真实转发探测口径)

> 实时状态以 `check-nodes.sh` / `clash-node-states` 为准; 下表只记结构与已证实的结论。

| 家族 | 节点 | 协议 | 状态 |
|------|------|------|------|
| 腾讯云硅谷 | Reality 43.173.115.36:8443 (samsung) | VLESS+Reality+Vision | ✅ 真实转发可用 |
| 阿里云 | Reality :8444 (apple) + VMess 直连/CF中转 | VLESS+Reality / VMess | ✅ 全部可用 |
| GCP | Reality :8444 (cloudflare) + SS-2022 + VMess CF中转 | 同左 | ✅ 全部可用 |
| 搬瓦工2 (CN2GIA LA, 74.211.101.240) | CF中转 (vps2) + 优选104a/b + Reality:8444 + 直连 | VMess+WS+TLS / VLESS+Reality | ✅ CF 线可用; 直连与 Reality 被墙 (v4 直连 EOF) |
| 搬瓦工1 | CF中转 (vps) + 优选 ×8 | VMess | ⏸ 停机至 10-02 重置 |
| 腾讯云上海 | 无代理 (国内云红线) | — | Tailscale derper |
| 猎豹 | 本地 SOCKS5 51081 | SOCKS5 | ✅ 出口为机房 IP |

**已证实的根因 (09-23)**:
- smux × mihomo 的 VMess 出站全系故障 — 移除后阿里/GCP/搬瓦工 VMess 全部恢复。此前"链路冷却"是误诊。**禁止再开 smux**。
- 搬瓦工2 重置后服务端 uuid 串成搬瓦工1 的 — 已改回。
- CF 节点开启证书校验不影响可用性 — 已全部开启 (仅源站直连保留跳过)。

**未验证 (勿当结论引用)**:
- "Meta core 忽略 dialer-proxy" — 支撑证据无效 (cache 本不含 proxies), 待用探测端口复验。
- "delay API 对 vless 恒报错" — 现象真实, 原因未查; 已不依赖 delay 判定。
- claude.ai 403 与节点无关 — 所有机房 IP 都 403; API / Claude Code 不受影响。

## 4. 策略组与规则

- 组: Proxy / 智能路由(url-test) / 大流量 / 住宅IP(fallback) / 全局兜底 / 开发 / **AI服务 (fallback: 搬瓦工2-CF中转 → 搬瓦工2 优选池 → Reality ×3 → 猎豹 …)** / 流媒体 / 视频会议 / 猎豹-白名单 / 池-搬瓦工×2
- 规则 (home): common 直连白名单 + 广告拦截 → AI 服务段 → 大流量 (含 huggingface/hf.co/lmstudio.ai) → 开发 → 支付 → 流媒体/会议 → MATCH
- travel: 回国加速 (cn→智能路由, 其余 DIRECT)
- Tailscale 控制台域名走代理

## 5. Tailscale 自建中继 (derper)

- 服务: 上海机 43.142.115.242, `derper -hostname derp.fshwjw.top -a :8443 -stun -certmode manual`
- 证书: acme.sh DNS-01 (CF token), 自动续期 cron active; CF 记录 DNS-only
- 效果: **shanghai 39.8ms 登顶 Nearest DERP** (hkg 同期 274ms)
- 接入: 管理台 ACL 加 derpMap (RegionID 900), 见 `DERP-MAP.md`
- **STUN 桥接 (0922)**: Go epoll/kernel3.10 不兼容致 derper 自带 STUN 全死 → `-stun-port=-1` + python stun-server.py (systemd) 独占 3478; 打洞前提恢复 (双侧对称 NAT 下 direct 仍不保证)
- tailscaled 客户端: plist NO_PROXY 豁免 derp.fshwjw.top (绕 Clash 转发层)

## 6. 猎豹线路体检结论 (2026-09-22)

7 区域 (美/日/台/韩/新/港/其它) 实测: 出口均为 **Nebula Global (AS18186)** 机房 IP, 非住宅。
- 美国T1: 149.104.139.83 (RTT 182ms 坐实LA) · 日本线: 149.104.51.194 (RTT130 东京) · 香港线: 206.119.59.207 (CF colo=HKG)
- 结论: 区域标签真实但全是机房落地; "住宅IP"组名不副实 (claude 走 DC IP 无风控豁免); 晚高峰容量紧 (WP1爆满)

## 7. 运维脚本体系 (repo/scripts/, 软链 ~/.local/bin)

脚本全表与 cron 以 `clash-inventory.sh` 输出为准。关键机制:

- **真实转发探测**: build.py 为每个节点生成 `127.0.0.1:17800+i` 专用 listener; `clash_probe.py` 经端口请求 generate_204。node-watch / check-nodes / health 均用它 (不再用 nc 或 delay API 判定)。
- **部署**: build.py lint → 双写 → 经内核 API `PUT /configs` 重载 → 规则数+节点数对账 → 不一致自动回滚。
- **巡检**: node-watch (23 分/时) · fleet-watch (41 分/时) · bw-warn (11 分/时) · bwg-usage (6h) · health/guard/traffic (30m) · cert (03:01) · 优选 IP (03:07)
- **通知**: osascript + `clash-notify.sh` (企业微信主 / TG 备, 配置在 `~/.local/etc/clash-notify.conf`, 未配置时只有本机通知)
- **凭据**: 一律在 `~/.local/etc/` (repo 外, 600), 不进 git

## 8. 多机部署

- 新 Mac 从零: `scripts/bootstrap-mac.sh`; 已装机器追平: `scripts/sync-mac.sh` (副机只挂本机轻量 cron, 对外探测只在主力机跑)
- 服务器: `scripts/bootstrap-server.sh reality` · 清单 `fleet.yaml`

## 9. 台账

唯一台账: `SharedConf/ClashConfig/plans/2026-09-23-retro-and-roadmap.md` (§3 路线)。本节不再单独维护。
