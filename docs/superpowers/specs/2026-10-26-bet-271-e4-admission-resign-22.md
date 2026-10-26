---
schema_version: specification/v1
spec_version: 1.0.0
title: B3 E4 准入清单重签到 22 条 —— 三条异主线 launchd 服务的逐条取证与 exempt_labels 补登
bet_id: BET-Y2Q4-T10-271
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-26
---

# 目标

把 BET-Y2Q4-T10-259 署名的准入清单从 **19 条重签到 22 条**（逐条取证行齐备），并把 principal
于 2026-10-26 单独署名的**那 3 条**写进机读豁免面（`launchd_namespace.exempt_labels` 11 → 14）。
可测后果是 `--reality-check` 的 **E4 由 22 条降到 19 条**（`external` 桶 5 → 8），
`e4_prefix_ok` **仍为 false** —— 这是本轮的如实终态，不是半途：E4 的通过条件是「一条 E4 finding 都没有」
（§2.1 从判据本体导出），余下 19 条是署名面，逐条裁定不属于本轮授权范围。

本轮为什么要做：分区面自己红着的时候，「每批切完 `--reality-check` E2 仍为 0」这条 B4b 中止判据
没有参照系。重签让**判据的分母**从一份过期快照（19 条，2026-10-19）变成当次实测（22 条），
并把其中属主无歧义的 3 条从「未分区」挪到「已承认的外部服务」。

# 1 证据（2026-10-26 实测，读数产出检出 = `8bff1d90e`）

`--reality-check` 当前读数 `E1 drift=0 (ok)  E2 undeclared=0  E3 lint_debt=0  E4 prefix_ok=False`，
E4 列出 **22** 条。与 T10-259 清单（19 行）做双向集合比对：**新增 3 条，零条退出**。

| label | 实际执行的东西 | 调度形状 | env 条数 | mtime (UTC) | 字节 | sha256:16 | 仓内镜像 | registry 声明 | `launchctl print` |
|---|---|---|---|---|---|---|---|---|---|
| `com.fleetops.logrotate` | `/usr/bin/env uv run --script ~/Project/fleet-ops/tools/rotate_logs.py` | Calendar + RunAtLoad | 1 | 2026-10-24T09:40:28Z | 1052 | `3dfc5058ecb20b4d` | 无 | 未声明 | not running |
| `com.fleetops.sync` | `/bin/sh ~/Project/fleet-ops/tools/sync_state.sh` | StartInterval + RunAtLoad | 0 | 2026-10-23T13:56:08Z | 722 | `8e761c20773b6720` | 无 | 未声明 | not running |
| `com.localbrain.ops-engine` | `/usr/bin/python3 ~/Project/work-agent/scripts/ops_engine/main.py`（WD 同目录） | RunAtLoad + KeepAlive | 2 | 2026-10-21T08:45:37Z | 2045 | `3f92fb4459fdadda` | 无 | 未声明 | **running** |

三条的共同形状：源码在**其它工程线**的仓里（`Project/fleet-ops`、`Project/work-agent`），
本仓既不生成它的 plist，也没有它的 registry 条目 —— 与 T10-259 已签的 #1–#12（`com.local.*` /
`com.valvesoftware.*`）同类，而非 `com.localbrain.*` #13–#16 那条「待署名」分支，因为 #13–#16
悬而未决的是「work-agent 是否要移交本仓管辖」，而本轮新增两条 `com.fleetops.*` 的属主没有歧义。

# 2 决策与准入机制的选择

`.omo/_truth/registry/services.yaml` 的 `launchd_namespace` 提供两条互斥机制（T10-259 spec §「机制」表原文）：

- `workspace_prefixes` 追加前缀 —— 命中即归 `workspace` 并进 E2 等式。**本轮不采用**：它会把该前缀下
  所有 plist 一次性拉进本仓管辖，任何一条未登记立刻让 E2 变红（`com.localbrain` 前缀下已有 5 条，
  其中 4 条仍待署名）。
- `exempt_labels` 追加**逐条精确**条目（`label` + `classification` + `reason`）—— 本轮采用。
  注册表自身的注释（`:6339-6341`）就要求豁免面收窄到具体 label，「新装的第三方 job 才不会自动落进
  豁免清单」，所以补登必须是三条具名条目，不能写成前缀。

## 2.1 E4 的通过条件（判据本体，读自源码而非倒推）

`bin/mof/gen-service-configs.py:773`：`"e4_prefix_ok": not any(f.startswith("E4") for f in findings)`；
`:684`：只要 `buckets["unmanaged_unknown"]` 非空就 append 一条「E4 未分区 label N 条」。
⇒ `prefix_ok=True` 要求**全部**本机 label 落入 workspace / owned / external / unclassified 四桶之一，
补登 3 条只把计数 22 → 19，不可能归零。这条在本轮授权之前就该说清楚，见 §7。

分类：`com.fleetops.logrotate` 与 `com.fleetops.sync` = `external`（fleet-ops 属主）；
`com.localbrain.ops-engine` = `external`（work-agent 属主，与 #13–#16 同族但本条**正在运行**，
故 reason 里如实写运行态，供后续 work-agent 管辖裁定时一并处理）。

