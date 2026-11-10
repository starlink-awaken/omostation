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

证据文件（两个平面各按自己的 `generated_at` 轮次读数，不跨平面混比）：
`~/.local/share/zhixing-dashboard/current.json`（聚合平面，`current/orchestrator.py` 每 300s
新起进程写出的运行时快照）与 `revisions/*/data.json`（生产者平面）。

| 读数 | 发布前 | 发布后 |
|---|---|---|
| `"diagnostic command exit 2"` 全份出现次数 | **1** | **0** |
| `source_states.scheduler.status` | `STALE_UNAVAILABLE` | `OK` |
| `source_states.scheduler.error` | `Collection failed for 'scheduler': diagnostic command exit 2` | 键不存在 |
| `source_states.scheduler.last_success_at` | `2026-11-07T00:04:27Z` | `2026-11-10T01:49:14Z` |
| A9 `detail`（revision 平面 `data.json`，带原因串） | `…cockpit_sources, strategy=PARTIAL; documents=PARTIAL; scheduler=STALE_UNAVAILABLE(Collection failed for 'scheduler': diagnostic command exit 2)` | `…cockpit_sources, strategy=PARTIAL; documents=PARTIAL` —— **`scheduler` 项消失** |
| A9 `detail`（聚合平面 `current.json`） | 同上短语可见 | `A9 evidence incomplete: cockpit_sources`（**原因串在此平面被截断**，见 §5.3） |

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

## 5 发布后再测 A9：已核实事实与未决项

**本节被重新测量推翻过五次**，错在哪、被什么否证都留在 §5.4/§5.4b 与提交历史里，不再重述推理：
只保留可复现的读数与代码出处。这一节因此比初稿长，但它是我能给出的最强形态——每条都能被
第三方用同样的命令复算。

### 5.1 修复在线上生效的最强证据：原因串里 `scheduler` 项消失

按轮次读 `revisions/*/data.json` 的 A9 `detail`（该平面带 `_cockpit_source_reasons` 全文）：

| 轮次（本地时钟） | A9 detail 的原因部分 |
|---|---|
| 09:48:18（发布前最后一轮） | `strategy=PARTIAL; documents=PARTIAL; scheduler=STALE_UNAVAILABLE(Collection failed for 'scheduler': diagnostic command exit 2)` |
| 09:52:04（发布后第一轮） | `strategy=PARTIAL; documents=PARTIAL` —— **`scheduler` 不再出现** |

与 §2 的 `source_states.scheduler`（`STALE_UNAVAILABLE` → `OK`、`last_success_at`
2026-11-07 → 2026-11-10）互相独立地指向同一结论：`exit 2` 在线上通路已消除。

### 5.2 A9 仍 PARTIAL 的原因是两个源 12 天没有成功观测（durable）

02:21:04 轮 `current.json` 与 01:58:14 轮 `data.json` 对这两项读数一致：
`strategy.status=PARTIAL`、`last_success_at=2026-10-28T08:18Z`（约 306h）；
`documents.status=PARTIAL`、`last_success_at=2026-10-29T03:22Z`（约 287h）。
判据 `panorama-collect.py:1504-1511` 接受 `OK`/`DEFERRED`/有界的 `STALE_UNAVAILABLE`,`FAIL`，
**`PARTIAL` 任何年龄都不被接受** ⇒ 这两项独立于本次修复，是 A9 现存的真实缺失证据，
此前被 `scheduler` 的 `exit 2` 排在同一 detail 里而不显眼。

### 5.3 聚合平面丢失诊断信息（未决，值得立案）

同一轮同一底层判定，两个平面写出的 A9 记录不同：

| 平面 | `verdict` | `detail` |
|---|---|---|
| `revisions/*/data.json`（生产者产物） | `PARTIAL` | 带完整原因串 |
| `current.json`（聚合产物） | `UNKNOWN` + `source_verdict=PARTIAL` | 在 `cockpit_sources` 处**截断**，原因串丢失 |

`verdict=UNKNOWN` 而 `source_verdict=PASS/FAIL/PARTIAL` 是 cockpit 适配层的设计，不是缺陷
（`tests/test_zhixing_wrapper_base_source.py:87-88` 直接断言此形状；本轮 11/11 门都是 `UNKNOWN`，
`source_verdict` 分布 PASS 5 / FAIL 3 / PARTIAL 1 / NOT_ADMITTED 2）。
但 `detail` 在聚合时被截掉原因，**正好重新造出** `panorama-collect.py:1513-1516` 注释里
2026-10-23 那次要消灭的现象（「只看得到 `cockpit_sources` 时无法分辨原因，得人工翻 cockpit current.json」）。
截断点在哪一层未查，属新缺陷。

