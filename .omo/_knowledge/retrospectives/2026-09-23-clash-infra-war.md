---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-23
---
# 复盘：Clash/Tailscale 基础设施大战 (2026-09-22 ~ 09-23)

> 范围: ClashX→Meta 迁移 · SSOT 模板化 · 三机 Reality · 自建 derper · 双机同构 · 17 脚本体系
> 产出: clash repo 24 commits · 知识文档 · 本复盘

## 1. 战果量化

| 维度 | 战前 (09-21) | 战后 (09-23) |
|------|-------------|-------------|
| 真源 | 单文件 config.yaml 手改 | SSOT 模板 + build.py lint 门禁 + 双写部署 |
| 内核 | ClashX (core 停更 4 年, 9090 不监听) | ClashX Meta mihomo 1.19.31, API 全通 |
| 协议 | VMess+WS+TLS 全家 (2019 特征) | **三机 VLESS+Reality** (硅谷/阿里/GCP) + VMess 存量 |
| 多机 | 单机 | 本机 + macmini 双机同构 (iCloud SSOT) |
| Tailscale | 官方中继 88~274ms 绕路 | 自建上海 derper **59ms** (Nearest 登顶) |
| 运维 | 手工快照清单 | 17 脚本 / 8 cron / node-watch 状态机 / inventory 活清单 |
| 监测 | 无 | 失联❌告警 + 恢复✅通知 + 证书/优选/IP 全覆盖 |

## 2. 失败模式清单 (老王自己的失误, 按成本排序)

| # | 失误 | 损失 | 根因 |
|---|------|------|------|
| F1 | **两次 x25519 生成错对** — Reality 服务器写第一对私钥、客户端写第二对公钥, 节点瘫痪 `REALITY authentication failed` | ~1h | 并行调用未共享随机源; 后续修正为"单次调用取 PRIV+PUB 双值"流程 |
| F2 | **STUN 诊断绕路 5 层** — 报文格式→安全组→iptables→strace假阴性→最后 A/B 才切中 Go/kernel 真因 | ~2h | 没有先做最小对照实验 (python 绑同端口 30 秒就能一锤定音) |
| F3 | **iCloud 双写真相缺失** — Meta `kUserEnableiCloud=1` 读容器, bootstrap 只写本地, 容器占位文件致**规则消失事故** (92→6 条) | ~30min | 部署目标枚举不完整; "真身在哪"未文档化 |
| F4 | **DNS 三连环** — 5353 被 Chrome mDNS 抢占 + nameserver 用国外 DoH(被墙) + health 脚本端口 5354 写错 | ~1.5h (含 macmini 黑洞连带) | DNS 从未按国内环境设计; 端口选择无冲突检测 |
| F5 | **密集 delay 测试炸出 GFW EOF** — 377 次 `connect error: EOF` 是自己测出来的 | ~1h 误判为服务器故障 | 测试行为改变系统状态, 未节制未记录 |
| F6 | **收编脚本不改引用** — bootstrap SRC 相对路径 + dist 产物名两个连环 bug | ~20min | 结构迁移未 grep 全部消费者 (declare≠execute 变体) |
| F7 | **组成员 replace(...,1) 贪心** — AI服务组漏加 Reality, `proxy not exist` | ~10min | 锚点匹配假设过强 |
| F8 | **宿主环境隐形地雷** — cp/mv/ps/ls 全被 alias 改造 (交互确认/procs), osascript 引号 heredoc 四连败 | ~40min | 动手前未 `command -v` 验真身; 转义地狱未用"写文件执行"绕过 |
| F9 | **密码框依赖用户在场** — 4 次弹框 3 次超时 (含 1 个非本会话残留框叠着) | 间接拖延 | 长时挂起的授权请求无在场确认机制 |

## 3. Meta 教训 (可固化 Pattern)

- **P-a 结构迁移三步走**: 移动文件 → `grep -r 消费者` → 修引用 → 冒烟。收编/重命名必须全量改引用。
- **P-b 部署目标是 SSOT 的一部分**: `settings.yaml::deploy` 数组化已落地; 新目标必进数组, 进数组必有回读验证。
- **P-c 诊断先 A/B 后深挖**: 30 秒对照实验 (同端口换实现/同路径换协议) 优先于 5 层串行猜测。
- **P-d 测试有反作用**: 对抗性环境 (GFW/风控) 下密集探测 = 制造故障; 巡检频率是安全参数不是效率参数。
- **P-e 宿主验真**: alias 化 shell (cp -i/ps→procs)、TCC 权限、密码框在场 — 操作前验工具真身。
- **P-f 密钥一次生成双值**: 凡 keypair 生成, 单次调用内取齐 PRIV/PUB, 严禁两次调用拼对。

## 4. 迭代优化路线

### P0 (今天, 人工)
- [ ] CF API Token 轮换 (曾入对话日志) → 更新上海机 acme account.conf
- [x] 猎豹 GUI 重连 (0923 完成, socks5=up, 新出口 38.148.221.191)
- [x] 搬瓦工时间表落定: #1 0923 11:30 (自动任务 0ef9f2f6) · #2 1002 (debt DEBT-20261002-BWG2)

### P1 (本周, 老王)
- [x] **deploy 后自动对账** (本次复盘当场实现): build.py --deploy → 触发 Meta 重载 → curl API 规则数与产物对账, 不匹配 exit 1 — declare≠execute 的机制终结者第 1 件
- [x] 降级版同步机制化 (build.py --deploy-legacy, 三目标实跑 LEGACY-DEPLOY)
- [ ] stun-server 进 node-watch 探测 (3478 STUN 挂了打洞静默退化)
- [x] health DNS 跑绿验证 (6053, "Clash DoH 解析正常" 首绿)

### P2 (本月)
- [x] 优选 IP 每日 cron (03:07)
- [ ] TG notify 配置 (等用户 token)
- [ ] 上海机 kernel-ml 升级评估 (3.10→5.x 治 Go 兼容本; 若 python stun-server 长期稳定则降级为可选)
- [ ] derper 冗余规划 (第二台国内机热备 — 依赖新购国内轻量)

### P3 (理想态) — 详版: repo/plans/P3-roadmap.md (0923)
- [x] **deploy 全链路闭环**: 对账+失败自动回滚 (受控投毒实弹: 拦截→回滚→复验92=92)
- [x] 体系一页看板 clash-dashboard.sh + **B1 接入 agent-brief health.clash** (2ac8404c1)
- [ ] 协议存量清退: 搬瓦工 vmess 全族 Reality 化 (等复活后)

## 5. 成本账

- 时间: ~20 人时跨 2 天 (含 macmini 部署与 Tailscale 三层病)
- 失误税: ~5.5h (F1-F9 合计) — 占比 ~27%, 主要是 F2 诊断绕路与 F4 DNS 设计债
- 云资源: 腾讯双机 (既有) + 3 张证书 (acme 免费) — 零新增成本
