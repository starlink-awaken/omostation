---
schema: md/v1
status: completed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-27
type: report
bet_id: BET-Y2Q4-T10-208
title: BET-Y2Q4-T10-208 事件账本在线快照到 XDG 状态根（ADR-0456 B4b 批次 1） — closeout receipt
created: '2026-09-27'
run_id: 20260927T134924Z-project-doc-change-18cfdd73
---

# BET-Y2Q4-T10-208 closeout receipt — ADR-0456 B4b 批次 1

> 本文件是 ledger `completion_evidence` 指向的 receipt。§3 的 canary 三条是 closeout 撰写时点
> （2026-09-27T14:26Z）在**合并后的 main**（`d83c1b6b1`）上重新实测的，非复述交付期数字。
> 契约定义见 `docs/superpowers/specs/2026-09-27-event-ledger-state-snapshot.md`（`spec_version 1.0.0`，
> 摘要绑定 `sha256:0bea20f2…`，本轮**未改动**该文件 — 见 §5 打假第 1 条）。
> 复盘见 `.omo/_knowledge/retros/BET-Y2Q4-T10-208.md`。
> 本轮边界：**只建快照、不动权威**。plist / crontab / launchctl 一行未改，权威 ledger 未写入。

## 1. 交付物

| 项 | 值 |
|---|---|
| 主仓 PR | #4466（`state: MERGED`，`mergedAt 2026-09-27T14:20:16Z`） |
| 主仓 merge commit | `d83c1b6b17d18e07913e36893daf8554ee1dd473` |
| merge commit 触及文件 | **恰好 6 个**（`git show --name-only d83c1b6b1`）：`AGENTS.md`、`ARCHITECTURE.md`、`Makefile`、`docs/plans/3y-bet-ledger.yaml`、`docs/superpowers/specs/2026-09-27-event-ledger-state-snapshot.md`、`projects/omo` — 无生成态（`.omo/state/**`、`BRIEF.md` 均未随 PR 走） |
| 行量 | `+325 / -3`（`git diff --shortstat d83c1b6b1^1 d83c1b6b1`） |
| 子模块 gitlink | `projects/omo` `a9d0165ec345b006e8e8eaf850fd1dcde3b3b520` → `599632c5f37b14f4812bf53320d2eacc4e2a3bca`；合并后复核 `git -C projects/omo branch -r --contains 599632c` = `origin/main`（子 PR omo #199 已先落子仓 main） |
| 内核 | `omo ledger snapshot` — `sqlite3.Connection.backup()` 在线复制 + `--bootstrap` 空库引导 |
| 入口 | `make runtime-state-snapshot`（Makefile，不走 `bin/` — `check-bin-quota-diff.py` 禁净增脚本） |

## 2. 契约语义（本轮固化的四条不可省的行为）

1. **源只读**：`--source` 以 read-only URI 打开，绝不构造 `EventLedgerSurface`（那会触发写路径与 schema 迁移）。
2. **dest 存在即拒绝**：`reason: dest_exists`，非零退出，不覆盖、不追加。
3. **落盘前校验哈希链连续性**：比较源与副本在同一 sequence 区间内**已存储**的 `event_hash`
   （`prefix_equal` + `first_bad_sequence`），刻意**不重算**哈希 — 重算等于给内核的规范化做第二份实现，
   正是 ADR-0456 要消除的重复真值。
4. **副本永远非权威**：`authoritative: false` + `authority_note` 说明翻转权威需要改道 launchd/cron 并注入
   `OMO_EVENT_LEDGER_DB` 的那一批。

## 3. 验证

### 3.1 合并后 live canary（本轮实测，dest 指向一次性目录，不碰真实状态根）

| # | 动作 | 结果 |
|---|---|---|
| A | `snapshot --source <权威> --dest <一次性>` | `ok: true`、`mode: snapshot`、`chain_total: 67`、`compared_sequences: 67`、`chain_ok: true`、`integrity_check: ok`、`prefix_equal: true`、`source_head_sequence == dest_head_sequence == 67`、`source_ahead: 0` |
| B | 同 dest 再跑一次 | **拒绝**：`reason: dest_exists`、`RC=1`、未覆盖 |
| C | `snapshot --bootstrap --dest <一次性>` | `mode: bootstrap`、`chain_total: 0`、`chain_ok: true`、`integrity_check: ok`、`authoritative: false` |

A 的 67 条 vs §4 的 63 条差 4 条 = 这 1.5 小时内生产侧真实增量。快照在**活的、正在增长的**源上仍然
`prefix_equal` 且 `source_ahead: 0`，这是"在线备份而非文件复制"这一核心主张的直接证据。

