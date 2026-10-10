---
schema: md/v1
status: PROPOSED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-10-09
type: ssot
id: ADR-0465
related:
  - ../../_archive/infrastructure-history/phase0-硬件基建/hw-05-配置同步与终端环境.md
  - ./0464-declaration-vs-execution-three-governance-blindspots.md
tags: [config-sync, dotfiles, magpie-boundary, secrets, tailscale, swiftbar]
---

# ADR-0465 — mbp ↔ Mac mini 配置同步架构：git dotfiles 仓 + rsync 单向 + launchd 巡检 + SwiftBar 出口

- **Status**: PROPOSED（方案已于 2026-10-09 全量落地两机并实测验证；本 ADR 补记选型与边界契约，supersede hw-05）
- **Date**: 2026-10-09
- **Traceability**: 会话 `3086faa0`（计划 `Workspace/Plans/mbp-magpie-woolly-balloon.md`，已批准）；
  交付仓 `github.com/starlink-awaken/dotfiles`（私有）；同日 Tailscale GUI→brew daemon
  迁移（另一会话 `e27fbad7` 协调分工完成）。

## Context

两机（Mac mini hub / MacBook Pro client）长期各自手维护 `~/.claude`、shell、brew、
菜单栏配置，漂移无人发现。2026-10-09 盘点发现：`com.l4.omo.sync` LaunchAgent 因
uv 传参错误处于崩溃循环，且其语义是治理状态自记录而非文件同步（见
`projects/omo/src/omo/omo_sync.py`）；iCloud 桌面/文稿同步结构已坏（偏好开但
~/Desktop 是真实目录）；hw-05 时代的配置同步先例早已 archived 且基于过期假设。

约束：模型/客户端配置分发以 **magpie 为核心**（用户指定），MEMORY/PULSE/会话数据
体量大且机器本地，生成文件（settings.json）与 magpie 写入面（~/.config/magpie/**）
不能进任何同步通道，否则冲突放大。

## Decision

### 1. 选型（对比结论）

git 私有仓（dotfiles）+ rsync over Tailscale SSH + launchd 漂移巡检 + SwiftBar 可观测
出口。否决 iCloud（结构坏+330M MEMORY 冲突副本+明文上云）、Syncthing（双向持续同步
对生成文件是冲突放大器）、Mackup（symlink 依赖坏 iCloud）、chezmoi/nix 整装复活
（hw-05 先例；重造成本不匹配两机现状）。吸收 chezmoi 的 per-host 变体思想
（`dot/hosts/<hostname>/`）与密钥永不进仓原则。

### 2. magpie 边界契约（写冲突防线）

| 面 | 归属 |
|---|---|
| `~/.config/magpie/**` | magpie 独占，任何同步脚本/manifest/备份排除 |
| `~/.claude/CLAUDE.md` magpie 块、`settings.json` | 生成文件不同步，仅做生成链一致性巡检 |
| AI 客户端配置/skill 分发、provider key 流动 | 全归 magpie，不重复造分发器 |
| MEMORY / PULSE / 会话数据 | 机器本地，永不同步 |

### 3. 分层与方向

L1 AI 工具链（LifeOS 配置三件套 git 双向；USER 其余 mini→mbp 单向 rsync；系统目录
只校验不复制）· L2 终端（per-host shell 四件套 + 共享 zshrc.d 分支机制 + Brewfile
基线）· L3 菜单栏（menubar 收编进仓，SwiftBar cask）· L4 Workspace（不 rsync，GitHub
remote 天然覆盖）· L0 通道（ssh config MagicDNS 别名，IP 变更免改）。

### 4. Secrets 政策

明文 key 永不进仓/不进同步（settings.user.json 因含明文 DeepSeek key 暂缓入仓，
待 Keychain 六步轮换完成后脱敏入仓——2026-10-09 用户指示延后）。巡检含 sk- 明文
泄漏规则，红灯即报警。

### 5. 可观测

`bin/sync-drift.py`（capture/check/status/parity/restore）每小时 launchd 巡检，原子写
drift-report；SwiftBar `sync.30s.sh` 读报告渲染绿/红灯+修复动作；红灯演练已实测
（篡改纳管链接→下轮巡检变红→restore 恢复）。

### 6. 本仓变更（随本 ADR 落地）

- 3 处旧 Tailscale IP 引用更新（GUI 迁移 brew daemon 后 mini 新 IP）：
  `bin/health/tailscale-heartbeat.sh`、`bin/gac/convergence-pulse.py`、
  `projects/omo/src/omo/pipeline_supervisor.py`（走 .subtrees + bump-pointer）。
- `com.l4.omo.sync` LaunchAgent 判删（坏件 + 职能重叠），debt 条目
  `O-BROKEN-LAUNCHAGENT-OMO-SYNC` 记录证据。
- 工具脚本全住 dotfiles 仓，绕开本仓 bin/ 脚本配额（add 1 = delete 1）。

## Consequences

- 正面：同步面持久化（git）、可观测（drift-report + menubar 红绿灯）、单向显式、
  magpie 零干扰；glm 路由回写问题的根治路径已铺（源头入仓 + 巡检规则）。
- 负面/债务：Brewfile 仅基线不强制对齐；menubar parts 中 hub 服务探测项在 mini 上
  按域主机适配未做（已知非同步故障）；local-ops 目前一次性单向拷贝未纳正式层。
- 后续：Keychain 轮换完成后 settings.user.json 脱敏入仓；MBP 主机名固化与
  tailscaled 直连重启为用户手工步（sudo）。
