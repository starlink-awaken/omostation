---
type: report
title: BET-Y2Q4-T10-343 部署追加回执 —— scheduler 采集器修复的 publish 落地与线上复测
bet_id: BET-Y2Q4-T10-343
status: completed
created: 2026-11-10
last-reviewed: 2026-11-10
lifecycle: record
owner: governance-agent
schema_version: closeout-receipt/v1
---

# BET-Y2Q4-T10-343 部署追加回执

本文件是 `2026-11-09-panorama-a9-phantom-json-closeout.md` 的**追加**记录，不改写原收据。
原因：原收据被台账 `completion_evidence.operational.fresh_receipt.sha256` 按内容摘要绑定，
编辑它会使已入账的摘要失效。同理不改 `.omo/_knowledge/retros/BET-Y2Q4-T10-343.md`
（被 `replay.sha256` 绑定）。

原收据 §4 声明的边界是「部署侧未验证」。本文件把该边界改为**已验证**，并给出读数。

## 1 动作与授权

| 项 | 值 |
|---|---|
| 动作 | `python3 bin/gac/zhixing-host-sync.py publish --file collectors/scheduler.py --json` |
| 授权 | principal 于本会话选择「授权我执行发布」（2026-11-10），范围 = 该单文件发布 + 部署侧复测 |
| 执行树 | `/Users/xiamingxing/ws-a9-publish`，游离 HEAD `697151a9cdc4ad2f297b079b0bdfd0203537c016`（= 当时 `origin/main` tip，含 `afbe32105`） |
| 预检 | 同树先跑 `plan --file collectors/scheduler.py --json` → `state=drifted`、`write_performed=false` |
| 结果 | `ok=true`、`created=true`、`version_dir=releases/697151a9…` |

**为什么必须换树**：`_ROOT` 由 `Path(__file__).resolve().parents[2]`（`:54`）在调用时刻解析，
发布源 = 脚本所在树。共享主工作区当时落后 `origin/main` **74 个 commit**，在其上跑 `plan`
得到的是 `state=in_sync` —— 因为源与运行时**同为修复前版本**。从陈旧树发布是空动作，
甚至可能反向。这是「写路径要在调用时刻解析」与「本地工作树 ≠ origin/main」（PITFALL-COO-006）
在发布通道上的复合实例。

## 2 发布前后读数（线上通路，非仓内模拟）

证据文件：`~/.local/share/zhixing-dashboard/current.json`（由 `current/orchestrator.py`
每 300s 新起进程写出的运行时快照，即 A9 判据的实际输入面）。

| 读数 | 发布前（09:44:10 快照） | 发布后（09:49:24 快照） |
|---|---|---|
| `"diagnostic command exit 2"` 全份出现次数 | **1** | **0** |
| `source_states.scheduler.status` | `STALE_UNAVAILABLE` | `OK` |
| `source_states.scheduler.error` | `Collection failed for 'scheduler': diagnostic command exit 2` | 键不存在 |
| `source_states.scheduler.last_success_at` | `2026-11-07T00:04:27Z` | `2026-11-10T01:49:14Z` |
| A9 `detail` | 含 `diagnostic command exit 2` | `A9 evidence incomplete: cockpit_sources` |

接管方式：无人工重启。两个 launchd job（`…zhixing-dashboard`、`…-refresh`）的
`ProgramArguments`/`WorkingDirectory` 都经 `current/` 符号链接解析，`current` 原子翻转后
下一次 refresh tick（实测 30s）即使用新 release。

效果定性：`scheduler` 源的 stale 从**连续 3 天**恢复。这是原收据记 `value: NOT_PROVEN`
时无法给出的读数。

## 3 回滚基线

`publish` 输出自带 `previous_version = 17afa5408…--pub-0c898071…`；
`releases/.current-history.json` 记录同一值；旧 release 目录仍在盘且其
`collectors/scheduler.py` sha256 前缀 `28ad3162…` 可查。回滚命令：
`python3 bin/gac/zhixing-host-sync.py restore --json`。

发布前状态完整快照见 `/tmp/a9-pre-publish.json`（会话内取数，含 38 个 release 目录清单）。

## 4 结构化运行记录（AGENTS.md §14.2 六字段）

