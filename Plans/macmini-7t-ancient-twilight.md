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
| 配额再平衡：SHAREDWORK 976G→300G、SHAREDMODEL 1000G→1650G（同容器总量守恒，在线调整） | `diskutil apfs resizeVolume disk10s1 300g`<br>`diskutil apfs resizeVolume disk10s2 1650g` | 4.1T 盘换线/换口后稳定数日（9 天掉线 2 次） |
| MOVESPEED 定位固化：冷层+数据集增长空间（1.9T 闲置即余量，不再切卷） | 写入 vault-paths（P1） | — |
| Model 终态：P1 迁完 LMStudio 独有模型后转 TM 独占卷 | `tmutil setdestination /Volumes/Model`（P1） | 迁移验证 + 观察期 |

遗留风险登记：SHAREDMODEL 热层 663G 无备份（P1 用 Model 排空后空间做镜像或轮换）；4.1T 盘硬件层可疑（两次异常消失：10-07~10-10 三天、10-10 夜~10-11 晨 8.5h，keepalive 日志为证）。

## 披露与假设

- KOS 先例检索不可用（kos-cli 不在 PATH，MCP 返回 "Retrieval database not found"），已用仓内 `rg` 替代——按 CLAUDE.md §6.6，声明为检索缺口而非"无先例"。
- Model↔SHAREDMODEL 重复体积按元数据估算（df），精确去重清单待 P1 `rclone check` 产出。
- 全部破坏性/不可逆操作（tmutil removedestination、Lex 重建加密卷、mdutil、删除 Model 存量、SMB 开放）执行前逐项向用户确认，本计划批准 ≠ 逐项授权。
- 假设：三块盘常驻 mini（用户 2026-10-10 确认；2026-10-11 进一步确认**放弃**原"某盘给 MBP 在家时用"的拔插计划——SHAREDWORK 跨机角色固化为网络共享，MBP 侧另有一块独立 2T Model 盘不在本规划范围）。
