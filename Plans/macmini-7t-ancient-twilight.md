# Mac mini 7T 外接存储长期规划

## Context

mini（M4 Pro / 24G RAM / macOS，永不休眠）挂着 3 块 USB 3.2 Gen2 SSD、5 个 APFS 卷 ≈ 7.1T。用户要求结合 eCOS 架构与三节点算力体系（MBP 128G 权威推理 / mini 轻量并行+向量 / Y7000P CUDA）规划长期利用。

当前核心矛盾：**存量 ~1.1T 模型资产零备份、卷角色漂移、守盘脚本守错盘**。已与用户确认：三块盘**全部常驻 mini**（备份目的地可长期挂载、Docker/向量库可放外接、跨机走 Tailscale 网络）。

规划原则：长期最优架构 + 分阶段落地（先止损、再收敛、后扩能力）；全部收敛到既有 SSOT（vault-paths.yaml / BOSROUTE / BET 台账），不建平行结构。

## 现状事实（2026-10-10 实测）

| 物理盘 | 卷 | 容量/已用 | 现状 |
|---|---|---|---|
| disk4 1T | `Model` | 470G / 438G | 旧模型库，38 处代码引用指向它；`Backup/利用科工作/` 7.4G 敏感明文 |
| disk6 2T | `Lex` | 2T / ~空 | 空卷，可自由规划 |
| disk8 4.1T | `MOVESPEED` | 2T / ~空 | 空卷，可自由规划 |
| disk8 4.1T | `SHAREDWORK` | 976G / ~空 | 空卷（SHAREDMODEL 容器预留 1000G 的另一半） |
| disk8 4.1T | `SHAREDMODEL` | 1000G / 664G | 新模型库（LM Studio 下载目录 + Ollama 模型软链 + Docker DataFolder 都已指向它） |

异机侧（MBP，权威推理节点）：2T SSD（自带模型库）+ **1T HDD**（机械盘，天然适合追加式冷备档案库，不适合随机读写热层）。

关键缺陷（证据）：
- **零备份**：Time Machine 目的地是坏配置（指向 "Macintosh HD / Local" 自身）；`bin/ops/cold-backup-drill.sh` 未排程、且 **gpg 未安装**当前跑不了。
- **守盘脚本守错盘**：`~/bin/disk-keepalive.sh:21,37` 硬编码 `disk4`，设备号已漂移（现 disk4=Model 盘，SHARED* 在 disk10），日志 36 次 REMOUNT FAILED + 63 次 NEEDS_ATTENTION 全是噪音。
- **全部外接卷未加密** + Spotlight 开着（索引churn）。
- 模型存量分裂：Model 438G ↔ SHAREDMODEL 664G，两处重复（9-14 用户已要求 Model→SHAREDMODEL 迁移，未收尾）。
- vault-paths.yaml 声明的 `sharedwork_root`/`shareddisk_root` 与实际卷名不符（`/Users/SharedWork`、`/Volumes/SharedDisk` 不存在）。

## 目标架构：卷角色分配（终态）

```
内置盘        系统 + 代码仓 + models-active 软链农场（现状不变，24G RAM 尽量留内存）
SHAREDMODEL   模型热/温层唯一 SSOT（LM Studio + Ollama + mlx 权重）  bos://shareddisk/model
SHAREDWORK    跨机工作区数据（敏感工作文档、共享语料）                bos://shareddisk/work
Model 1T      Time Machine 目的地（mini 内置盘备份）+ 迁移期中转
Lex 2T        离线冷备份档案库（GPG 加密冷备 --target，重建为加密 APFS 卷）
MOVESPEED 2T  模型冷层 + 数据集/大文件 scratch
MBP 1T HDD    异机副本目的地（冷备档案镜像 → 3-2-1 灾备闭环）
```

跨机（MBP/Y7000P）访问一律走 Tailscale + SMB/rsync 到 SHAREDWORK，不再拔盘搬动。备份遵循 3-2-1：① 运行数据（mini 内置/SHAREDMODEL）② 本地冷备（Lex）③ 异机副本（MBP HDD，经 Tailscale 推送加密档案，机械盘只做追加写入）。

