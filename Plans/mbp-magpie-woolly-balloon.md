# mbp ↔ Mac mini 配置同步落地计划

> **状态 (2026-10-10 复盘)**: 全部落地。后续追加: SwiftBar mini 四域适配 · SYNC-MATRIX v1 · SharedConf 迁 git (决策 A, dotfiles/sharedconf + 凭证契约) · brief 刷新链四层断根修复 (决策 B, zhixing-dashboard PR #19 + launchd 常驻) · 双机命名规范 (mbp / Mac-mini, .host 锚定)。挂账: DeepSeek key 轮换 (P0)。
> Phase 6 产物: ADR-0465 + debt O-BROKEN-LAUNCHAGENT-OMO-SYNC + 3 处旧 IP 修复，
> worktree 分支 work/mbp-mini-sync @ ae5e3779d（proposal-only，待用户审批 push/PR/merge）。

> 本文件原为「修复 LifeOS Pulse」计划——该任务已于 2026-10-09 完成并实测验证（Pulse RUNNING、端口 31337 监听、skill-guard/agent-guard 均 200）。现按用户新指令「规划并确保落地」重写为 mbp↔Mac mini 同步方案。

## Context

用户原始需求（另一会话 `741c16fa` 全文已合并）：本机与 mbp 做好配置同步，**以 magpie 作为模型管理核心**；把 MBP 上的 SwiftBar 装到 Mac mini 并同步数据；全面梳理两机同步面，找**持久化、可观测**的管理机制；评估现成工具（iCloud 等）。另一会话尚未动手，建议由本会话独占执行。

**关键实测事实**（设计 agent 经 SSH 到 MBP 复核）：
- 本机 = Mac mini（M4 Pro/24G/macOS 27.0，Tailscale 100.99.210.78）；对端 mbp = `macbook-pro-brew`（100.68.80.44，用户确认；macbook-pro-2014 排除）
- SSH 密钥认证 mini→MBP 已通（BatchMode 免密）；MBP 有 brew(208 formulae)/rsync/git；MBP 主机名当前为 `localhost`（需 `scutil --set` 固化）
- MBP 已装 magpie 且 sync 已配置——usage 目录两个设备哈希证明**两机 magpie 已在实际同步**；MBP settings.json **无** DEEPSEEK 明文 key（外溢未发生，保护窗口）
- 两机 LifeOS 同版本 7.40.4（pinnedVersion/commit 一致）
- SwiftBar 在 MBP：插件实体在 `~/.config/menubar/`（hub.30s.sh "Fleet Hub v2"+parts/+bar-lint.sh，活跃编辑中，非 git），`~/.config/swiftbar-plugins/` 仅符号链接；mini 两者皆无
- 本机 iCloud 桌面/文稿同步结构已坏（偏好开但 ~/Desktop 是真实目录）——不可依赖
- `com.l4.omo.sync` LaunchAgent 崩溃循环（uv 把目录当子命令），且语义是治理状态自记录非文件同步 → 删
- glm 覆盖根因：glm env 在源头 `settings.user.json`（32-44 行），被覆盖是因为手改了生成文件 `settings.json`（SessionStart 钩子 MergeSettings 回写）——流程缺陷，本方案顺带根治

## 方案选型（用户要求的工具对比结论）

| 工具 | 判定 |
|---|---|
| iCloud | ❌ 实测结构坏；330M MEMORY 必演化冲突副本；明文上云 |
| Chezmoi+age | ❌ 不整装复活（hw-05 先例已 archived，全盘复活带入过期假设）；**吸收三件套**：hostname 模板化、密钥永不进仓、私有 git 仓 |
| Syncthing | ❌ 双向持续同步对「生成文件 + magpie 写入面」是冲突放大器 |
| Mackup | ❌ 覆盖面窄，symlink 模式依赖已坏的 iCloud |
| Nix-darwin | ❌ v1 不做（两机 178/208 手装包，重造成本不匹配）；吸收 Brewfile 基线思想 |
| **git 私有仓 + rsync over Tailscale SSH + launchd 巡检 + SwiftBar 出口** | ✅ **推荐**：工具零新增、通道现成、显式单向+排除消灭冲突类、可观测直接复用仓库既有 pattern |

## magpie 边界契约（写冲突防线）

| 内容 | 归属 |
|---|---|
| `~/.config/magpie/**`（sync/quotas/logins/providers/library/backups） | magpie 独占；本方案任何脚本/manifest/备份**排除** |
| `~/.claude/CLAUDE.md` 的 magpie:begin/end 块 | magpie 独占（整个文件不同步） |
| `~/.claude/settings.json` | 生成文件，不同步，只做「生成链一致性」巡检 |
| `settings.user.json`（glm 路由 + 密钥源头） | **收进 dotfiles 仓（脱敏后）**——glm 问题根治点 |
| AI 客户端配置/skill 分发、provider key 跨机流动 | 全归 magpie（用户指定核心），不重复造分发器 |
| MEMORY(330M)/PULSE(104M)/会话数据 | 机器本地，永不同步 |

## 分层同步范围

| 层 | 内容 | 方向/机制 |
|---|---|---|
| L1 AI 工具链 | `settings.user.json`(脱敏)/`LIFEOS_CONFIG.toml`/`OPERATIONAL_RULES.md` | 双向 git；USER 其余（TELOS 等 ~1.2M，排 CACHE/*.bak*）mini→mbp 单向 rsync；LIFEOS 系统目录（TOOLS/RULES 等）与 releases **只校验不复制**（不一致→落后机重跑 LifeOS 更新） |
| L2 终端 | `.zshenv/.zprofile/.zshrc/.gitconfig` + `zshrc.d/<hostname>.zsh` 分支 | 双向 git+软链农场；Brewfile 按机两文件（`brew/Brewfile.Mac-mini` / `Brewfile.mbp`，首版仅基线） |
| L3 菜单栏 | `~/.config/menubar/` 收编进仓；SwiftBar cask 装 mini | git 双向；MBP 为初始源；mini 建 `~/.config/swiftbar-plugins/` 链接 + defaults PluginDirectory |
| L4 Workspace | 内容不 rsync（GitHub remote 天然覆盖，16 子模块） | 可选 submodule 指针校验 |
| L0 通道 | `~/.ssh/config` 加 `Host mbp/mini`（用 MagicDNS 名，IP 变更免改） | BatchMode 密钥（已通） |

## Secrets 先行（Phase 1，早于一切同步落地）

DEEPSEEK_API_KEY 六步（顺序不可倒）：
1. **用户在供应商标台签发新 key（不吊销旧）** ← 唯一用户手工步
2. 两机 Keychain：`security add-generic-password -U -a "$USER" -s DEEPSEEK_API_KEY -w <NEW>`
3. dot/zshenv 注入 `export DEEPSEEK_API_KEY="$(security find-generic-password -w -s DEEPSEEK_API_KEY 2>/dev/null)"`；新终端实调验证
4. `settings.user.json` 摘除明文（Python read→check→modify→write，自动留 `.pre-keychain-bak`；禁 sed -i）；触发重生成后验证 settings.json 无 `sk-` 且 magpie 代理对话正常
5. 供应商标台吊销旧 key
6. 清 `USER/CONFIG/*.bak*` 残留（确认列表后删）

回退：④ 异常 → 恢复 `.pre-keychain-bak` 重开会话；keychain 在 ssh/launchd 触发解锁弹窗 → 降级 `~/.config/secrets.env`（chmod 600、永不进仓、不进同步）。**MBP 全程不接触明文**。
magpie 域内凭证（sync.json 的 password/passphrase 等）：不迁不动不扩散（可选加固：走 magpie UI 改 passphrase，非关键路径）。

glm 根治三招：源头进 git（改动有 diff 可回滚）+ drift 巡检规则「settings.json 手改检测」+ CONFIG 目录加警示 README。

## 执行阶段（每阶段独立验证/回退，可停点；总量约 1.5-2 个工作日）

### Phase 0 通道与基线（~1h）
- 双机 `~/.ssh/config` 各加 `Host mbp` / `Host mini`（MagicDNS 名 + IdentityFile + ServerAliveInterval）
- 验证双向 BatchMode OK（反向 MBP→mini 若不通：比对 MBP 公钥与 mini authorized_keys，不在则追加——Phase 0 唯一状态变更）
- 两机 manifest 基线（sha256 清单，排除 magpie/CACHE/*.bak*/MEMORY/PULSE）+ premigration 本地备份（rsync 到 `~/.local/share/dotfiles-sync/premigration/`）
- 验证：双向 `ssh … 'echo OK'`；manifest 非空。回退：删 config 追加段

### Phase 1 Secrets 治理（~1h，见上节）
- 验证：settings.json 无 `sk-`；`rg -rl 'sk-5e4d' ~/.claude` 为空；新终端 deepseek 实调成功；MBP 侧恒为空

### Phase 2 dotfiles 仓 + 终端层（~3h）
- mini 建仓：`mkdir -p ~/dotfiles/{dot/lifeos,dot/config,bin,launchd,brew,docs}` → `gh repo create starlink-awaken/dotfiles --private --source=. --push`（**创建/推送前向用户确认**）
- MBP 先 `scutil --set HostName/LocalHostName macbook-pro-brew`（避免 "localhost.zsh"）
- shell 四件套迁入 `dot/` + zshrc 尾部 `source ~/.zshrc.d/$(hostname -s).zsh`（两机分支文件都进仓）
- `bin/apply.sh` 软链农场（幂等；`--revert` 可整体回退：删链接、premigration 备份 mv 回）
- 两机 `brew bundle dump --file=brew/Brewfile.<host> --describe`
- MBP `git clone` + `bin/apply.sh`；小步多 commit
- 验证：两机 `~/.zshrc` 为符号链接；新终端正常；MBP `brew bundle check` 一致

### Phase 3 SwiftBar / menubar（~2h）
- MBP：`mv ~/.config/menubar ~/dotfiles/menubar && ln -s ~/dotfiles/menubar ~/.config/menubar`
- mini：`brew install --cask swiftbar` + `ln -s ~/dotfiles/menubar ~/.config/menubar` + `swiftbar-plugins/hub.30s.sh` 链接 + `defaults write com.ameba.SwiftBar PluginDirectory` + `open -a SwiftBar`（**用户点一次首启授权**）
- parts/ 内主机差异路径加 `hostname -s` 分支
- 验证：两机 menubar 显示 Hub；任一机改 parts 提交→对端 pull 生效。回退：unlink+mv 回原位；mini 卸 cask

### Phase 4 LifeOS 配置层（~3h）
- **差异盘点门**：两机 USER 目录 manifest diff（仅 MBP 有/仅 mini 有/同名异内容三类清单）**给用户过目后才动手**
- 配置三件套进仓 + `~/.claude/LIFEOS/USER/CONFIG/settings.user.json` 符号链接到仓
- `bin/sync-user.sh` 单向上行：`rsync -av --delete --exclude 'CACHE/' --exclude '*.bak*' --exclude 'settings.user.json*' ~/.claude/LIFEOS/USER/ mbp:.claude/LIFEOS/USER/`（先 `--dry-run --itemize-changes`；MBP 侧 `--backup --backup-dir`）
- `bin/sync-drift.py parity`：两机 pinnedVersion / settings.system.json sha / LIFEOS 系统目录 sha 互比，只报告不修复
- 验证：MBP 新会话 SessionStart 正常生成 settings.json（无 sk-）；两机 env 键集合一致；rsync 二次运行为空操作（收敛）

### Phase 5 可观测（~2h）
- `bin/sync-drift.py`（泛化 `bin/gac/zhixing-host-sync.py` 母本）：`capture/check/status/restore`，check 三规则（①settings.json 手改检测 ②两机版本一致 ③仓有未提交改动）→ 原子写 `~/.local/share/dotfiles-sync/drift-report.json`，漂移 exit 1
- launchd `com.local.dotfiles-drift` 每小时巡检（复用 `bin/ops/launchd/com.omostation.zhixing-host-drift.plist` 模板），两机各装（`launchctl bootstrap gui/$(id -u)`）
- `hub.30s.sh` 加「⇄ Sync」菜单段：读 drift-report（漂移数/巡检时间/仓脏文件数），绿/红图标，子菜单含 `sync-user.sh --dry-run`
- 验证：`launchctl kickstart` 后报告 mtime 更新；人为 touch 纳管文件→下轮 exit 1→menubar 变红。回退：bootout + rm plist

### Phase 6 omostation 治理落点（~1h，仓内动作走完整工作流）
- `bin/agent-workflow.py bootstrap` → `bin/gac/gac-worktree.sh claim mbp-mini-sync`
- 新增 ADR（架构选型/magpie 边界契约/分层表/secrets 政策/supersede hw-05）+ debt 条目（com.l4.omo.sync 判删）
- 工具脚本全住 dotfiles 仓，天然绕开仓库「脚本配额 add 1 = delete 1」
- PR 创建/合并**先向用户确认**；合并后 worktree merge/release + `agent-workflow.py closeout`
- 同阶段执行：`launchctl bootout gui/$(id -u)/com.l4.omo.sync && rm ~/Library/LaunchAgents/com.l4.omo.sync.plist`
- 验证：`make gac-local-gate` 绿；ADR 入索引

## 坏件处置

| 项 | 决定 |
|---|---|
| `com.l4.omo.sync.plist` | **删**（uv 传参坏 + 与 magpie/新同步层职能重叠；记 debt） |
| glm 覆盖 | 根治（源头进 git + drift 规则 + 警示） |
| iCloud 结构坏 | 不修（证据入 ADR） |

## 不做清单（v1）

iCloud 任何依赖；MEMORY/PULSE/会话数据同步；接管/改写/备份 `~/.config/magpie/**`；直接同步 `settings.json`/`CLAUDE.md`；Workspace 内容 rsync；明文密钥任何文件级跨机复制；SSH 私钥跨机分发；macOS defaults 同步；引入 chezmoi/syncthing/mackup/nix；macbook-pro-2014 与 Windows 机纳入；Brewfile 反向强制对齐。

## 关键复用文件

- `/Users/xiamingxing/Workspace/bin/gac/zhixing-host-sync.py` — sync-drift.py 直接泛化母本
- `/Users/xiamingxing/Workspace/bin/ops/launchd/com.omostation.zhixing-host-drift.plist` — 每小时巡检 LaunchAgent 模板
- `/Users/xiamingxing/.claude/LIFEOS/USER/CONFIG/settings.user.json` — glm 路由与密钥源头（Phase 1/4 核心对象）
- `/Users/xiamingxing/Workspace/.omo/_archive/infrastructure-history/phase0-硬件基建/hw-05-配置同步与终端环境.md` — 被 supersede 先例，ADR 需引用

## 用户介入点（执行中会显式暂停等待）

1. Phase 1 步①：供应商标台签发新 DeepSeek key
2. Phase 3：mini 上 SwiftBar 首启授权点击
3. Phase 2/6：`gh repo create` / `git push` / PR 创建与合并（按全局规则逐次确认）
4. Phase 4：两机 USER 差异盘点清单过目
