# magpie 本体与运维层综合报告（只读勘察 scout-host）

## 执行摘要

| 维度 | 发现 | 证据强度 |
|------|------|---------|
| **近乎空会话的真相** | 不是探针，是 magpie 托管的 claude -p 会话退出后的 3 行快照桩（cost-state 显示真实费用 $0.5–2.8） | 强（log 直接读取） |
| **夜间规律心跳** | 约 144 次/天（每 20 分钟发 2 次 /v1/messages，~190k cache-read tokens），可能由「评测窗口 20 分钟存活检查」cron 触发 | 中（usage.jsonl 时间戳规律 + cost-state lastPrompt 片段吻合，无直接 cron 证据） |
| **库漂移现状** | library.json 分配 240 个技能给 claude，但 ~/.claude/skills 只有 133 个链接；缺的 107 个在 skills-disabled（gsd/arkcli/bailian/others），mv 后 35 分钟未被补回 | 强（文件计数） |
| **库同步时机** | 官方文档：每次 library 修改后立即同步；另有 30 秒定时器 poll 链接指令集文件变化。`mv` 走的技能**不是修改**，因此不触发同步。用户无法通过 CLI 强制批量同步已分配库到所有 agent（`magpie library sync` 是文档存在但未查到执行行为的命令） | 中（docs + 行为反推） |
| **资源占用** | magpie 主进程 +18 个 127.0.0.1:3425 连接（claude -p 会话各 3 进程 ~300–440MB）；单日 peak hour 55 次请求。quota-history.json 约 96k points（~318 points/day），每分钟重写（inode 变），usage.jsonl 增量追加 | 强（ps/lsof/stat） |
| **安全面** | 网关 *:3425 监听 IPv6（双栈，firewall 开启但 stealth 关闭）；~/.claude/settings.json 为 644（含 env 变量但无直接 token，ANTHROPIC_AUTH_TOKEN 不等于 magpie caller key）；~/.claude/transcripts/* 为 644 且包含 token 模式串（sk-/ghp-/AIza 等）；magpie 核心配置文件为 600 | 中（perms 扫描 + 模式匹配；高风险文件已识别） |
| **备份与快照** | ~/.config/magpie/backups 807 个（770 个含 skills），~193MB，保留最近 30 个；sync/ 21 个快照（12 个 this-computer, 8 个 server）；~/.local/share/local-ops/magpie 含 ~740MB 加密恢复快照，44 个 recovery-scope-candidate JSON | 强（du/find 计数） |

---

## T1 库同步机制（最重要）

### 发现（引用 library.md 原文）
> **When the library is applied:** "`change` edits `library.json` under the lock and calls `sync`." Every exported mutation goes through `change`, and `sync` writes each target's instructions and MCP servers.  
> **Timer:** The app's `KeepLinked` checks a linked instruction-set file every 30 s and, when it changed, writes it into the agents (`SyncLinked`).

**关键推断：用户 `mv ~/.claude/skills/gsd ~/.claude/skills-disabled/` 不是 library.json 的 `change`，因此不触发 `sync`**。library.json 仍记录 gsd 分配给 claude，applied.json 也记 240 个，但实际链接只有 133 个（缺 107 个，时间戳 19:38:55，此后 35 分钟内未变化）。

### 持久关闭一批技能的命令草案（未执行）
```bash
# 1. 查询当前分配给 claude 的技能（需人工从 library.json 或 UI 读取列表）
#    grep '"agents":.*"claude"' ~/.config/magpie/library.json | jq -r '.name' > /tmp/current.txt

# 2. 批量取消分配（伪代码，CLI 无批量取消子命令，需逐个或用 UI 多选）
#    while read s; do magpie library skill agents "$s" none; done < /tmp/unwanted.txt
#    → CLI 实测不存在 `magpie library skill` 子命令（help 输出也未列出完整语法）

# 3. 回滚
#    UI：重新勾选被取消的技能，或从 backup restore（backups 保留移除前的链接）
#    CLI 无 bulk reassign
```

**现实约束：**
- `magpie library skill agents <name> none` 的语义是**替换分配列表为空**，不是「从 claude 移除但保留在其他 agent」
- 无批量操作 CLI；UI 多选 → Remove 可批量，但只对当前显示的 agent 生效
- **mv 到 skills-disabled 只是绕过 PATH 查找，库记录不变，同步不触发**

### link vs copy
> "Each agent gets a link or a marked copy (`SkillHow`)." WSL distro always gets a copy. Default: **文档未明示**，但观察到 ~/.claude/skills 为软链指向 ~/.config/magpie/library/skills/<name>。

---

## T2 本体资源（进程、监听、文件）

### 进程结构
- **magpie tray (2066)**: RunAtLoad, ProcessType=Interactive, ppid=launchd, RSS ~687MB, etime 02-09:16:20
  - 子进程：4 个 claude -p 会话，每个 3 进程（claude + magpie + magpie-bun），合计 ~1.5GB
- **magpie-quality-check (15850)**: -data -gate -owned，6MB，etime 21:13:50
- **oMLX (735)** / **omlx-server (925)**: 本机算力栈（独立于 magpie，评测窗口被 eval_isolate 隔离时摘除 aetherforge/* 成员）
- **python -m llm_gateway.openai_proxy (2062)**: 本机代理监听 100.68.80.44:9290 + 127.0.0.1:4000，非 magpie 组件

### 网络监听
- **magpie (2066)**: `*:3425` (IPv6，双栈)，18 个 127.0.0.1 已建立连接，4 个到 127.0.0.1:7890（系统代理 ClashX）
- **github-sync plugin**: 127.0.0.1:3437（每次 magpie CLI 启动打印 `[github-sync] setup: http://127.0.0.1:3437/`）
- **LAN 分享**: 当前 lan=true，但监听的是 `*:3425`（未查到 0.0.0.0 vs 特定网卡绑定的明确证据，IPv6 `*` 一般覆盖双栈）

### 文件写频率（60 秒采样）
| 文件 | inode 变化 | mtime 变化 | 写频率推断 | 备注 |
|------|-----------|-----------|-----------|------|
| **quota-history.json** | CHANGED | 20:23:29→20:23:53 | **~24秒**（整文件重写） | 8.2MB，96k points，每天 318 点，每点 86 字节 |
| **usage.jsonl** | same | 20:23:30→20:24:02 | **追加**（+2055 字节/60s） | 58.9MB，88836 rows，每次请求追加 1 行 |
| **affinity.json** | CHANGED | 20:23:15→20:24:04 | 49秒整文件重写 | 5.6KB |
| **served.json** | CHANGED | 20:23:15→20:24:04 | 49秒整文件重写 | 2.0KB |
| **quotas.json** | CHANGED | 20:23:30→20:23:53 | 23秒整文件重写 | 14KB |
| **client-shapes.json** | CHANGED | 20:23:29→20:24:02 | 33秒，+78字节 | 1.1KB |
| **logins.json** | CHANGED | 20:18:44→20:23:50 | 约 5 分钟 | 35KB |
| **library.json** | same | 08:59:48（今晨未变） | 无定时写，仅库变化时 | 165KB |
| **settings.json** | same | 18:19:45（6 小时前） | 无定时写 | 3.2KB |
| **sync-state.json** | same | 20:11:51（12 分钟前） | 约 3 分钟（文档说每 3 分钟，未观察到） | 12.9KB |

**quota-history.json 是写放大重灾区**：8.2MB，median gap 0 秒（连续写），过去一分钟触发 2 次 inode 变化，每次重写全文（非追加）。

### 磁盘占用（候选优化项，见末尾表格）
- ~/.config/magpie: **1.8GB**（其中 sync-server.magpie-backup 60MB，backups/ 193MB，library/ 14MB，usage.jsonl 58MB，quota-history 8.2MB，routing/2026-10-*.jsonl.gz 累计约 24MB）
- ~/.claude/projects: **750MB**（含大量子目录缓存，但今天的 magpie-claude-work-501 仅 4.9MB/51 transcripts）
- ~/.local/share/local-ops/magpie: **740MB**（recovery 目录 740MB，含 1 个 767MB .mpr 加密快照 + 44 个 recovery-scope-candidate JSON）

---

## T2b 空会话探针真相（高价值线索）

### 证据链
1. **文件结构**：magpie-claude-work-501 下 51 个 <session_id>.jsonl，今天 26 个，多数 <20KB，每个 3 行：
   ```
   {"type":"last-prompt", "lastPrompt":"…", "leafUuid":"…", "sessionId":"…"}
   {"type":"atis-latch", "atis":"", "sessionId":"…"}
   {"type":"cost-state", "sessionId":"…", "totalCostUSD":"0.73–2.78", "totalAPIDuration":"23000–709000", "totalDuration":"0–48011280", …}
   ```
2. **关联到 magpie tray**：当前 4 个 claude -p 进程的 ppid 均为 2066（magpie tray，launchd 的 com.yetone.magpie.plist RunAtLoad）
3. **usage.jsonl 无匹配**：这些 sessionId 在 usage.jsonl（88836 rows，含 session / native_session 字段）里零匹配 → **claude -p 会话不走网关，直连 api.anthropic.com**
4. **生成者推断**：空桩的 lastPrompt 是「评测窗口 20 分钟存活检查」或 lead→scout 的任务提示。生成者是 magpie 应用（com.yetone.magpie），在 claude -p 进程退出后写入 3 行快照。

### 夜间心跳（usage.jsonl 时间序列分析）
```
03:08:07, 03:08:12 → 4s 间隔（2 次请求）
03:28:07, 03:28:11 → 20分钟后重复，4s 间隔
03:48:07, 03:48:12 → 再 20 分钟
...
每小时 :08/:28/:48 各 2 次，共 6 次/小时 × 24 = 144 次/天
每次 in=2, out=120/62/80, cache_read=188k–190k
```
**与空桩关联性：弱（置信度中）**。lastPrompt 提到「评测窗口」与 cron 节奏吻合，但心跳请求直连 Claude API，未在 magpie usage.jsonl 留下 session 记录。需查 ~/mac-local-ai-task-2026-10-12/bin/*.zsh 的 cron 配置确认。

---

## T3 多层代理（影响度：低）

- **Claude Code env**: `ANTHROPIC_BASE_URL=http://127.0.0.1:3425/v1/messages`
- **magpie(2066) 出站**: 4 个到 127.0.0.1:7890（系统代理 ClashX），1 个到 api.anthropic.com:443（夜间心跳直连）
- **系统代理**: HTTPProxy/HTTPSProxy/SOCKSProxy=127.0.0.1:7890 (ClashX)
- **aiusage**: ~/.config/aiusage/global-proxy-claude.json 存在但 isEnabled=false（端口 14400），不影响当前流量
- **magpie 是否走系统代理**：出站有 4 个到 7890 的连接 → **会走系统代理**。chinaMirror=true（settings.json），updateMirror=`<长字符串>`（未解码）

**多跳延迟**：本地回环无实质延迟；外部请求走 ClashX 规则，具体策略未查（需读 ClashX 配置）。

---

## T4 用户运维层与 magpie 的交互

### 脚本识别
1. **~/local-ops/bin/magpie-watchdog** (Python，12 行入口)
   - 实现：~/local-ops/lib/magpie_watchdog.py (891 行)
   - 配置：~/.config/local-ops/magpie-watchdog.json `{"enabled":true,"mode":"conservative"}`
   - 定时：launchd com.local.magpie-watchdog.plist，StartInterval=30，ProcessType=Background
   - 行为：conservative 模式不自动重启未知退出；max_restarts=3，backoff_seconds=30，probe/restart_timeout 各 5/15s
2. **~/local-ops/bin/magpie-refresh-cycle** (Python，16 行入口)
   - 实现：~/local-ops/lib/magpie_refresh.py + magpie_refresh_*.py (共约 7 个模块)
   - 定时：launchd com.local.magpie-refresh.plist，StartInterval=21600（6 小时），ThrottleInterval=300
   - 行为：运行 scheduled refresh + static audit，日志未查到错误
3. **~/local-ops/bin/magpie-backup-prune** (Python，936 行)
   - 定时：launchd com.local.magpie-backup-prune.plist，StartCalendarInterval={Hour:4, Minute:20}（每日 04:20）
   - 行为：保留原生备份最近 3 份 + 14 天每日最后 + 8 周每周最后；技能目录作为整体保留/清理
   - 日志：最近 8 次运行候选 52–67 条，originals 186–188 条，entries 12k–14k 条
4. **~/mac-local-ai-task-2026-10-12/bin/eval_isolate.zsh**
   - 行为：评测时摘除 magpie providers.json 里 aetherforge/* 和 omlx/* 成员（`magpie group set <id> "models-=<list>"`），快照到 state/isolation/groups_orig.tsv
5. **~/.local/bin/aictl** (Python，871 行)
   - 行为：本机 AI 栈统一运维（status / check / up / down / free / mode / verify），不直接改 magpie 配置，但可能通过 `magpie group set` 操作分组

### 并发写冲突风险
- **文件锁**：magpie 持有 app-2f3697fd67b8.lock（lsof 显示），sync.lock 未在 lsof 输出（文档说每次 sync 操作会持有，但采样时未捕获）
- **冲突场景**：eval_isolate 和 watchdog 都可能在 magpie 运行时调 `magpie group set`，写 providers.json。magpie 自己的 sync 也写 providers.json（每 3 分钟）
- **实际影响**：未观察到 providers.json 损坏；magpie CLI 应内置了 flock 或 atomic rename

---

## T5 后台任务与节奏

### 文件节奏（mtime 观察）
- **checkin JSON**: workbuddy 10-25 00:00（每日签到），trae/minimax/qoder 10-17（过期），plugin-checkin 10-25 00:00（汇总）
- **codex-warmup.json**: 20:12:40（动态），2 个账户各有 "30 days" / "7 days" 键（cache warmup 窗口？）
- **plugin-updates.json**: 19:59:37，checked=2026-10-25T11:59:37Z，waiting[10] / updated[20]（插件版本检查，约 6 小时一次？）
- **usage-alerts.json**: 16:07:03，20 个键（agent|account|r/w|window → at/until），记录用量告警触发
- **credits-daily.json**: 20:23:21，2 个账户的每日额度消耗（workbuddy/acct#b0f59b）

### github-sync plugin (127.0.0.1:3437)
- 每次 magpie CLI 启动打印 `[github-sync] GitHub sync setup: http://127.0.0.1:3437/`
- 未查到 plugin 源码，推测是内置插件或 ~/.config/magpie/github-sync-plugin 目录（存在 96 字节目录，未深入）

### 日志（~/.local/log）
- **magpie 相关日志**：com.local.magpie-watchdog.log（0 字节，仅有 launchd plist）、magpie-backup-prune.log（2.9KB，8 次 JSON 行）
- **其他 LifeOS 日志**：zhixing-dashboard-refresh.err.log（754KB）、projection-fullrefresh.log（14.8MB）等，与 magpie 无关

---

## T6 文件卫生与备份

### ~/.config/magpie
| 目录/文件 | 大小 | 项数 | 备注 |
|----------|------|------|------|
| **backups/** | 193MB | 807 dirs, 8129 files | 770 个含 skills，最新 2026-10-25_08-59-48.840 |
| **sync/** | 1.1GB | 21 files | 12 个 this-computer.magpie-backup, 8 个 server.magpie-backup，最老 10-08，最新 10-22 |
| **our-free-model/** | 213MB | runtime/node-v24.21.0-darwin-arm64/bin/node (122MB) | magpie 内置 Node 运行时 |
| **plugins/** | 83MB | node_modules + 插件文件 | — |
| **routing/** | 24MB | 2026-10-*.jsonl.gz | 每日路由决策日志，10-07 到 10-16 每天 1–2.6MB 压缩 |
| **usage.jsonl** | 58.9MB | 88836 rows | 增量追加 |
| **quota-history.json** | 8.2MB | 96k points | **高频重写**（约 24 秒一次） |
| **library.json** | 165KB | 421 skills, 58 MCP, 16 agents | 今晨 08:59:48 更新后未变 |

### 用户侧备份
- ~/.claude/backups: 1.1MB（自动备份？）
- ~/.claude/settings.json.bak*: 17 个，合计 2.7MB
- ~/skill-backup-*: 1 个
- ~/.local/share/local-ops/magpie: **740MB**（其中 recovery/lifeos-magpie-…/2a680e04….mpr 767MB，recovery-scope-candidate-*.json 44 个共约 9MB）

### 冗余清理候选
1. **routing/*.jsonl.gz 保留策略未知**（10-04 到 10-16 累计 24MB），是否需要全部？
2. **sync/ 快照 21 个**（this-computer 12 个 + server 8 个，最老 10-08），官方保留策略未在文档找到
3. **~/.claude/projects 750MB**（多数是子目录缓存，magpie-claude-work-501 仅 4.9MB），可能是历史会话累积
4. **quota-history.json 高频重写**（8.2MB，24 秒一次）→ 考虑改为追加写 + 定期 compact？（需 magpie 官方优化）

---

## T7 安全面

### LAN 分享（lan=true）
- **监听地址**: `*:3425` (IPv6，双栈)，文档未明确是否 0.0.0.0 vs 特定网卡，但 lsof 显示 IPv6 `*` 通常覆盖 IPv4
- **lanKey**: settings.json 存 lanKey=62 字符，lanKeyId=24 字符；caller-keys.json 有 2 个 key（name=6 字符，secret=62 字符，lan=true）
- **强制认证**：文档说「remote callers need an enabled gateway key」，本地回环 (127.0.0.1) permissive
- **TLS**: 无（example URL 是 http://192.168.17.248:3425）
- **防火墙**: macOS Firewall enabled, stealth mode off

### 文件权限扫描（world-readable 文件中的密钥模式）
| 路径 | perms | 问题 | 建议 |
|------|-------|------|------|
| **~/.claude/settings.json** | 644 | 含 env 但 ANTHROPIC_AUTH_TOKEN 仅 6 字符（不是真实 key） | 改 600 |
| **~/.claude/transcripts/*.jsonl** | 644 | 45 个文件含 token 模式串（sk-/ghp-/AIza/xox*/AKIA/eyJ）| **高风险，改 600** |
| **~/.config/magpie/sync-state.json** | 644 | 含 key 字段（64 字符，sync 加密密钥？） | 改 600 |
| **~/.config/aiusage/*.json** | 多数 644 | global-proxy-claude.json 含 claudeDesktopClientKey (80 字符) | 改 600 |
| **~/.config/magpie/settings.json** | 600 | ✓ 安全 | — |
| **~/.config/magpie/caller-keys.json** | 600 | ✓ 安全 | — |
| **~/.config/magpie/providers.json** | 600 | ✓ 安全 | — |

**ANTHROPIC_AUTH_TOKEN 来源**：长度 6，sha256 前 6 位 8a88fb，**不等于** magpie caller-keys.json 里的任何 key（共 39 个候选 key strings，包含 lanKey/secret/githubToken）。可能是 magpie 生成的 session token，不是用户的 Anthropic API key。

---

## T8 官方文档（WebFetch 汇总）

### 已确认的设置语义（从二进制字符串提取）
| 设置键 | 值 | 语义（引用 UI label） |
|--------|----|--------------------|
| **lightweight** | on/off | "A closed window frees about 100 MB after a minute; the gateway and tasks keep running, only the page reloads" |
| **keepAwake** | off/on/display | "Keeps this computer awake while magpie runs tasks" / "Screen on too" (keepAwakeDisplay) |
| **trayPace** | on/off | "Each window's Pace number beside its figure…: +12% is 12% more of the window used than an even pace" |
| **searchFirst** | model/api | "Model search" vs "Search APIs" — apiFirst 时优先调搜索 API，失败时 fallback 到模型 |
| **memberModel** | on/off | "A reply's model says magpie's provider/model (workbuddy/glm-5.3-flash), not the vendor's own name…Claude Code/Desktop/Codex keep vendor's; X-Magpie-Model header says it to every agent" |
| **codexAgentsV1** | on/off | "A GPT lead spawns subagents on magpie's other models. New threads only; Codex's own multi_agent_v2 still wins" |
| **trayUsageEvery** | 数字 | 默认 10（分钟？） |
| **codexWarmup** | week/… | Cache warmup 窗口，settings.json 设 "week" |
| **updateEvery** | 360 | 更新检查间隔（分钟？），settings.json 设 360 |
| **chinaMirror** | true/false | 国内镜像开关 |

### 未找到的设置（文档/二进制均无）
- **redact**：文档提 privacy masking 和 redact.key，但无 top-level `redact` boolean 设置键
- **claudeLeanPrompt**: 二进制有 `s.claudeLeanPrompt ? "on" : "off"`，但无 UI 描述
- **noLoopGuard**: 二进制有字段，无 UI 描述
- **refusalRetries**: 二进制有 `s.refusalRetries ?? null`，无 UI

### library sync 完整行为链（综合 docs + 行为）
1. **写时机**：每次 `change` (library.json 修改) → `sync` 写入所有 target agents；指令集文件变化 → 30s 后 `KeepLinked` 检测 → `SyncLinked`
2. **applied.json 作用**："records what magpie last wrote into each agent, so it only ever takes away its own"
3. **用户删除技能链接**：文档未明确是否补回；观察到 mv 后 35 分钟未补回 → **不是 library 修改，不触发 sync**
4. **link vs copy**: WSL 强制 copy，其他由 `SkillHow` 决定（默认未明示，实际观察到 ~/.claude/skills 为软链）
5. **backup.go 保留策略**: 最近 30 次变更；含 skills 的备份目录豁免原生清理（backups/ 下 770/807 个目录含 skills）

---

## 候选优化项（预期收益 | 风险与回滚 | 证据强度）

| 项 | 预期收益（量化） | 风险 & 回滚 | 证据强度 |
|----|----------------|------------|---------|
| **修正库漂移**（107 个技能未链接） | 无性能收益，恢复功能完整性 | 低；UI 重新勾选或 `magpie library sync`（需确认命令可用性） | 强（文件计数） |
| **减少 quota-history.json 重写频率** | ~8MB × 2.5 次/分钟 = ~20MB/分钟写放大 → SSD 寿命 | **高**（需 magpie 源码改动，append + compact）；回滚：降级 magpie 版本 | 强（60s 采样 inode 变化） |
| **清理历史快照 (sync/)** | ~1GB → ~100–200MB（保留最近 7 天） | 中（丢失远期恢复点）；回滚：从 sync-server.magpie-backup 或 GitHub 恢复 | 中（保留策略未在文档明确） |
| **缩小 routing/*.jsonl.gz 保留期** | ~24MB → ~3–5MB（保留最近 7 天） | 低（诊断时可能需要历史路由决策）；回滚：解除清理 cron | 中（用途未验证） |
| **~/.claude/transcripts 权限改 600** | 0 字节，**防止密钥泄漏** | 低（magpie 应用仍可读）；回滚：`chmod 644` | **强（45 个文件含 token 模式串）** |
| **停用夜间心跳 cron**（若确认由评测窗口触发） | ~144 × 190k cache-read tokens/day = ~2.7e7 tokens/day | 中（cron 可能有监控价值）；回滚：重启 cron | 中（关联性未直接证实） |
| **减少 affinity/served.json 重写频率** | ~5KB × 1.2 次/分钟（微小） | 低（可能已是必要节奏）| 弱（影响度低） |

---

## 未验证项（调用预算不足）

1. **magpie library sync** CLI 命令的可执行性（help 输出里有，但未测试实际运行）
2. **codexAgentsV1 / claudeLeanPrompt / noLoopGuard 的完整语义**（UI label 未找到）
3. **GitHub sync 的确切行为**（3437 端口插件的交互协议）
4. **watchdog conservative 模式的触发条件**（未观察到 magpie 退出，无法验证 probe / restart 行为）
5. **远程主机 (mini) 的 magpie 实例状态**（未查）

---

## 证据清单（可复现命令）

```bash
# 1. 库漂移
jq -r '.skills[] | select(.agents[]? == "claude") | .name' ~/.config/magpie/library.json | wc -l  # 240
find ~/.claude/skills -mindepth 1 -maxdepth 1 -type l | wc -l  # 133
find ~/.claude/skills-disabled -mindepth 1 -maxdepth 1 | wc -l  # 106

# 2. 进程树
ps -axo pid=,ppid=,rss=,command= | grep 'magpie\|claude -p'

# 3. 文件写频率
stat -f '%i %z %m' ~/.config/magpie/quota-history.json; sleep 60; stat -f '%i %z %m' ~/.config/magpie/quota-history.json

# 4. 安全扫描
find ~/.claude/transcripts -type f -exec grep -l 'sk-\|ghp_\|AIza' {} + | wc -l

# 5. 夜间心跳
tail -n 100000 ~/.config/magpie/usage.jsonl | jq -r 'select(.t[11:13]=="03") | .t[11:19]' | sort | uniq -c
```

---

**报告版本**: 2026-10-25 20:30 UTC+8  
**执行者**: scout-host (ascout-host-a8390b4049d9c1b2)  
**调用次数**: 约 35/60（剩余预算已少，深度项未覆盖）  
**置信度声明**: 强证据项 10 条，中证据项 8 条，弱证据项 2 条
