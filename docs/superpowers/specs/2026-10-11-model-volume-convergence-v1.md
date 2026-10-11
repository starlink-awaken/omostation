---
type: spec
schema_version: specification/v1
status: accepted
lifecycle: spec
spec_version: 1.0.0
bet_id: BET-Y2Q4-T10-242
owner: governance-team
last_updated: '2026-10-11'
last-reviewed: '2026-10-11'
---

# BET-Y2Q4-T10-242 — P1 存储收敛 spec

> 上位 BET: BET-Y2Q4-T10-242（台账行 ~41638）。本文是其实施规格与验证契约。
> P0 已完成（2026-10-10/11）：冷备工具链修复+首档验证、231G 清理、keepalive UUID 化、
> Keychain 口令管理、TM 坏配置清除、Spotlight 五卷关闭。

## 1. KOS 先例

KOS 检索不可用（kos-cli 不在 PATH；MCP `search_knowledge` 返回 "Retrieval database not found"，
2026-10-10 与 10-11 两次尝试）。以仓内 rg 替代：
- `docs/superpowers/specs/2026-09-23-omlxc-health-cli-fix-design.md` — 三份 omlx 拷贝漂移问题（只开票不动手 → 本 BET 一并处理 omlx 副本收敛）
- `projects/aetherforge/packages/gateway/src/llm_gateway/gateway.py:290-302` — 2026-08-10 omlx 迁 `~/omlx` 决策注释（launchd TCC 无法 exec 外置卷二进制）
- `.omo/_knowledge/decisions/` 无直接存储迁移先例（rg 验证）
- 2026-09-14 会话（c20b0b05）用户已定向「Model→SHAREDMODEL 迁移」，本次为该方向的正式化与完成。

## 2. 现状基线（2026-10-11 实测）

| 面 | 事实 |
|---|---|
| Model 卷 | 206G 用（LMStudio 195G 独有 + omlx 19G 运行面 + INDEX.md）；零活跃消费方（lsof 空、无 LM Studio/ollama/omlx 进程、launchd embed-node 走 ~/omlx-embed、dotfiles 无引用） |
| SHAREDMODEL | 663G 用 / 1000G reserve；LM Studio `downloadsFolder` 与 ollama 软链已指向它 |
| ~/omlx | 空壳 12K（仅 cache/conf），OMLX_ROOT 默认即此（gateway.py:303） |
| /Volumes/Model/omlx | bin 648K + conf 124K + gateway 466M + weights-local 18G + models-active 软链 8K + logs/run |
| 软链农场 | `/Volumes/Model/omlx/models-active/*` → 同卷 `/Volumes/Model/LMStudio/...`（绝对路径软链） |
| 硬编码 | cockpit `OMLX_BIN="/Volumes/Model/omlx/bin/omlx"`；catalog-daemon VOLUMES 3/4 幽灵路径；constraints.yaml model-volume storage 字段；DOMAIN-model-volume storage；delegation-alias-check litellm 默认路径；vault-paths sharedwork/shareddisk_root 幽灵路径 |

## 3. 方案

### 3.1 数据迁移（先备份语义，非删除）

1. **LMStudio 独有模型 195G → SHAREDMODEL**：`rclone copy`（`--checksum` 不行则 size+modtime），**保持发布者目录结构**。model 名称+发布者两卷同名时跳过（已在 P0 清理时删除 Model 侧重复）。
2. **omlx 运行面拆解**（launchd TCC 约束，见 gateway.py:294 注释）：
   - `bin/ conf/ gateway/ models-active 清单 run/` → `~/omlx`（~470M）
   - `weights-local/` 18G → `MOVESPEED/cold-models/omlx-weights-local`（视觉权重，非当前 mini 角色所需）
   - `logs/` 不迁（churn 数据）
3. **models-active 软链农场重建**：在 `~/omlx/models-active` 以**相对化路径重链**——每个链接的 target 改为 `/Volumes/SHAREDMODEL/lmstudio/<pub>/<model>`；先产出映射清单（旧 target → 新 target）人工抽查两三个再全量重建。
4. **INDEX.md** 重写为退役说明（指向 SHAREDMODEL/新卷角色）。
5. **Model 源数据保留策略**：rclone check 全量校验 + 7 天观察期（至 2026-10-18）后才可清 Model/LMStudio（且届时 TM 已迁入,先迁 TM 再清)。

