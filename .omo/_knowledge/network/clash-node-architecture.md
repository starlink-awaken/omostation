# ClashX 节点架构与代理体系（2026-09-21 终版）

> SSOT: ClashX 代理体系的全量文档。配置: `~/.config/clash/config.yaml` → symlink → iCloud ClashX Documents
> 存档: `~/.config/clash/backups/` · 仓库: `~/.config/clash/repo/`

## 节点清单（20 个活动节点）

### 云机房（机房 IP，CF 边缘隐藏源站）
| 节点 | 服务器 | 协议 | CF 前端域名 | 源站隐藏 |
|------|--------|------|-----------|---------|
| 阿里云-VMess-直连 | 47.253.89.56:443 | VMess+WS(/ray) | — | — |
| 阿里云-CF中转 | aly.fshwjw.top:443 | VMess+WS+TLS | aly.fshwjw.top → 172.67.196.104(CF) | ✅ |
| GCP-SS-直连 | 34.58.87.36:8443 | SS2022 | — | — |
| GCP-CF中转 | gcp.fshwjw.top:2087 | VMess+WS+TLS | gcp.fshwjw.top → 172.67.196.104(CF) | ✅ |

### 搬瓦工（流量耗尽停机中，等月度重置）
| 节点 | 服务器 | 协议 |
|------|--------|------|
| 搬瓦工2-VMess-直连 ~ 优选×4 | 176.122.177.208:443 + CF优选IP | VMess+WS(/v2ray) |
| 搬瓦工1-CF中转 ~ 优选×8 | vps.fshwjw.top + CF优选IP | VMess+WS(/v2ray) |

### 本地依赖
| 节点 | 端点 | 状态 |
|------|------|------|
| 猎豹-SOCKS5-直连 | 127.0.0.1:51081 | ✅ 可通（claude 403/chatgpt 200）；需 app 手动点"连接" |

## 分组结构（9 组）

| 组 | 类型 | 链 | 职责 |
|----|------|-----|------|
| Proxy | select | 智能路由/大流量/住宅IP/全局兜底/开发/猎豹-白名单场景/DIRECT | 用户选择器 |
| 智能路由 | url-test(300s,80ms) | 池2→池1→阿里云×2→GCP×2→搬瓦工×2 | 日常最快 |
| 大流量 | url-test(300s,80ms) | 阿里云×2→GCP×2 | 下载/大文件，仅机房（保留 BWG 流量） |
| 住宅IP | fallback(30s) | 池2→池1→猎豹-白名单场景 | Claude/敏感，纯住宅 |
| 全局兜底 | fallback(60s) | 智能路由→住宅IP→猎豹-白名单场景 | 最高可靠 |
| 开发 | fallback(30s) | 大流量→DIRECT | 开发资源不断 |
| 猎豹-白名单场景 | select | 猎豹-SOCKS5-直连/DIRECT | 手动住宅 |
| 池-搬瓦工2-CF优选 | url-test(300s,50ms) | 5 节点 | BWG2 内部 CF 优选 |
| 池-搬瓦工1-CF优选 | url-test(300s,50ms) | 9 节点 | BWG1 内部 CF 优选 |

## DNS
```yaml
dns:
  enable: true
  listen: 127.0.0.1:5353
  nameserver: [https://1.1.1.1/dns-query, https://dns.google/dns-query]
  fallback: [https://dns.alidns.com/dns-query, https://doh.pub/dns-query]
  fallback-filter: {geoip: true, geosite: [cn], ipcidr: [240.0.0.0/4, 100.64.0.0/10]}
```

## 路由策略

| 优先级 | 匹配 | 出口 | 理由 |
|--------|------|------|------|
| 1 | 本地 (10/172.16/192.168/127/100.64/169.254/localhost/.local/fshwjw.top) | DIRECT | 内网不走代理 |
| 2 | 中国 (GEOSITE,cn + GEOIP,cn) | DIRECT | 国内更快 |
| 3 | Apple CDN | DIRECT | 苹果中国 CDN |
| 4 | 广告 (category-ads-all) | REJECT | 节省流量+提速 |
| 5 | AI 敏感 (claude.ai/anthropic.com) | 住宅IP | GFW SNI 阻断机房 IP |
| 6 | 大流量 (github/docker/huggingface/steam/游戏/网盘) | 大流量 | 保留 BWG 流量 |
| 7 | 开发资源 (容器/包管理器/OS源) | 开发 | 机房优先 |
| 8 | AI 通用 (openai/google) | Proxy | 机房可通 |
| 9 | 流媒体/社交 | Proxy | 必须翻墙 |
| 10 | 海外兜底 (geolocation-!cn) | Proxy | 默认 |

## 监控、告警与恢复

### 脚本
| 脚本 | 用途 | 调用 |
|------|------|------|
| `~/.local/bin/clash-health.sh` | 全链路健康：节点延迟+服务级(claude/chatgpt/google/bulk/direct)+猎豹socks5 | cron 每 30 分钟 (:13/:43) |
| `~/.local/bin/clash-probe.sh` | 搬瓦工 IP 恢复探测 | cron 每小时 (:22) |
| `~/.local/bin/clash-cert-check.sh` | CF 证书过期（10 天内告警） | 每天 03:01 |
| `~/.local/bin/clash-traffic.sh` | 流量统计 CSV + 差值 | cron 每 30 分钟 (:07/:37) |
| `~/.local/bin/clash-toggle.sh` | 紧急断开/恢复 (off/on/status) | 手动 |
| `~/.local/bin/clash-git-sync.sh` | 配置 git 自动提交 | 每 2 小时 |
| `~/.local/bin/clash-status.sh` | 一键终端总览 | 手动 |

### 告警
- 失效/恢复双向 macOS 通知
- 状态文件防重复告警
- 日志自动轮转（5000 行）

### 兜底与恢复
- 分组 fallback/url-test 自动跳过死节点
- 猎豹断开→自动 fallback；重连→通知
- 搬瓦工恢复→探测通知→自动选入
- Clash API 全挂→FATAL 告警

## 云主机调优（2026-09-21）
| 机器 | 调优 | 结果 |
|------|------|------|
| GCP 34.58.87.36 | BBR+fq, VMess-WS+TLS 入站 2087, CF 前端 | ✅ |
| 阿里云 47.253.89.56 | BBR+fq, 443 plain WS→WS+TLS, CF 前端 | ✅ |

## CF 前置
- 阿里云: aly.fshwjw.top → CF 边缘 172.67.196.104 → 源站 47.253.89.56
- GCP: gcp.fshwjw.top → CF 边缘 172.67.196.104 → 源站 34.58.87.36
- 证书: acme.sh DNS-01 自动续签（ECC-256），部署钩子 + 续签 cron
- 验证: DNS 解析到 CF IP（非源站），✅ 源站隐藏成功