### 3.1b done_when 逐条复核（合并后，本轮实测）

| done_when | 结论 | 实测依据 |
|---|---|---|
| #1 `--bootstrap` 走生产同一 `connect()` 入口、`count()==0`、**`schema_fingerprint` 与生产相等** | **PASS** | 用 `omo.event_ledger.schema.schema_fingerprint()` 逐字节比对 5 个库（生产 / 真实 prod 副本 / 真实 dev 库 / canary prod / canary dev）→ **全部 `equal_to_production=True`**；键集 `migrations/tables/triggers`，5 表 3 触发器一致 |
| #2 online-backup + `integrity_check ok` + 链无 `first_bad_sequence` | **PASS** | §3.1 A |
| #3 前缀连续且**不重算哈希** | **PASS** | §3.1 A `compared_sequences: 67`、`prefix_equal: true` |
| #4 dest 存在即拒绝且不动既有文件 | **PASS** | §3.1 B `dest_exists` + `RC=1` |
| #5 provenance sidecar 十字段齐 | **PASS** | §4 实测两份 sidecar |
| #6 测试只在 `tmp_path`、不读真实 home / 真实生产库 | **PASS** | `uv run --directory projects/omo python -m pytest tests/test_event_ledger_snapshot.py -q` → **20 passed in 1.61s** |
| #7 零运行时效应"实测而非断言"：前后六计数一致 + `repo_root.py --json` 逐字节一致 + plist 计数不变 | **部分** | plist 43、六计数、`repo_root --json` 均实测一致；但 `--reality-check` 的 **`exit 0` 期望今日不成立**（E4 因机器侧新装两个 `com.local.aictl-verify-*` fail-closed，见 §6 第 2 条）。`e1_drift=0` / `e2_undeclared=0` 两个被本条真正关心的量仍为 0 |
| #8 `make runtime-state-snapshot` 入口 + `bin/` 无净新增 | **PASS** | `Makefile:219`；本轮 6 文件中无 `bin/**` |
| #9 AGENTS/ARCHITECTURE 点明两状态根且直言未权威 | **PASS** | merge commit 内 `AGENTS.md +9`、`ARCHITECTURE.md +1` |
| #10 子仓先 merge、父指针走事务、`--is-ancestor` 退出 0 | **PASS** | `599632c` 在 omo `origin/main`（§1 复核）；事务打印 `submodule-reachability: PASS` |

### 3.2 合并前在本树上的验证

- `governance surfaces --json`（CI 实际检出的那棵树）→ `status: ok`、`unregistered_top_levels: []`、`missing_registered_roots: []`
- 三条 commit 各自 lane 干净：`docs,docs_data` / `config` / `submodule_pointer` 分别 PASS
- 指针事务 `submodule-pointer-transaction.sh` → `submodule-reachability: PASS (1 gitlinks, changed-from HEAD)`；无 rewind
- spec 摘要绑定逐字节一致：工作树文件 == `HEAD:` 对象 == 台账 `content_digest`（`0bea20f2ee5a5364…`）
- **CI：22 pass / 4 skipping / 0 fail**（`gh pr checks 4466`），含曾杀死 #4461 的 `interface-check` 系
- L3 深度安全审查：0 findings
- 本地 `make gac-local-gate`：29 PASS / 1 FAIL，唯一 FAIL 为门禁自身超时缺陷（§6 第 4 条）

## 4. 运行时零效应证明

| 断言 | 实测 |
|---|---|
| 未启停任何服务 | 无 `launchctl` 调用 |
| plist 未改道 | `~/Library/LaunchAgents` 全量 **58**，指向 `Workspace` 的 **43**（`rg -l Users/xiamingxing/Workspace *.plist`）— 与交付前同一计数 |
| crontab 未改 | 一行未动 |
| 权威 ledger 未被写 | `runtime/omo/event-ledger.sqlite3` 155,648B，mtime 20:33（早于本轮全部动作且此后未变）；A 的 `source_ahead: 0` |
| 真实状态根副本仍非权威 | `prod` `mode: snapshot` seq 63/63、`dev` `mode: bootstrap`，两份 `authoritative: false`、`chain_ok: true` |

### 4b 一次性产物清理（operational `cleanup` 轴的证据）

本轮全部写动作的落点，以及 closeout 时的处置：