```json
{
  "inputs": {
    "source_tree": "/Users/xiamingxing/ws-a9-publish@697151a9cdc4ad2f297b079b0bdfd0203537c016",
    "asset": "bin/panorama/assets/host/scheduler_collector.py.asset",
    "deploy_name": "collectors/scheduler.py",
    "base_release": "17afa5408a01b164af14be4c559f615766715025--pub-0c898071716f40368528150bcb2e4b02",
    "evidence_file": "~/.local/share/zhixing-dashboard/current.json"
  },
  "basis": [
    "bin/gac/zhixing-host-sync.py:266-372 (_prepare_version: 从当前完整 release 出发, 只叠加所选文件, staging + rename)",
    "bin/gac/zhixing-host-sync.py:54 (_ROOT 在调用时刻解析 => 发布源随树而变)",
    "bin/panorama/panorama-collect.py:1484-1512 (A9 的 15 个必需源与准入标签集)",
    ".omo/_knowledge/ops/zhixing-dashboard-runbook.md 日常操作 (check/capture/restore 语义)"
  ],
  "approver": "principal (会话内显式选择「授权我执行发布」, 2026-11-10)",
  "result": {
    "publish_ok": true,
    "created": true,
    "version_id": "697151a9cdc4ad2f297b079b0bdfd0203537c016",
    "selected_sha256_prefix": "51f2b2815438c374",
    "post_verify": "current.json 内 'diagnostic command exit 2' 1→0; source_states.scheduler STALE_UNAVAILABLE→OK",
    "rollback_available": true
  },
  "duration_ms": null,
  "model_usage": "none"
}
```

`duration_ms` 写 `null`：`publish` 自身输出不含耗时字段，本记录不事后估一个数冒充测量。
未新建日期分片的 JSON 运行面 —— §14.2 的最小实现口径允许记录随回执落盘，
而既有平面上只有一处 (`​.omo/state/runtime/governance-dashboard.json`) 含 `duration_ms`，
此时另起一个新面属于扩面而非补缺。

## 5 新暴露的三条事实

1. **线上 A9 判定器旧于仓内**。部署 release 的 `panorama-collect-main.py`
   sha256 前缀 `fa7eb9c1…`，与 `origin/main` 的 `f891ad40…` 和主工作区的 `e7f6a4b6…`
   **三方互不相同**。后果实测：部署 detail 只有 `cockpit_sources`，而 `panorama-collect.py:1519`
   会把 `_cockpit_source_reasons(...)` 一并带出 —— 2026-10-23 那次「降级必须带原因」的修复
   没上线。**publish 不会修正它**：`_prepare_version` 从 base release 整体复制再叠加所选文件
   （`:313-332`），漂移内容被继承。按 runbook 该行属于运维裁决：有意热修 → `capture` 入仓，
   意外覆盖 → `restore`。本回执不代为判定。
2. **A9 仍 PARTIAL，原因换成了两个源真坏了 12 天**。按 `:1484-1512` 同口径复算
   `current.json`：14 个必需源 12 合格、2 不合格 —— `documents`（`PARTIAL`，
   上次成功距今 286.5h）、`strategy`（`PARTIAL`，305.5h）。原故障遮蔽了它们：
   修好 `scheduler` 之前，A9 的 detail 只显示 `diagnostic command exit 2` 那条路径。
3. **`PARTIAL` 不在 A9 的准入标签集内**。`:1504-1511` 接受 `OK`/`DEFERRED`，
   以及 6h 界内的 `STALE_UNAVAILABLE`/`FAIL`；`PARTIAL`（部分成功）**任何年龄都不被接受**。
   这与同处注释「标签会因采集器而异……却只有一个被接受」是自同一类问题，
   但放宽准入集是门语义裁决，不由本次部署顺带完成 —— 记为待裁决，不在本 BET 范围。

## 6 台账为什么不改

- `value` 轴的合法取值只有 `NOT_PROVEN / REJECTED / ACCEPTED`（`bin/plan/bet-ledger.py:440`），
  且 `value_indicator_policy=false` **强制** `value.status=NOT_PROVEN`（`:1940-1943`）。
  本 BET 入账时即 `value_indicator_policy: false`，所以 §2 的证据不能、也不应转成
  `ACCEPTED`（那要求 policy=true 与真人签名，且 `overall_state` 会从 `delivery_accepted`
  变 `outcome_accepted`，:3049）。
- `delivery_accepted` 仍由 `VERIFIED + PROVEN + NOT_PROVEN` 正确派生（`:1948-1951`），
  无需改写。
- 因此本 BET 的 ledger 条目一字未动；部署证据以本追加文件承载，`bet_id` 已绑定可检索。