## 分阶段路线图

### P0 安全止损（本周，风险低）

1. **修 disk-keepalive**：按卷 UUID（`diskutil info -plist` 的 VolumeUUID / APFSVolumeUUID）解析设备而非 `disk4` 硬编码；清掉 stale 的 `NEEDS_ATTENTION`；保留其安全挂载检查骨架（那是好的设计）。
2. **装 gpg**（`brew install gnupg`）→ 跑 `bin/ops/cold-backup-drill.sh --target /Volumes/Lex/... --dry-run` 验证链路 → 首次真跑；产物随手 `rsync` 一份到 MBP 1T HDD（当前 7T 资产零异机副本，这是最低成本的即时止损）。密钥口令经环境变量传入，不落盘不打印。
3. **清 Time Machine 坏目的地**（`tmutil removedestination`，需确认）——P1 模型迁完后再把 Model 卷设为新目的地。
4. **敏感文档处置**：`/Volumes/Model/Backup/利用科工作/` 7.4G 明文 → GPG 加密归档进 Lex 冷备（源文件保留，不删）。
5. **Spotlight 关闭外接卷索引**：`sudo mdutil -i off /Volumes/{SHAREDMODEL,MOVESPEED,SHAREDWORK,Model}`（需确认）。
6. **Lex 重建为加密 APFS 卷**（可选项，需单独确认——不可逆，但卷是空的，成本≈0）。

### P1 存储收敛（2–4 周，中风险，走 ADR-0203 workflow）

执行前 `uv run --with "pyyaml" python bin/agent-workflow.py start <id> --profile <agent> --bet <BET-ID>`，新 BET 登记进 `docs/plans/3y-bet-ledger.yaml`（Y2Q4），债务项进 `.omo/debt/items/`。

1. **完成模型迁移 Model→SHAREDMODEL**（用户 9-14 已定的方向）：
   - `rsync -n` / `rclone check` 先出差异清单，去重后分批拷贝；
   - 改 `projects/omlxc/conf/models.json`（disabled.vision-nemotron-omini 等指 Model 的路径）→ SHAREDMODEL；
   - 跑 `omlxc models reconcile` 对账；
   - 38 处 `/Volumes/Model` 引用改为经 `protocols/vault-paths.yaml` 的 `sharedmodel_root` 解析（代表性落点：`projects/omlxc/bin/omlx`、`omlx-node-setup.sh`、`omlx-dashboard`、`omlx-gw-guard`、`scripts/full-status.sh`、`pipeline-watchdog.sh`、`projects/cockpit/src/cockpit/web/api_compute.py:191`、`projects/aetherforge/packages/gateway/src/llm_gateway/gateway.py:296`、`projects/ecos/src/ecos/l0/constraints.yaml:669`、`projects/ecos/scripts/catalog-daemon.py:38`、`bin/delegation-alias-check.py:202`）；
   - 同步更新 MOF：`projects/ecos/src/ecos/ssot/mof/m1/bosroute/BOSROUTE-SHAREDDISK.yaml` 等 4 个文件的 `storage:` 字段与卷名对齐；
   - vault-paths.yaml：`sharedwork_root`→`/Volumes/SHAREDWORK`、`shareddisk_root` 修正为真实卷；
   - **launchd 约束落地**：按 `projects/omlxc/conf/launchd-proposal.md` 的 mount-guard 模式（launchd/TCC 不能直接执行外接卷上的二进制、`/Volumes/Model` open() 会挂死），守护脚本必须住内置盘 `~/bin`。
   - 回滚保障：Model 盘数据在 `rclone check` 全量校验 + 一周观察期前**不删不动**。
2. **Model 排空后转 Time Machine**：`tmutil setdestination /Volumes/Model`，覆盖 mini 内置盘（代码仓+系统）。
3. **omlx 三份漂移副本**收敛只开票不动手（已有 spec：`docs/superpowers/specs/2026-09-23-omlxc-health-cli-fix-design.md`），随 P1 一并登记。