# 3 done_when

1. `--reality-check` 读数：E4 由 **22 条降到 19 条**、`external` 由 5 变 8，且
   E1/E2/E3/`unclassified`/`owned_declared=owned_installed`/`registry_declared_total`/`installed_total`/E5
   **逐字段未变**（豁免面只改归类，不改本机装了哪些 job）。`e4_prefix_ok` 保持 false 并已在 §2.1 说明原因。
2. T10-259 准入表补 3 行（#20–#22），行数 = **22**，与该次 `--reality-check` 的**全部 22 名**（19 条仍在
   E4 + 3 条已进豁免面）**双向相等**（`missing=[] extra=[]`）；另外单独断言「live E4 的 19 名 ⊆ 表内前 19 行」。
3. `exempt_labels` 由 11 条增至 14 条，新增三条各有 `label`/`classification`/`reason`，
   且 `services.yaml` 仍是**单文档 `services` 与 `launchd_namespace` 同档**（`:6342-6343` 那条禁令）。

# 4 验收（每条都可在干净检出复算）

- 复算命令 A：`python3 bin/mof/gen-service-configs.py --reality-check` ⇒ 期望读数
  `E1 drift=0  E2 undeclared=0  E3 lint_debt=0  E4 prefix_ok=False` + 「本机 81 = workspace 48 +
  unclassified 0 + external 8」 + 「E4 未分区 label **19** 条」，E5 仍 1+1。
- 复算命令 B：Python 取 `--reality-check --json` 的 E4 名单（19 名）与本表 #1–#19 逐名对拍，
  再取「19 名 + §1 三条 = 22 名」与本表 #1–#22 对拍 ⇒ 两侧 `missing=[] extra=[]`。
- 复算命令 C：`yaml.safe_load_all(services.yaml)` 取 `docs[-1]` 同时含 `services` 与
  `launchd_namespace.exempt_labels`，且豁免条目数 = 14、三条新条目的 `classification` 均为 `external`。
- 复算命令 D：既有回归四个文件（注册表面，2026-10-26 实测存在）
  `tests/test_service_registry_reality.py`、`tests/test_gen_service_configs.py`、
  `tests/unit/test_reality_check_kernel_root_pin.py`、`tests/unit/test_gen_service_runtime_root.py`；
  本轮零 Python 改动，故判据是「零回归」而不是「新增通过」。装置要求：这四条用例经
  `bin/lib/repo_root.canonical_root()` 取根，必须显式钉 `OMOSTATION_ROOT=<被测检出>`，
  否则在 `HOME=<空>` + `env -u OMOSTATION_ROOT` 下 `workspace()` 直接 `RuntimeError`
  （实测 2 failed，红的是装置定位不到根，不是断言失败）。
  实跑命令与读数见 closeout receipt §2。
- `bet-ledger.py lint` 零 error；`doc-governance-check --no-new-warnings --scope tracked` 基线告警数不变。

# 5 非目标

- **不动运行面**：不 `bootstrap`/`bootout`、不翻 `enabled`、不改任何 `~/Library/LaunchAgents` 文件、
  不碰 crontab。补登只是「承认现实并已看过」，不是接管。
- 不裁定 `com.localbrain.*` #13–#16 是否移交本仓管辖（署名面）。
- 不宣布 B3/B4b/B5 或 ADR-0456 任何阶段完成。
- 不改 `workspace_prefixes`（§2 已述代价）。

# 6 回滚

revert 本 BET 的 squash commit ⇒ `exempt_labels` 回到 11 条、准入表回到 19 行、
`--reality-check` 的 E4 回到 22 条（`external` 回到 5）。零机器态变化，故回滚不需要任何运行面动作。
注意 T10-259 的 `accepted_specifications[0].content_digest` 与它的 `verify` 期望值也随本表重签而重算
（同一批内完成，字段路径见 T10-270 spec 的摘要刷新纪律）—— revert 会把这两处一并退回。

# 7 一处需要留痕的错话（授权文字与判据本体不符）

本轮向 principal 出选项时，把预期结果写成「**E4 归零**」。那是**在读 `:773` 之前**写下的措辞：
我按「22 条 = 清单 19 条 + 新增 3 条」倒推，以为补登 3 条就清了；实际清单那 19 条只签在文档里，
**从未进入机读豁免面**（T10-259 §6 明确「不为凑 `ok=true` 把任何 label 塞进 `services.yaml`」），
所以豁免面当时只有 11 条，E4 的归零需要 22 条全部有名有归处。

处置：授权范围按 principal 的原话执行（补登 3 条 + 重签清单），**不**擅自把余下 19 条塞进豁免面来
凑 `prefix_ok=True` —— 那正是 T10-259 §6 与 #124 划给署名的面。不符的那句话在本 spec（§2.1/§3/§4）、
准入表 §1.1、台账 `done_when` 与 receipt 四处同步更正，并作为一条可复用判据进 retro：
**给 principal 的选项里凡是「门禁会变成什么读数」的承诺，必须先从门禁的 pass 条件源码导出，
不能从「待办清单少了几项」倒推。**
