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

## 5 发布后再测 A9：三条已核实事实 + 两条未决

**先记一次自我更正**：本节初稿把 A9 仍 PARTIAL 归因于「部署判定器旧于仓内 ⇒ 用旧判据」，
并写 `documents`/`strategy` 状态为 `PARTIAL`。复查后两处都不成立，已按下面的实测替换。
原因值得单独记：`current.json` 每 300s 被整体重写，**状态标签是瞬时量**，
把一次读数当定论就会错。

### 5.1 漂移的实际内容是事件台账根解析（与 A9 判据无关）

- 部署副本 `panorama-collect-main.py` sha 前缀 `fa7eb9c1…`，与 `origin/main` 的 `f891ad40…`、
  主工作区的 `e7f6a4b6…` **三方互异**（这是原 §5 里唯一站得住的部分）。
- 逐段比对（`difflib` n=0，共 66 行差异）后，差异**全部**集中在事件台账路径：
  `origin/main` 用 `from repo_root import …, event_ledger_path, …` 并在缺省时调
  `event_ledger_path()`；部署副本没有该导入，改由模块级常量
  `EVENT_LEDGER = os.environ.get("OMO_EVENT_LEDGER_DB", ROOT / "runtime/omo/event-ledger.sqlite3")`
  硬解析。⇒ 线上副本缺的是**事件台账根解析**那笔重构，属 ADR-0456 三根口径问题。
- **A9 判据不受此漂移影响**（已双检）：两副本的 `required_sources` 都是同一组 14 项
  （集合差为空）、准入标签判据行一致（`OK` / `DEFERRED` / 有界的 `STALE_UNAVAILABLE`,`FAIL`）、
  `_cockpit_source_reasons` 都存在、`cockpit_path` 同一表达式。
- 处置仍属运维裁决：有意保留 → `capture` 入仓；应更新 → 由 `publish` 带上该文件。本回执不代判。

### 5.2 同一轮内 `gates[]` 与 `source_states` 给出矛盾读数（未决）

对 `generated_at = 2026-11-10T02:15:25Z` **同一个文件同一轮**读数：

| 读数方式 | 结果 |
|---|---|
| 按 `panorama-collect.py:1504-1511` 判据复算 14 个必需源 | **不合格源 = 无** |
| 同轮 `gates[]` 里 A9 | `verdict=UNKNOWN`、`source_verdict=PARTIAL`、`detail="A9 evidence incomplete: cockpit_sources"` |

`verdict=UNKNOWN` 而 `source_verdict=PASS` 是 cockpit 适配层的**设计**而非缺陷
（`tests/test_zhixing_wrapper_base_source.py:87-88` 就是这么断言的；本轮 11/11 门都是 `UNKNOWN`，
其 `source_verdict` 分布为 PASS 5 / FAIL 3 / PARTIAL 1 / NOT_ADMITTED 2）。
但「复算无不合格源」与「A9 仍报 `cockpit_sources`」不能同时为真，且该 detail **没有带原因串**
（判据 `:1519` 会把 `_cockpit_source_reasons(...)` 一并接上），所以疑点在
`gates[]` 这一层的写入者与其取数轮次，不在准入标签集。**未决，建议立案。**

### 5.3 两个源的 `last_success_at` 已 12 天（durable 事实）

`documents` 286.9h、`strategy` 306.0h（约 12 天）没有成功观测。它们的 `status` 标签在不同轮次间
在 `PARTIAL` 与 `DEFERRED` 之间摆动（01:50 轮读到 `PARTIAL`、10:15 轮读到 `DEFERRED`
+ `error="Deferred: host load above budget"`）；`DEFERRED` 被 `:1508` **无条件接受**（不看年龄），
`PARTIAL` 则**任何年龄都不被接受**。⇒ 同一判据对同一对源可给出相反结论，
负载高的轮次反而让 A9 在这两项上通过。这与 `:1498-1503` 注释自陈的设计意图
（「真正的信号是年龄而不是状态标签」）方向相反，属门语义问题，同样**不在本 BET 范围**。

### 5.4 我这次发布对 A9 的实际效果边界

可归因于本次发布的只有：`"diagnostic command exit 2"` 从线上产物消失（1→0），
且 `scheduler` 的 `last_success_at` 从 2026-11-07T00:04Z 变为 2026-11-10T01:49Z。
10:15 轮 `scheduler.status` 又显示 `DEFERRED`（负载让步，`observed_at=01:59:42`），
这**不是**回归——它的上次成功仍在界内，判据照样接受。
A9 整体是否转 PASS 不由本 BET 决定，见 §5.2 / §5.3 两条未决。

## 6 台账为什么不改

- `value` 轴的合法取值只有 `NOT_PROVEN / REJECTED / ACCEPTED`（`bin/plan/bet-ledger.py:440`），
  且 `value_indicator_policy=false` **强制** `value.status=NOT_PROVEN`（`:1940-1943`）。
  本 BET 入账时即 `value_indicator_policy: false`，所以 §2 的证据不能、也不应转成
  `ACCEPTED`（那要求 policy=true 与真人签名，且 `overall_state` 会从 `delivery_accepted`
  变 `outcome_accepted`，:3049）。
- `delivery_accepted` 仍由 `VERIFIED + PROVEN + NOT_PROVEN` 正确派生（`:1948-1951`），
  无需改写。
- 因此本 BET 的 ledger 条目一字未动；部署证据以本追加文件承载，`bet_id` 已绑定可检索。