### P2 能力扩展（长期，低风险按需）

- **MOVESPEED 模型冷层**：dead models（mistral-128b 等物理跑不动的 74G 级权重）从热层轮换归档到冷层，登记表沿用 `projects/aetherforge/docs/omlx-dead-models-registry.md` 的 K3 策略。
- **向量/知识库迁移**：KOS、embed-node（`~/omlx-embed` 829M）数据面迁 SHAREDWORK/外接，释放内置盘给 24G 内存压力（参照 `docs/local-compute/compute-mesh-handbook.md` mini 角色：轻量并行+极速 CoT+向量检索）。
- **Docker DataFolder 决策**：已在 `/Volumes/SharedModel/DockerDesktop`（128G 配额）；常驻 mini 前提下保留，但写入 vault-paths.yaml 并在 P0 修复 keepalive 后纳入守护范围。
- **跨机共享**：SMB（仅 Tailscale 网段）暴露 SHAREDWORK/MOVESPEED；MBP 上 `~/Workspace` 大产物（构建缓存、数据集）改走网络而非拔盘。
- **冷备自动化 + 异机副本**：cold-backup-drill.sh 的 launchd plist 按脚本头部注释由**人工安装**（不自动注册），月度排程；每次冷备产出后经 Tailscale `rsync`/`rclone` 把加密档案镜像一份到 MBP 1T HDD（追加写入，不删旧档）——单机损毁灾备从"15 分钟还原"升级为 3-2-1 闭环；`restore-cold-snapshot.sh` 每季度演练一次还原（15 分钟验收线，BET-Y2Q1-T10-01 遗留的 drill 由人执行项）。

## 关键文件

- `bin/ops/cold-backup-drill.sh` + `bin/ops/restore-cold-snapshot.sh`（冷备/还原，P0 主力复用）
- `~/bin/disk-keepalive.sh`（修复，不重写）
- `protocols/vault-paths.yaml`（路径 SSOT，扩展不替换；同步镜像副本 `scripts/scripts/protocols/`）
- `projects/omlxc/conf/models.json`、`projects/omlxc/conf/launchd-proposal.md`
- `projects/ecos/src/ecos/ssot/mof/m1/bosroute/BOSROUTE-*.yaml`（4 个）
- `docs/plans/3y-bet-ledger.yaml`（BET 登记）、`.omo/debt/items/`（债务）
- `projects/aetherforge/docs/omlx-dead-models-registry.md`（冷层轮换策略沿用）

## 验证

- P0：`disk-keepalive.log` 一小时无 REMOUNT FAILED/NEEDS_ATTENTION 噪音；冷备产出 tar+sig 双件且 `gpg --list-packets` 可解结构（不打印明文）；`tmutil destinationinfo` 显示 Model 卷。
- P1：`rclone check /Volumes/Model/LMStudio /Volumes/SHAREDMODEL/...` 差异=0；`omlxc models reconcile` 无 orphan；`rg -l "/Volumes/Model" projects/ bin/` 仅剩 TM/迁移历史注释；`make gac-local-gate && make ssot-guardian` 通过；抽取一个 alias（coding-fast）实跑推理确认迁移后可用。
- P2：还原演练计时 ≤15 分钟（对齐 BET-Y2Q1-T10-01 验收线）；MBP 经 Tailscale 挂载 SMB 读写成功；MBP HDD 上的冷备镜像与 Lex 原件 `rclone check` 一致。
- 文档面：`uv run --with "pyyaml" python bin/ssot/doc-ssot-lint.py --json` 通过。

## 卷拓扑统一规划（2026-10-11 清理后增补）

清理后实测：Model 437G→206G 用（23%）、SHAREDMODEL 663G、MOVESPEED 97G（冷层）、SHAREDWORK/Lex 空载。

