---
schema: md/v1
status: completed
lifecycle: report
type: closeout-receipt
owner: governance-team
last-reviewed: 2026-10-26
bet_id: BET-Y2Q4-T10-271
---

# BET-Y2Q4-T10-271 收口 receipt —— E4 准入清单重签到 22 条，三条异主线 launchd 服务具名补登

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-271`
规格：`docs/superpowers/specs/2026-10-26-bet-271-e4-admission-resign-22.md`
准入对象：`docs/superpowers/specs/2026-10-19-b3-admission-review-checklist.md`（T10-259，19 → 22 行）
注册表：`.omo/_truth/registry/services.yaml` `launchd_namespace.exempt_labels`（11 → 14 条）
工程腿：PR #4902 → squash `63d389ceea932ad5242e992346626318d2f411a5`（分支 commit `a4e1b34b1` + `1bdc5d696`，4 文件 +265/−10）
收口腿：分支 `agent/governance-agent/bet271-closeout`，run `20261026T064932Z-project-doc-change-45ffde6b`

## 0 交付性质（先把边界说清）

文档面 + 注册表面，**零 Python 改动**（merge-base 起 `.py` 计数 = 0），**零运行面动作**：
本机 launchd 未 `bootstrap`/`bootout`、`enabled` 未翻、`~/Library/LaunchAgents` 一行未改、
crontab 未碰。补登的语义是「承认现实并已逐条看过」，不是接管 —— `com.localbrain.ops-engine`
实测正在运行，归 `external` 只表示本仓不生成不接管，**不构成**对本仓管辖权的裁定。

## 1 前后读数（同一台机器，两个 registry 版本）

检出基线 `8bff1d90e` 的注册表 → 合并后 `63d389cee` 的注册表；除下列两项外**逐字段相同**：

| 字段 | 前 | 后 |
|---|---|---|
| `e1_drift` | 0 | 0 |
| `e2_undeclared` | 0 | 0 |
| `e3_lint_debt` | 0 | 0 |
| `unclassified` | 0 | 0 |
| `installed_total` | 81 | 81 |
| `workspace_scoped` | 39 | 39 |
| `owned` | 48/48 | 48/48 |
| `registry_declared_total` | 75 | 75 |
| `external` | 5 | **8** |
| **E4 未分区 label** | **22 条** | **19 条** |
| `e4_prefix_ok` | False | False |
| E5 两项 | 1 + 1 | 1 + 1 |

补登的三条（`com.fleetops.logrotate` / `com.fleetops.sync` / `com.localbrain.ops-engine`）
各自带 argv、调度形状、env 条数、UTC mtime、字节数、sha256:16、仓内镜像有无、launchctl 态
与 principal 2026-10-26 署名，取证行见 spec §1。

## 2 验收复算（每条都在干净检出可重跑）

| # | 判据 | 读数 |
|---|---|---|
| 1 | `python3 bin/mof/gen-service-configs.py --reality-check --json` 逐字段断言 | `e1=0 e2=0 e3=0 unclassified=0 external=8 installed=81 workspace_scoped=39 owned=48/48 declared=75 prefix_ok=False e5=1+1 findings=3`，rc=0 |
| 2 | 豁免面结构断言（单文档同档 + 三条新条目） | `services_in_last_doc=True exempt=14 new=3 all_external=True` |
| 3 | T10-259 准入表 ↔ live E4 名单双向集合比对 | `rows=22 e4=19 missing=[] extra=[]` |
| 4 | T10-259 spec sha256 与台账绑定一致 | `955de80b6ce0ca58c1cb5d54fbe1ef49108c83fe0b76eeac4e01477fb0731804` |
| 5 | `python3 bin/plan/bet-ledger.py lint` | `OK -- 567 bets, 16 tracks, no errors` |
| 6 | merge-base 起 `.py` 改动计数 | `0` |
| 7 | 注册表面回归四文件（`tests/test_service_registry_reality.py`、`tests/test_gen_service_configs.py`、`tests/unit/test_reality_check_kernel_root_pin.py`、`tests/unit/test_gen_service_runtime_root.py`） | `72 passed`，rc=0 |
| 8 | `python3 bin/ssot/doc-governance-check.py --no-new-warnings --scope tracked` | `PASS (4690 files, 31 warnings)`，rc=0 |
| 9 | `python3 bin/gac/gac-local-gate.py --scope staged --json`（逐 lane 各一次） | 两轮均 `ok=True hard_fails=[]`；唯一非 skip 失败项 `current-state-coherence`（worktree 无 `.omo/state/system.yaml`，T10-235 摘库后为常态软告警，预存） |
| 10 | 合并后独立复算：`git show origin/main:.omo/_truth/registry/services.yaml` 物化到临时文件后跑 `--reality-check --registry <该文件>` | 与判据 1 逐字段相同（证明读数来自**已合并的那份注册表**，不是我的在制工作树） |

判据 7 的装置要求：这四条用例经 `bin/lib/repo_root.canonical_root()` 取根，必须显式钉
`OMOSTATION_ROOT=<被测检出>`；在 `HOME=<空目录>` + `env -u OMOSTATION_ROOT` 下会读到
2 failed，红的是 `workspace()` 定位不到规范检出（`RuntimeError`），不是断言失败 ——
本轮零 Python 改动，该装置敏感度是预存的，不是回归。

## 3 真实终态是 E4 = 19，不是 0

门禁 pass 条件读自源码：`bin/mof/gen-service-configs.py:773`
`"e4_prefix_ok": not any(f.startswith("E4") for f in findings)`，而 `:684` 只要
`buckets["unmanaged_unknown"]` 非空就打印「E4 未分区 label N 条」。
⇒ `prefix_ok=True` 要求**每一条本机已装 label 都被分区**，本轮补登 3 条只把 22 降到 19。

剩下 19 条的署名面（按族分好，便于后续逐族裁定）：

| 族 | 条数 | 悬而未决的是什么 |
|---|---|---|
| `com.local.*` | 13 | 属主清楚（本机私有运维工具），可族裁为 `external`；但 T10-259 §6 明确拒绝「为凑 `ok=true` 把 label 塞进 `services.yaml`」，族裁也是一次署名动作 |
| `com.localbrain.*` | 4 | 待裁定的是「work-agent 线是否移交本仓管辖」（#13–#16），不是取证 |
| `com.valvesoftware.steamclean` | 1 | 第三方 app 自注册，取证已齐 |
| `com.xiamingxing.benchq-watch` | 1 | 署名面 |

另 E5 两项按判据原样留存，均为 principal 决定：`com.l4.omo.sync`（声明 `enabled=true`
但本机未装）、`com.cockpit.dashboard`（声明 `enabled=false` 但本机仍装）。
本轮不宣布 B3 收口，也不宣布 ADR-0456 任何阶段完成。

## 4 一处需要留痕的错话（可复用规则）

立项时给 principal 的选项文案写的是「E4 归零」。那句话是从「19 已签 + 3 新增 = 22 全签完」
倒推出来的，不是从门禁的 pass 条件导出的 —— 而 T10-259 的 19 行从来只是**文档面**，
从未进过 `exempt_labels`。规则已写进 spec §7：

> 给 principal 的选项里凡是「门禁会变成什么读数」的承诺，必须先从门禁的 pass 条件源码导出，
> 不能从「待办清单少了几项」倒推。

同批后果：改 spec 字节就要重算 digest，而这次牵连到**另一条已闭合的 BET**（T10-259 的
`content_digest` 与一处 `verify expect:` 裸十六进制串），两处都在同一批里同步（spec §6 记录）。

## 5 回滚

revert 收口腿 ⇒ 只撤 receipt/retro 与台账 `done`；revert `63d389cee` ⇒ `exempt_labels` 回 11 条、
准入表回 19 行、E4 回 22 条。零机器态变化，回滚不需要任何运行面动作。
注意这条回滚是**两半分仓的**：注册表与清单在同一个 squash commit 里，但 digest 耦合使
「只回滚文档面」会让台账绑定与 spec 字节不一致（lint 会红），回滚要整批 revert。
