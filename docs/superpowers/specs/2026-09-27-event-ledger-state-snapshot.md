---
schema_version: specification/v1
spec_version: 1.0.0
title: Event Ledger Online Snapshot to the XDG State Root (ADR-0456 B4b batch 1)
bet_id: BET-Y2Q4-T10-208
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-27
adr: ADR-0456
---

# ADR-0456 B4b 批次 1 — 事件账本在线快照（不翻转权威）

> 契约正文只写不变量。所有数字为撰写时点（2026-09-27T12:0Z）在**真实生产库**上的一次实测，
> 用于说明前提，不构成判据。引用本契约所在 ADR 时必须写文件名
> `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md`（`ADR-0456` 标识冲突，见该文件 §）。

## 0. 本批次的边界（先说清"不做什么"）

B4b 在计划里是两件事：**状态搬迁**与**分批切换**。本契约只管前者，且明确**不翻转权威**：

| | 本批次（B4b-1） | 下一批次（B4b-2+） |
|---|---|---|
| 生产库继续被谁写 | **仍是** `$(state_root())/runtime/omo/event-ledger.sqlite3` | 同一处，直到该批切换 |
| `~/.local/state/omostation/prod/**` 的地位 | 经验证的**快照**，`authoritative: false` | 成为唯一写者 |
| plist / crontab | **一行不改** | 分批改写 + 注入 `OMO_EVENT_LEDGER_DB` |
| `canonical_root()` / `state_root()` / `event_ledger_path()` 的解析结果 | **逐字节不变** | 改道 |

理由（实测，不是偏好）：内核侧 `projects/omo/src/omo/event_ledger/surface.py` 的
`_resolve_db_path()` **不读** `OMOSTATION_STATE_ROOT`，只读 `OMO_EVENT_LEDGER_DB`，
否则回落到 `WORKSPACE_ROOT`。所以在没有任何进程的环境里注入 `OMO_EVENT_LEDGER_DB` 之前，
把库复制到新位置**不会**改变任何在跑服务的写入目标——"搬完就断服务"的担心在本批次不成立，
而"搬完就改道"的声称同样不成立。本批次交付的是**机制被证明可用**，不是**位置已改**。

## 1. 前提（实测，且每条都可能被后续复现否证）

1. **源库是活的且带未落盘的 WAL**：`journal_mode=wal`，`-wal` 文件显著大于主库文件
   （撰写时点主库 151 KB / `-wal` 4.1 MB，`-wal` mtime 晚于主库 mtime），
   并且有常驻进程持有写句柄（`lsof` 实测命中）。
   ⇒ **`cp` 主库文件得到的副本会漏掉 WAL 中的已提交事件，链验证必红。**
   唯一正确的复制手段是 SQLite 在线备份 API（`sqlite3.Connection.backup()`）；
   本仓已有先例与注释：`bin/ssot/scene-history.py`（"在线备份 API, WAL 安全（不用 cp）"）。
2. **链可自证、锚点为空**：`event_log.previous_hash → event_hash` 逐行链接，
   `verify_chain()` 在本批次起点上实测 `breaks=0`；`integrity_anchor` 表 **0 行**。
   ⇒ 不存在"历史锚点"可依赖，连续性只能由链本身证明。
3. **哈希是纯 SHA-256、无签名密钥**：`event_hash` / `root_hash` 不引用任何 vault/env 密钥，
   `integrity_anchor.signed_at` 只是 `_utc_now()`（名为 signed 实为 unsigned）。
   ⇒ Agent 可以在不触碰 `config/security/vault.yaml` 的前提下完成验证。
   **但本契约刻意不要求任何一方计算哈希**：见 §2 判据 4。
4. **`bin/` 有净新增脚本配额**：`bin/gac/check-bin-quota-diff.py` 以 `新增 > 删除` 判定 exit 1，
   且 glob 覆盖 `bin/**/*.py`（含 `bin/lib/`）。
   ⇒ 新能力不加在 `bin/`，加在内核 `omo ledger` 子命令面；入口放 `Makefile`。
5. **子模块 gitlink 必须落在子仓默认分支**（契约
   `docs/superpowers/specs/2026-09-26-submodule-gitlink-reachability.md`，BET-Y2Q4-T10-204）：
   主仓 pin 必须已是 `projects/omo` `origin/main` 的祖先，否则会被 freshness 自动化**静默倒回**。
   ⇒ 交付顺序固定为：子仓 PR 合并 → 主仓经
   `bin/ssot/submodule-pointer-transaction.sh` 改 pin → 主仓 PR。不得手工 `git add projects/omo`。

## 2. 契约：`omo ledger snapshot`

新增内核子命令 `snapshot`（`projects/omo/src/omo/omo_ledger.py` 的 `SUBCMDS` 面），
两种互斥模式：

```
omo ledger snapshot --source <db> --dest <db> [--json]     # 快照模式
omo ledger snapshot --bootstrap --dest <db> [--json]       # 空库引导模式
```

### 2.1 快照模式必须保证的六条

1. **WAL 安全复制**：源以只读 URI 打开，目的为新建文件，复制只经
   `Connection.backup()`；禁止 `cp`、禁止读 `-wal`/`-shm` 旁路文件。
2. **失败即关闭（fail-closed），且不产生半成品**：`--dest` 已存在即拒绝并退出非零，
   错误信息指名"换路径或显式删除"，**不提供静默覆盖**。中途任何一步失败必须删掉
   已创建的目的文件与 provenance 文件，不留半份快照。
3. **副本自证**：在副本上跑 `PRAGMA integrity_check`（须 `ok`）与
   `LedgerBroker.verify_chain()`（须 `ok=True` 且 `first_bad_sequence is None`）。
   副本经**生产同一代码路径**（`LedgerBroker.connect()`）打开，因此同时证明
   schema 与内核兼容（`apply_schema` 幂等 + `verify_schema` 不漂移）。