**原则**：物理拓扑保持（不合并容器、不改卷名——663G 无处中转 + 38 处代码引用/软链/Docker·LMStudio 配置连锁迁移成本过高 + 4.1T 盘硬件待验证）；命名统一只在逻辑层（vault-paths/BOS），物理卷名作兼容底座。

| 动作 | 命令 | 前置条件 |
|---|---|---|
| 配额再平衡：SHAREDWORK 976G→300G、SHAREDMODEL 1000G→1650G（同容器总量守恒，在线调整） | `diskutil apfs resizeVolume disk10s1 300g`<br>`diskutil apfs resizeVolume disk10s2 1650g` | 直连对照实验后稳定数日（见下节「综合存储架构 v2」；原"9 天掉线 2 次"出自 keepalive 误报日志，已作废） |
| MOVESPEED 定位固化：冷层+数据集增长空间（1.9T 闲置即余量，不再切卷） | 写入 vault-paths（P1） | — |
| Model 终态：P1 迁完 LMStudio 独有模型后转 TM 独占卷 | `tmutil setdestination /Volumes/Model`（P1） | 迁移验证 + 观察期 |

遗留风险登记：SHAREDMODEL 热层无备份的风险已部分缓解——稀有权重 232.4 GiB 已在 Lex 有校验过的副本，公开源权重可由清单重下（见下节）；4.1T 盘硬件层可疑，依据是 9/7 厂家故障说明与 10-11 14:47 的一次实测整链掉线（见下节）。此前写在这里的"两次异常消失：10-07~10-10 三天、10-10 夜~10-11 晨 8.5h，keepalive 日志为证"来自 keepalive 误报日志，**已作废**。

## 综合存储架构 v2（2026-10-11 实测：内置盘备份 / NAS / Y7000P / 4.1T 盘）

> 关联：BET-Y2Q4-T10-242（存储收敛）、BET-Y2Q4-T10-243（4.1T 兜底体系）。本节数字均为 2026-10-11 当天实测。

**目标**：每类不可重建的数据至少两份、其中一份异机或异介质，且每一份都经过解密或回读校验；监控只在真出问题时报警。

### 实测事实

| 资产 | 实测 | 角色 |
|---|---|---|
| 小米 NAS（MINAS） | 仅暴露一个 SMB 共享，7.2T、剩 3.5T；写入 9.8 与 24.9 MB/s（两次采样，波动大）；不响应 ICMP；RAID 级别未确认（用户称双盘） | 只放加密归档的在线副本；不放热数据，不做几百 GB 级搬运 |
| Y7000P | Wi-Fi 6E（链路 2.4 Gbps），rclone+sftp 传 256 MiB 用 13~15 秒（约 18~21 MB/s）；E:（内置 990 PRO 2T NVMe）空闲 1764G，H:（4T USB）仅剩 273G，F:（T7 2T USB）仅剩 105G；无 rsync，有 tar/wsl/git | 如需放置，只放稀有权重 232G 到 E:（源取 Lex 副本）；848G 全量镜像不做 |
| mini 内置盘 | 460Gi，已用 294Gi；Documents 56.6G（Finder 的 iCloud 桌面与文档开关为开，同步是否完成未验证）、Library 50.5G、Workspace 9.1G | 备份清单见下 |
| `~/.claude` | git 报告它不是仓库、无远端（LifeOS 文档称有私有远端，与现场不符） | 此前零备份，已纳入内置盘备份 |

### 对原假设的订正

| 原假设 | 实测 | 处理 |
|---|---|---|
| 小米 NAS 可作主力归档 | 写入 10~25 MB/s | 降为加密归档的在线副本 |
| Y7000P 局域网回灌 SHAREDMODEL 约 1 小时 | 走 Wi-Fi，约 20 MB/s，848G 要 12 小时以上，恢复同样久 | 不做全量镜像 |
| Y7000P 的 4T 盘有约 1T 空闲 | H: 仅剩 273G，空闲在 E: | 如需放置用 E: |
| keepalive 日志反映 4.1T 盘频繁掉线（"9 天 3 次大规模""间隔缩至 3 分钟""三天""8.5h"） | **误报**（见下） | 作废；T10-243 设计文档与 HW-DISK8 债务中的相关数字待订正 |