### 5.4 生产者身份字段不构成发布的证据（我前几版都读错了，此处只留实测）

保留窗口内 48 份 `revisions/*/manifest.json` 的 `producer.collector_sha256` **恒为** `f891ad40…`
（= `origin/main` 上 `bin/panorama/panorama-collect.py` 的内容），`producer.root_oid` 在
11-09 23:28Z 由 `afcee8ef2…` 跳到 `697151a9…`。两者都早于我 11-10 01:48Z 的发布。
⇒ 这些字段与本次 publish **没有可证的因果关系**，我前三版把它当成"哪份判定器在执行"的证据是错的。

publish 这次真正改变的只有一件事，按字节可复算：

| 发布前 release `17afa5408…--pub-0c898071…` | 发布后 release `697151a9…` |
|---|---|
| `collectors/scheduler.py` `28ad3162…`，内含 `--json` **2 处** | `collectors/scheduler.py` `51f2b281…`，内含 `--json` **0 处** |
| `panorama-collect-main.py` `fa7eb9c1…`（`--json` 15 处，未变） | 同哈希、同样 15 处（未变） |
| 清单 `schema = v2`，带 `publication_id` | 清单 `schema = v1`，`publication_id = null` |

**别把 15 处 `--json` 读成缺陷仍在**：那是 collector/main 各自 CLI 的正常参数；A9 的幻影参数只在
`collectors/scheduler.py` 的诊断命令行里，那 2 处已归零，与 §2 的 `scheduler.status` 和 §5.1 的
原因串消失互相独立地对上。清单 schema 从 v2 变 v1 是因为发布脚本取自我 `697151a9` 那份源树
（`_ROOT` 按 `__file__` 解析），不是配置项——这条也说明"用哪棵树发布"会改变产物形态。

**未决**：`root_oid` 的来源没定论。新清单 mtime 是 09:48（我的发布），而 `root_oid=697151a9`
在它出现之前 2.5h 就已经写进 revision，所以该值不是从我这份清单读的；
`panorama-collect.py:571-582`（有 `.zhixing-host-release.json` 时走 `release_identity.py`）
与 `:585-588`（现场 git 根要求 `code_oid == refs/remotes/origin/main`）两条路都能产出形如观测的值，
实际走的是哪条、`ZHIXING_DASHBOARD_CODE_ROOT` 指向何处，我没有查出来，不在此断言。

### 5.4b 常驻进程仍指向发布前的 release（运维事实，非缺陷断言）

`live_server.py`（pid 50155）的 cwd 仍是发布前的
`releases/17afa5408a…--pub-0c898071…`，而 `current` 已指向 `releases/697151a9…`。
publish 只翻转符号链接，300s 刷新任务是每次新起 `current/orchestrator.py` 进程才吃到新代码，
常驻服务进程不换。⇒ 本次修复生效的是**刷新/投影通路**；服务进程内旧代码的影响面未测，
是否重启 `com.omostation.zhixing-dashboard` 属运维决定，我没有动它。

### 5.5 发布继承漂移这一条仍然成立（代码事实）

`_prepare_version` 从 base release 整树复制再叠加所选文件（`zhixing-host-sync.py:313-332`），
实测发布后新 release 的 `panorama-collect-main.py` 仍为 `fa7eb9c1…`（与 base 相同）。
⇒ 单文件发布既不修正也不掩盖同目录其他文件的漂移。

## 6 台账为什么不改

- `value` 轴的合法取值只有 `NOT_PROVEN / REJECTED / ACCEPTED`（`bin/plan/bet-ledger.py:440`），
  且 `value_indicator_policy=false` **强制** `value.status=NOT_PROVEN`（`:1940-1943`）。
  本 BET 入账时即 `value_indicator_policy: false`，所以 §2 的证据不能、也不应转成
  `ACCEPTED`（那要求 policy=true 与真人签名，且 `overall_state` 会从 `delivery_accepted`
  变 `outcome_accepted`，:3049）。
- `delivery_accepted` 仍由 `VERIFIED + PROVEN + NOT_PROVEN` 正确派生（`:1948-1951`），
  无需改写。
- 因此本 BET 的 ledger 条目一字未动；部署证据以本追加文件承载，`bet_id` 已绑定可检索。
