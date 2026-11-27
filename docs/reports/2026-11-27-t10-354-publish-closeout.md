---
schema: md/v1
status: completed
lifecycle: evidence
owner: xiamingxing
last-reviewed: 2026-11-27
type: report
bet_id: BET-Y2Q4-T10-354
title: BET-Y2Q4-T10-354 发布面收口 — host-mirror publish + 线上复测，done_when 三条全绿
---

# BET-Y2Q4-T10-354 发布面收口回执

前置回执：`docs/reports/2026-11-26-t10-354-post-merge-verification.md`（结论：done_when#3 真值
为 `drifted`，BET 暂不置 done）。本回执是它的**后续动作与复测**，承接该结论：模板修复已入主干，
但**发布面未吃到**。

## 做了什么（动作面）

| 步骤 | 命令 / 通道 | 结果 |
|---|---|---|
| 发布镜像 | `python3 bin/gac/zhixing-host-sync.py publish`（托管通道；`apply`/`capture` 在 `BLOCKED_COMMANDS`） | release 由 `releases/4ac8447107408c48bc03ca8a54cce241bd304376` 切到 `releases/8f43efedc4e04e80e7612a68c6be046f4950c6cb`，`current` 符号链接原子换指 |
| 回滚演练位 | `python3 bin/gac/zhixing-host-sync.py restore` | 保留在通道内（`current` 指回上一 release），未触发 |
| 进程重绑 | `launchctl kickstart -k gui/$(id -u)/com.omostation.zhixing-dashboard` | 见下「一次自伤与自愈」 |

## done_when 逐条复测（2026-11-27 00:3xZ 读数）

| 条款 | 判据 | 本次实测 | 判定 |
|---|---|---|---|
| #1 模板 `D.<7 字段>` 引用清零 | `rg -c "D\.(anomaly_events\|current_findings\|library\|live_sources\|pending_publications\|reconciliation_candidates\|value_loop)\b" bin/panorama/assets/host/template.html` | rc=1、零输出（零命中） | 达成 |
| #2 守卫 dry-run missing 7 → 0 | 复刻 `bin/panorama/panorama-collect.py::_check_template_data_consistency`（refs = `set(re.findall(r"D\.([a-z_][a-z0-9_]*)", tpl))`，missing = refs 中 payload 缺席/为空者）× live payload（revision `5ebfcafa…`，114 顶层键） | SSOT 模板 refs **55**、missing **0**；release 模板 refs **55**、missing **0**；对照宿主根 stale 副本 refs **62**、missing **7**（恰为那 7 字段，即改前基线） | 达成 |
| #3 `zhixing-host-sync.py check` 维持 in_sync | `python3 bin/gac/zhixing-host-sync.py check` | rc=0，`ok: true`，`write_performed: false`，`source_tree.stale: false`、`behind_origin_main: 0`，`target_root = releases/8f43efedc…` | 达成 |

## 线上实测（不是纸面推断）

- `GET http://127.0.0.1:43191/health`：`code_drift: false`、`dashboard_code_oid: 8f43efedc4e04e80e7612a68c6be046f4950c6cb`、
  `projection_status: BOUND_FRESH`、`payload_age_seconds ≈ 290`。
- `GET http://127.0.0.1:43191/`：HTTP 200，17,642,533 字节（本次读数）。
- 发布侧守卫：发布器（`com.omostation.zhixing-projection-fullrefresh`，180s 周期）在 `ZHIXING_DASHBOARD_CODE_ROOT`
  指向的 release 面上取模板，**改后发布周期不再打印 `⚠️ template-data consistency: 7 fields`**（改前每次发布必打）。
- live payload 侧证：`source_states` 21 键齐备（含 `workflow.observed_at = 2026-11-27T00:19:36Z`）——
  即模板改读 `D.source_states`（4 处引用）后，swarm 面板拿到的是真实 21 源数据，而非恒 `NO_DATA`。

## 一次自伤与自愈（留痕，不美化）

publish 换指 `current` 之后，跑着的 `com.omostation.zhixing-dashboard` 进程仍绑定旧 release
（`/health` 报 `code_drift: true`、`dashboard_code_oid: 4ac84471…`、`projection_status: CODE_DRIFT`），
页面 503。根因是**进程未随符号链接换指而重绑**，不是模板问题。
处置按仓内既有模式（`bin/gac/panorama-refresh-guard.py` 同款）：`launchctl kickstart -k` 重启该
launchd job，8 秒后 `code_drift=false`、`dashboard_code_oid=8f43efedc…`、`projection_status=BOUND_FRESH`、
`GET /` 恢复 200。
**教训**：`publish` 的原子换指只保证**文件面**，不保证**运行面**；托管通道的发布动作必须连带
一次进程重绑，否则发布成功而线上 503。

## 残留引用归因（诚实记账，非本 BET 欠账）

线上页面仍可见 `D.live_sources` ×3、`D.pending_publications` ×2。逐处归因：

| 来源 | 文件 | 仓内 SSOT | 性质 |
|---|---|---|---|
| `D.live_sources` ×3 | `ui_extensions.js`（发布目录内为 legacy 资产，**本仓无源文件**） | 无 | 读的是 payload 从未提供的键（页面内 `"live_sources"` 键命中 0） |
| `D.pending_publications` ×2 | `workbench_ui.js`（源 `bin/panorama/assets/host/workbench_ui.js.asset`） | 有 | 同上，payload 从未提供该键（页面内 `"pending_publications"` 键命中 0） |

两处都是**改前即已死的引用**（payload 一直没有这些键，读取写法均为可选链/守卫式
`D.live_sources?.…`、`((D.pending_publications && …) || [])`），不构成模板退役引入的回归，
也不触发本 BET 的 circuit_breaker（页面 HTTP 200，无 JS 断链）。本 BET 的 done_when 口径是
**模板面**引用清零，该口径达成。

同时遗留两处**不属于本 BET 写面**的接缝，供后续单独立项（未擅自开面）：

1. 宿主根 `~/.local/share/zhixing-dashboard/template.html` 仍是 stale 副本（refs 62、missing 7）。
   本 BET 的 non_goals 明写「不动宿主根 stale 副本」，故保留。
2. `ui_extensions.js` 在本仓无源文件，却仍参与页面渲染（release 目录内为 legacy 资产）——
   属发布目录的资产溯源缺口。

## 结论

- 工程腿：PR #5586（squash 合并 `cd4ae2ec31bc39ce0dbf4281b39c26e57ed3ace7`）已落主干，模板面达成。
- 运行腿：托管发布通道已把修复推到线上，守卫告警消失、`check` 回到 `in_sync`、页面 HTTP 200、
  `source_states` 21 源数据在位 → `operational: PROVEN`。
- 价值腿：治理契约类交付，无真人验收样本 → `value: NOT_PROVEN`（`value_indicator_policy: false`）。
- `overall_state: delivery_accepted`。

## 复现命令

```bash
rg -c "D\.(anomaly_events|current_findings|library|live_sources|pending_publications|reconciliation_candidates|value_loop)\b" bin/panorama/assets/host/template.html   # rc=1
python3 bin/gac/zhixing-host-sync.py check                                                                            # rc=0, ok:true
curl -s http://127.0.0.1:43191/health                                                                                 # code_drift=false
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:43191/                                                        # 200
```