### 备份矩阵

| 资产 | 位置 | 加密 | 校验 | 状态 |
|---|---|---|---|---|
| mini 内置盘 must-keep 清单（76.8 GiB、849,110 条目：Documents、Workspace、`.claude`、`.codex`、`.config`、Pictures、钥匙串文件等） | Lex `cold-backup/mini-internal/20261011T025545Z/` | gpg AES-256，口令在登录钥匙串（service `cold-backup`） | 整包解密+列表 rc=0/0；还原抽样 2/2 逐字节一致；sha256 记入 manifest | 完成 |
| 同上 | NAS `_backups-from-mini/mini-internal/20261011T025545Z/` | 归档本身已加密 | NAS 回读 sha256 与 manifest 一致 | 完成 |
| 补充小归档（1.05 GiB、7,478 条目：`.kems-pilot`、`.lmstudio` 对话与设置、`.cherrystudio` 配置、omlx-embed 脚本） | Lex `…/20261011T082143Z/` 与 NAS 同路径 | 同上 | 解密+列表 rc=0/0；还原抽样 2/2 一致；NAS 回读 sha256 一致 | 完成 |
| 稀有发布者权重（232.4 GiB） | Lex `cold-backup/sharemodel-hot-tier/rare-publishers/` | 否（公开模型权重） | 与源端逐目录大小、文件数一致 | Lex 完成；第 3 份未做 |
| 公开源权重（约 545G） | 无副本 | — | — | 可由清单重下 |
| 工作区 git 追踪面冷备（8.05G） | Lex 与 MBP | gpg AES-256 | Lex 原件与 MBP 回传 sha256 一致 | 完成（10-10） |

未覆盖：`Library/Application Support`（如 Claude 10.98G、Google 6.76G，多为应用本体或云同步）与缓存类目录；iCloud 托管的 Documents 同步完成度未验证。

### 4.1T 盘（MOVESPEED mini M4 4TB 扩展坞，DK5A1-4T）调查结论

- **接入方式**：不是直连 mini。链路是 mini 后置雷电口（以 USB 3.2 10 Gb/s 模式工作，雷电总线显示"无设备"属正常）→ VIA VL822 hub（带 Genesys 二级 hub 与一个 MCP01 设备）→ 盘。
- **9/7 厂家故障说明**（用户整理，存 NAS 根目录）：mini、MBP、Y7000P 三台主机、多根线、带电 hub、两种桥接芯片（RTL9210VB、RTL9220）均复现；首次超时稳定在约 10.4 秒；指向 SSD 主控 RTS5772DL 或固件；购于 2025-10-15。
- **keepalive 误报根因**（已在 launchd 内复现）：launchd 下的 `/bin/bash` 无「可移动卷」TCC 授权，`ls` 与写入均报 `Operation not permitted`。旧脚本用 `ls` 判挂载，于是每 3 分钟误判一次「未挂载」并"重挂"。佐证：StorageKit 在重挂时记录 `Mounted: Yes`；rsync 从该卷连读约两小时无中断。
- **真实掉线**：统一日志只留约 18 小时（至 10-10 22:03），期间仅 1 次——2026-10-11 14:47:44，该口上 3 个 SuperSpeed 设备在 6 毫秒内一起消失、约 1 秒后链路恢复，三个卷（含未被监控的 MOVESPEED）被系统卸载。这是整条 hub 链路一起掉，与 9/7"只有盘自己掉"的特征不同。
- **已修**：`~/bin/disk-keepalive.sh` v3.2（仓库外脚本）：挂载判定改用 `diskutil info`；保活写入降为尽力而为，被拒不计异常；真实掉线按小时从统一日志采集到 `~/Library/Logs/disk-keepalive.drops`，附"同刻消失的 SS 设备数"，回看窗口随距上次采集的间隔自适应；v3.1 增加维护开关（`disk-keepalive.maintenance`，人为拔线或卸载期间暂停检测，2 小时自动失效）。保活写入在 launchd 下仍被拒，恢复需给 `/bin/bash` 完全磁盘访问权限（范围大，暂不做；也没有证据显示空闲会致掉线）。同批在仓库内修了 `hot-tier-resilience.sh` 的 `verify`（平铺模型目录被静默当成已校验）与 `daily-report`（纳入 `.drops`）。
- **误报的连带后果**：脚本守卫 `guard_hot_online` 读 keepalive 的 `state` 计数（≥5 退避）。误报期间 `state` 恒为百位数，周日 04:00 的定时 `sync-rare` 会被静默拦下；v3 归零后该守卫才恢复正常。
- **直连对照实验的判定规则**：把盘从 hub 摘下，直插 mini 后置雷电口，观察 3~7 天，看 `.drops` 里的 `ss_removed`。直连后不再掉 → 问题在 hub 或 mini 到 hub 的那段线；仍掉且 `ss_removed=1` → 回到 9/7 结论，走售后换盘。拔线本身会产生一条 Removed 记录，需标注为人为。