4. **前缀一致性，不重算哈希**：源保持只读，逐序列比对**存储的** `event_hash` 字符串——
   取副本头 `H_dst`，要求源在 `1..H_dst` 区间每一行的 `event_hash` 与副本同序列逐字节相等，
   且副本 `1..H_dst` 无缺号。
   ⇒ 证明"副本是源的一条前缀，且没有跳过任何事件"，即计划要求的迁移边界无缺口。
   比对只用读到的值，绝不重新实现 `_hash_row` 的规范化（避免第二套真值定义）。
   若源在复制窗口内继续追加（`H_src > H_dst`），照实报告 `source_ahead=<H_src-H_dst>`，
   **不视为失败**，因为这正是"权威仍在源"的证据。
5. **来源自述（provenance sidecar）**：与副本同目录写 `<dest>.provenance.json`，至少含
   `source`、`dest`、`source_head_sequence`、`dest_head_sequence`、`source_ahead`、
   `integrity_check`、`chain_ok`、`created_at_utc`、`sqlite_version`、
   以及 **`authoritative: false`** 与固定字符串 `authority_note`。
   没有这份自述，新位置上的 `.sqlite3` 对后来者就是一个可能被盗认为真的高仿残骸。
6. **只读源、零副作用**：不得对源执行 `wal_checkpoint` / `VACUUM` / 任何写 PRAGMA，
   不得启停服务，不得改写 plist/crontab/launchd，不得设置任何环境变量。
   （`wal_checkpoint(TRUNCATE)` 会压缩别人正在写的 WAL，属越界。）

### 2.2 引导模式必须保证的三条

1. 空库经 `LedgerBroker.connect()`（生产同一入口）创建，**不手写 `CREATE TABLE`**；
   其 `schema_migration` 记录与 `schema_fingerprint` 必须与生产库一致。
2. `verify_chain()` 在空库上返回 `ok=True`（内核既有语义：空账本视为合法）。
3. 同样写 provenance，`authoritative: false`，并注明它是 dev profile 的**自有空 store**
   （决策 3：dev 默认起自己的空库，生产 ledger 只有一个写者）。

## 3. 落盘位置

| 用途 | 路径 | 创建者 |
|---|---|---|
| 生产状态根（目标，暂非权威） | `~/.local/state/omostation/prod/` | `snapshot --source … --dest …` |
| 开发状态根（空 store，可写） | `~/.local/state/omostation/dev/` | `snapshot --bootstrap --dest …` |

`~/.local/state/omostation/` 下**已存在**名为 `runtime` / `runtime-mvp` / `backups` 等历史子目录
（实测），故新目录名固定为 `prod` / `dev`，且实现不得复用任何既有名。

## 4. done_when（每条都可实测、可证伪）

1. `omo ledger snapshot --bootstrap --dest ~/.local/state/omostation/dev/event-ledger.sqlite3 --json`
   退出 0；该库 `verify_chain()` `ok=True`、`count()==0`、
   `schema_fingerprint` 与生产库相等。
2. `omo ledger snapshot --source <生产库> --dest ~/.local/state/omostation/prod/event-ledger.sqlite3 --json`
   退出 0；输出含 `integrity_check=ok`、`chain_ok=true`、`prefix_equal=true`。
3. 副本的 `dest_head_sequence` 与源 `1..dest_head_sequence` 区间的存储 `event_hash` 逐行相等，
   无缺号（判据 §2.1-4 的直接复现命令）。
4. 两个目的目录各有一份 `*.provenance.json`，且 `authoritative` 为 `false`。
5. `--dest` 已存在时命令**非零退出且不改动原文件**（幂等保护，测试钉住）。
6. 快照前后，`gen-service-configs.py --reality-check --json` 的
   `e1_drift / e2_undeclared / installed_total / workspace_scoped / owned_installed / owned_declared`
   逐键**完全一致**——即本批次对运行中系统零效应。
7. `python3 bin/lib/repo_root.py --json` 在快照前后输出逐键一致
   （`state_root == code_root`、`event_ledger_override: false`）——解析结果未被移动。
8. 指向 `/Users/xiamingxing/Workspace` 的 plist 计数在快照前后不变（实测基线为 51）。
9. `tests/test_event_ledger_snapshot.py` 全绿，且**不读宿主真实 home**（全部走 `tmp_path`）。
10. 无 `bin/` 净新增文件；入口是 `Makefile` 的 `runtime-state-snapshot`。
11. `AGENTS.md` / `ARCHITECTURE.md` 记录新状态根的存在与"**尚非权威**"这一点，
    以免其他 agent 把它当成已改道。

## 5. rollback

- 两个新目录（`~/.local/state/omostation/{prod,dev}`）是**仓外、无引用**产物：
  删除即完全撤销，未启动、未改道、未写入任何在跑进程能看到的位置。
- 内核侧回滚 = revert 子仓 commit + 主仓 pin 回退；主仓侧回滚 = revert 主仓 commit。
  两者都不影响源库（本批次对源只读）。

## 6. 与 BET-Y2Q4-T10-207 circuit_breaker 的关系

T10-207 的 `circuit_breaker` 明令停止"对 `runtime/omo/event-ledger.sqlite3` 的任何物理移动或
`.backup`"。**该禁令的作用域是 B4a**（其目的为零运行时效应），而 T10-208 是 principal 于
2026-09-27 逐批授权后另立的 bet，其本批次动作正是那条禁令所指的对象。
因此：本契约**不修改** T10-207 的任何字段，只在此处声明取代关系，
并把"不改解析结果、不切服务"作为 T10-208 自身的 circuit_breaker 写进台账。
