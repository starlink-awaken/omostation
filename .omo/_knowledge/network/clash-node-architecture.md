# Clash 节点架构 · 全量文档

> 最后更新: 2026-09-23 · SSOT 真源: `SharedConf/ClashConfig` (iCloud git 仓库)
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

## 3. 节点资产 (2026-09-22)

| 家族 | 节点 | 协议 | 状态 |
|------|------|------|------|
| 腾讯云硅谷 | Reality (43.173.115.36:8443, 伪装 www.samsung.com) | **VLESS+Reality+Vision** | ✅ 协议升级试点; 已历端口 443→8443 对抗 EOF 干扰; delay API 对 vless 恒报错为 mihomo 已知怪癖(实测通) |
| 阿里云 | Reality (47.253.89.56:8444, 伪装 www.apple.com) | **VLESS+Reality** | ✅ 2026-09-22 铺开; 独立 xray-reality unit 零破坏并行; firewalld+安全组已放行 |
| GCP | Reality (34.58.87.36:8444, 伪装 www.cloudflare.com) + SS-2022 + CF中转 | **VLESS+Reality** | ✅ 2026-09-22 铺开; gcloud 防火墙规则 allow-reality-8444 |
| 腾讯云上海 | 无代理节点 (红线: 国内云禁跑翻墙服务端) | — | 定位: **Tailscale derper** |
| 搬瓦工1/2 | CF中转 + CF优选 ×13 | VMess+WS+TLS+smux | ⏸ 流量耗尽暂停 (clash-bw-warn.sh 每小时探测恢复) |
| 阿里云 | 直连 + CF中转 | VMess | 链路冷却观察 (服务端健康) |
| GCP | SS-2022直连 + CF中转 | SS-2022 / VMess | SS 活; vmess 观察 |
| 猎豹机场 | 本地 SOCKS5 51081 | SOCKS5 | 出口=Nebula Global 机房IP(非住宅); 体检结论见 §6 |

**已知坑**: 密集 delay 测试曾触发 GFW 端口级 EOF 干扰 → 巡检频率克制 (probe 6h, bw-warn 1h)。

## 4. 策略组与规则

- 14 组: Proxy(总入口) / 智能路由(url-test) / 大流量 / 住宅IP(fallback) / 全局兜底 / 开发 / **AI服务**(select, 默认猎豹) / 流媒体 / 视频会议 / 猎豹-白名单 / 池-搬瓦工×2
- 92 条规则 (home): common(直连白名单+广告拦截REJECT) + AI服务段(openai/claude/gemini/grok等10域) + 支付住宅 + 流媒体/会议 + MATCH
- travel 场景: 回国加速 (cn→智能路由 + 默认 DIRECT)
- Tailscale 控制台域名走代理 (本机 DNS 对 tailscale 系解析失败, 2026-09-22)

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

| 脚本 | 功能 | cron |
|------|------|------|
| clash-health.sh | 全链路 (服务4项+节点delay+Reality TCP+derper+DNS泄漏+socks5) | */30 |
| clash-proxy-guard.sh | 系统代理端口自愈 | */30 |
| clash-traffic.sh | 流量 CSV 统计 | */30 |
| clash-git-sync.sh | SSOT 仓库幂等提交 | 9 */2 |
| clash-bw-warn.sh | 搬瓦工恢复探测+通知 | 11 * |
| clash-probe.sh | 全节点 TCP 443 存活 | 0 */6 |
| clash-cert-check.sh | 阿里/GCP xray 证书 + derp 证书 | 1 3 * |
| clash-node-watch.sh 🆕 | 全节点状态机: 分类探测+失联告警+恢复通知 (osascript+TG) | 23 * |
| clash-inventory.sh 🆕 | 活清单生成器 (清单即真值, 手工快照作废) | 手动 |
| clash-status.sh / toggle / profile / notify / webrtc-check | 手动工具 | — |
| check-nodes.sh / refresh-cf-ips.sh (repo/scripts) | 全节点 delay 巡检 / CF优选IP腐化 | 手动 |

共享配置: `repo/scripts/clash-scripts.conf` (软链 ~/.local/etc/), 含 API secret/路径/DERP 变量。
通知: `clash-notify.sh` 支持 Telegram (需自建 `~/.local/etc/clash-notify.conf`), 默认走 osascript 本地通知。

## 8. 多机部署

新 Mac: 等 iCloud 同步 → `bash repo/scripts/bootstrap-mac.sh` → 菜单勾系统代理/开机启动。
macmini: 同流程 (脚本自适应; 其 Tailscale 数据面问题另行排查)。

## 9. 挂账 / 下一步

- [ ] CF API Token 轮换 (曾入对话日志; 轮换后更新上海机 acme account)
- [ ] **本机 tailscaled 拉起** — plist NO_PROXY 已写好, 差 `sudo launchctl bootstrap system /Library/LaunchDaemons/com.tailscale.brew.plist` (Terminal.app 手跑; 弹框三次未输)
- [ ] 搬瓦工流量恢复 → node-watch/bw-warn 自动探测, 恢复后评估 Reality 模板
- [ ] 阿里云/GCP vmess 链路冷却复查 (Reality 已就位接班)
- [ ] 原版 ClashX 降级版机制化进 build.py (当前一次性同步)
- [x] macmini ClashX Meta 部署 (0922 17点完成, 双机同构)
- [x] Reality 三机铺开 (硅谷+阿里+GCP 全链路)
- [x] STUN 桥接 (打洞前提恢复)
- [x] node-watch 全节点状态机 + inventory 活清单