### 3.2 配置收敛（先改 SSOT, 再改消费方）

1. `protocols/vault-paths.yaml`：`sharedwork_root: /Volumes/SHAREDWORK`、`shareddisk_root: /Volumes/SHAREDMODEL`、`sharedmodel_root: /Volumes/SHAREDMODEL`（消除三幽灵路径声明）。镜像副本 `scripts/scripts/protocols/vault-paths.yaml` 同步。
2. `projects/ecos/src/ecos/l0/constraints.yaml:669` model-volume storage → `/Volumes/SHAREDMODEL`；description 更新。
3. `DOMAIN-model-volume.yaml` storage → `/Volumes/SHAREDMODEL`…（原文见 §2 基线表）→ 统一 `/Volumes/SHAREDMODEL`。
4. `catalog-daemon.py` VOLUMES 映射对齐实况（shareddisk→SHAREDMODEL, model→SHAREDMODEL 或退役、sharedwork→SHAREDWORK 卷）。
5. `api_compute.py` OMLX_BIN → 从 OMLX_ROOT 解析（`os.path.join(OMLX_ROOT,"bin","omlx")`），与 gateway.py 同一约定。
6. `bin/delegation-alias-check.py` litellm 默认路径 → OMLX_ROOT 解析。
7. BOSROUTE 三 yaml：增补 `properties.storage`（SHAREDDISK→`/Volumes/SHAREDMODEL` 等）+ description 更新（消除幽灵路径语义）。
8. `projects/omlxc/conf/models.json`：disabled.vision-nemotron-omini path → SHAREDMODEL 路径。

### 3.3 治理闭环

- 工作流 run 记录（agent-workflow start/claim/verify/closeout）。
- 债务登记 `.omo/debt/items/`：SHAREDMODEL 无备份风险（P2）、4.1T 盘硬件观察（换线后监控）。
- 复盘文档（retro）。
- KOS 检索缺口披露（见 §1）。

## 4. 验证契约

1. `rclone check /Volumes/Model/LMStudio /Volumes/SHAREDMODEL/lmstudio --one-way` 差异=0
2. `~/omlx/bin/omlx --version` 输出版本（内置盘可执行）
3. `uv run --with "pyyaml" python scripts/check-vault-paths.py` exit 0
4. `make gac-local-gate` 通过
5. 抽一个 alias（coding-fast 或 vision）实跑推理，确认软链农场重建后模型可加载
6. 拉取 softlink 抽查 3 个（ln -l）核对指向
7. rclone check 全量校验后，设 TM 目的地为 Model 卷：`sudo tmutil setdestination /Volumes/Model`（需你跑，涉及 sudo）
7. 观察期 7 天后（10-18）清 Model/LMStudio 源（需你确认）

## 5. 排序与风险

- 先 3.2 SSOT（纯代码/文档，可即时验证），再 3.1 数据迁移（小时级），再 TM/清理（需观察期与你的确认）。
- 主要风险：rsync/rclone 中 SHAREDMODEL 掉线（keepalive state≠0 即暂停）、软链农场绝对路径需逐条重链、大文件传输 CRC（用 rclone check 全量兜底）。
- 回滚：Model 源全程不动（只 copy 不 move），任何配置改坏可 git revert；软链农场重建前备份旧映射清单。
- circuit_breaker 契约见台账 BET 条目。
- 观察期后 Model/LMStudio 清理前提：TM 首备份完成 + 你确认。3.1 的 copy 阶段 risk_level 实际为 L1（不改源）。

## 5.1 三份 omlx 拷贝漂移（随本 BET 一并收敛）

spec 2026-09-23 只开票了三份漂移拷贝（`/Volumes/Model/omlx` 19G、`projects/omlxc` 仓内、`~/omlx` 空壳）——本 BET 顺带收敛：omlxc 仓内版本是 SSOT（git 管理），`~/omlx` 成为唯一运行面（copy 自仓内 conf,经 OMLX_ROOT 环境约定），`/Volumes/Model/omlx` 退役（bin/conf 入 ~/omlx，weights-local 入 MOVESPEED 冷层）。MBP 侧 2T Model 盘不在本 BET 范围。