| 路径 | 性质 | 处置 |
|---|---|---|
| `/tmp/omostation-canary/canary-{prod,dev}.sqlite3` 及其 `-shm`/`-wal`/`.provenance.json` | §3.1 canary 的一次性 dest，**8 个文件**，全部 `authoritative: false` | **已删除**（`test -e /tmp/omostation-canary` → 不存在） |
| `~/.local/state/omostation/{prod,dev}/event-ledger.sqlite3{,.provenance.json}` | §1 交付物本身（`make runtime-state-snapshot` 的产物） | **保留** —— 不是残留；删除它即 §7 的回滚 |

清理不伤交付物的判据（实测，非断言）：删除 canary 前后对真实状态根 4 个文件跑
`shasum -a 256 -c` → **全部 OK**（`prod` `547ba0c3…`、`dev` `c1f25f5e…`、两份 sidecar
`048ae2ce…` / `c2f179c9…`）。canary 与真实根处于不同目录，且真实根已存在 → 即便路径写错，
`dest_exists` 拒绝机制（§2 第 2 条）也让 canary 不可能覆盖它们。

## 5. 打假：与 plan / spec 不符的事实

1. **spec §4-8 的 plist 基线"51"是错的，实测 43**。spec 已被 `content_digest` 绑定，改它 = 破坏绑定并
   触发 `COMPLETION_FILE_DIGEST_MISMATCH`，所以**不改文件、在此留痕**。修正去处就是本节 + retro。
2. **"状态根已迁移"的说法为假**，本轮不成立。内核侧 `projects/omo/src/omo/event_ledger/surface.py`
   从不读 `OMOSTATION_STATE_ROOT`，只认 `OMO_EVENT_LEDGER_DB`，否则回落 `WORKSPACE_ROOT`。
   在新路径放一份副本 = 改变"还没有人读它"的东西。台账 `goal` 字段已写明这点。
3. **`owned_installed == owned_declared` 不是独立等式**。`gen-service-configs.py:477` 里
   `owned_declared = len(buckets["workspace"]) - len(e2_gap)`，是**派生值**。E1–E4 真正的门禁是
   `e2_undeclared == 0`。B4b 批次 2 若拿"49==49"当不变量会自欺。
4. **PASW worktree 里 `state_root` 就是 worktree 自身**（实测 `repo_root.py --json`：
   `code_root = ws-b4b1-evidence`、`state_root = ws-b4b1-evidence`、`event_ledger_path` 落在
   `ws-b4b1-evidence/runtime/omo/…` 而不存在的文件上，`canonical_root` 仍正确报 `Workspace`）。
   这符合 ADR-0456"未声明 profile 时二者相等"的不变量，但**后果未在 plan 里评估**：每个 worktree 自造一份
   平行 ledger，`release` 时随目录消失 —— 是静默丢失，不是冲突。列 §6 第 1 条上报。

## 6. 上报项（不在本轮处置）

1. worktree 写平面碎片化（§5 第 4 条）—— 需要 principal 决定：worktree 是否默认继承 canonical 状态根，
   或强制 profile 声明。
2. `services.yaml` 命名空间策略对新增 `com.local.*` fail-closed：本机今日 19:54 新装
   `com.local.aictl-verify-{daily,weekly}`（跑 `~/.local/bin/aictl`，不引用 Workspace），
   落入 `unmanaged_unknown` → `--reality-check` `ok: false`（E1 drift 0、E2 undeclared 0、E3 lint debt 2）。
   既有先例 `com.local.phosphene` 在 `exempt_labels`。属 B3 交付物的正常触发，非本轮引入。
3. `OMO_ALLOW_GIT_WRITE` 在仓库中不存在，而 `crontab.new:133` 无条件 commit —— B5"dev 禁 git 写"的前置缺口。
4. `gac-local-gate.py:395-401` 追加 `check-conflict-markers` 时未带 `timeout` 键，落到 `:573` 的 15s 缺省，
   而它实测 14–19s（`:553-554` 注释已自承会假超时）。
5. governance-check 系 jobs 检出 **head 树**而非合成 merge ref（`governance-check.yml:163-171`），
   故"修主干 + 重跑"对在途 PR 无效；AGENTS.md §6 现说法需订正。
6. PASW 子模块 clone 是 **shallow** 的，本地祖先判断双向误报，会骗过 gitlink 事务并造成
   pre-push `submodule-reachability` 假失败（本轮 `omlxc` 实例，见 retro Q4）。

## 7. 回滚

单点回滚 = revert `d83c1b6b1`：主仓 6 文件 + `projects/omo` 指针退回 `a9d0165`。
内核侧不需回滚动作（子仓 main 上的 `599632c` 只是**新增**子命令，既有 `ledger` 路径未改）。
真实状态根的两份副本可直接删除（`authoritative: false`，无读者）。
本轮无需数据回迁：权威从未离开 `runtime/omo/event-ledger.sqlite3`。