### 状态与里程碑

| 项 | 状态 | 说明 |
|---|---|---|
| 内置盘加密备份（Lex + NAS） | 完成 | 见备份矩阵 |
| keepalive 误判修复（v3 / v3.1 / v3.2） | 完成 | launchd 内已验证。v3 自 10-11 16:07 起，除 20:46~22:46 的人为维护窗口及其到期后一次真实重挂外无异常；14:47 之后统一日志没有新的 USB 移除事件。每小时增量采集已自然运行；v3.2 修了"维护窗口后回看窗口过短会漏记空档里的掉线"的盲区 |
| 4.1T 直连对照实验 | 待用户 | 10-11 20:51 已演练卸载（不需停应用，只有 CleanMyMac 监控进程持有一个目录句柄）；2 小时维护窗口到期未换线，已完全恢复；需用户在 mini 旁时重开窗口 |
| 冷备口令离线副本 | 待用户 | 口令只在登录钥匙串；内置盘损坏则所有 gpg 冷备不可解 |
| 仓库内误报数据订正（HW-DISK8 债务、T10-243 spec、T10-242 retro、T10-243 账本 goal） | 完成，PR 待合并 | omostation#4720（分支 `agent/governance-agent/storage-p1`）；spec 升 1.0.1 并同步绑定摘要 |
| `hot-tier-resilience.sh` 的 `daily-report` 纳入 `.drops`、`verify` 修平铺目录 | 完成，PR 待合并 | 同上；已用构造场景验证（原版确实误判通过） |
| **周同步排程的 TCC 缺口**（10-12 复盘新发现） | 代码完成，待用户安装 | launchd 直启的 `/bin/bash` 对外接卷读写全被拒（`selftest-launchd` 实测 `hot=77 lex_write=77`），原周任务 plist 装上后 `runs = 0` 从未运行。改为 launchd → `open -a iTerm` 启动器（实测 `hot=0 lex_write=0`）；新增 `weekly` / `selftest-launchd` / `install-schedule`，日报带周任务心跳与补跑；回归测试全过。装排程是人工步骤，且必须先让主工作区含 `weekly` 的版本 |
| `verify` / `manifest` 的静默假通过（10-12 复盘新发现） | 代码完成 | 读不到热层时 `verify` 曾 exit 0（抽样 0、不一致 0）、`manifest` 曾用空壳覆盖 Lex 上的旧清单；现在抽样为 0 / 读不到 / 清单缺失或超期一律失败，空清单不覆盖 |
| Time Machine（10-12 实测） | 待用户 | `tmutil destinationinfo` 为 "No destinations configured"，偏好 `AutoBackup = 0`、`LastBackupActivity = 2026-03-16`：内置盘近 7 个月无 TM 备份，现仅靠 10-11 的加密归档。Model 排空（10-18 观察期后）并重建卷后需用户 `sudo tmutil setdestination` |
| ecos 存储并轨改动（`DOMAIN-model-volume.yaml`、`constraints.yaml`、`catalog-daemon.py`） | PR 待合并 | #4716 合并时 `projects/ecos` 指针取了上游值，该改动实际未生效；omostation-ecos#93，本地测试 1388 通过。其 CI 红在 `ecos-constraint-compiler.py:226` 的 F841（ecos 主分支自 10-10 起即红，与本改动无关） |
| 稀有权重第 3 份（NAS 约 4 小时，或 Y7000P E: 约 3.5 小时） | 待定 | 232G |
| 本地 main 与 origin/main 分叉 | 已解决 | PR #4716 于 10-11 21:51 合并，两者重新一致 |

**交付现状（10-12 起）**：本地积压的 21 个提交已由 PR #4716「sync: 本地主树积压合并」交付，本地 main 与 origin/main 一致（`7591a2a93`），先前写在这里的"双向分叉、需拆 PR"的结论随之作废。10-12 已推送并开 PR：omostation#4720（订正误报数据 + `hot-tier-resilience` 修复）与 omostation-ecos#93（存储并轨），均待合并；ecos 的 PR 合并后还要更新主仓的 `projects/ecos` 指针，T10-242（账本状态 `blocked`）才能解封。另有 6 个文件里还留着 `/Volumes/SharedDisk` 旧引用（`ecos-health-check.py`、`check-disk-usage.py` 等监控脚本盯着一个不存在的卷；`check-disk-usage.py` 在挂载点不存在时 `return 0`，等于永远通过），该卷是退役、离线还是改名需要用户定，改之前不动。另发现 origin/main 账本 lint 当前有一条别的 BET 的错误：T10-240 `OVERALL_STATE_MISMATCH`（declared=`blocked`，derived=`delivery_accepted`），#4716 合并后即存在，与本文件改动无关。

## 披露与假设

- KOS 先例检索不可用（kos-cli 不在 PATH，MCP 返回 "Retrieval database not found"），已用仓内 `rg` 替代——按 CLAUDE.md §6.6，声明为检索缺口而非"无先例"。
- Model↔SHAREDMODEL 重复体积按元数据估算（df），精确去重清单待 P1 `rclone check` 产出。
- 全部破坏性/不可逆操作（tmutil removedestination、Lex 重建加密卷、mdutil、删除 Model 存量、SMB 开放）执行前逐项向用户确认，本计划批准 ≠ 逐项授权。
- 假设：三块盘常驻 mini（用户 2026-10-10 确认；2026-10-11 进一步确认**放弃**原"某盘给 MBP 在家时用"的拔插计划——SHAREDWORK 跨机角色固化为网络共享，MBP 侧另有一块独立 2T Model 盘不在本规划范围）。
- 2026-10-11 订正：本文件此前引用的 4.1T 盘掉线频次来自 keepalive 误报日志，已作废（见「综合存储架构 v2」）。真实掉线的长期频次目前无数据：统一日志只留约 18 小时，`disk-keepalive.drops` 刚开始积累。
- NAS 速度只有两次采样、RAID 级别未确认；Y7000P 速度含 rclone 启动开销，且走 Wi-Fi，随信号波动。
- 内置盘备份、小归档与 NAS 副本均为一次性手工作业（脚本在仓库外的 `~/.local/share/mini-internal-backup/`），尚无排程、保留策略与定期还原演练，不是持续机制。稀有权重的周同步在用 `install-schedule` 人工安装并由 launchd 真实触发成功一次之前，同样只是"设计 + 手工跑通"，不是持续机制。
- 2026-10-12 复盘：本文件和相关治理文档在 10-11 之前出现过两层"声明与执行不一致"——监控的输出在 launchd 里是假的（误报），执行端的周任务在 launchd 里根本跑不了（TCC）。两者同根（launchd 下的 `/bin/bash` 没有『可移动卷』授权），都是在交互终端里手测不出来、只有在 launchd 里复现才暴露。见 `.omo/_knowledge/retros/BET-Y2Q4-T10-243.md`。
