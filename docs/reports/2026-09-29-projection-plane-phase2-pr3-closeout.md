---
schema: md/v1
status: active
lifecycle: report
owner: governance-agent
last-reviewed: 2026-09-29
type: report
---

# B5 / ADR-0129 Phase 2 — PR-3 (读取面) closeout

BET-Y2Q4-T10-212 · ADR-0456 B5 · contract `docs/superpowers/specs/2026-09-28-projection-plane-phase2-untrack.md` (v1.1.0)

## 1. 这轮解决的是哪一类缺陷

PR-2 把三件生成态（`.omo/state/health.yaml`、`.omo/_control/governance-data.json`、`BRIEF.md`）
摘出 git 之后，**硬编码 legacy 路径的读取方只有两种结局**：读到一份再也无人更新的冻结文件，
或者什么都读不到。而"什么都读不到"在过去一律被折算成一个**结论**，不是一个空缺：

| 读取方 | 缺失被折算成 | 下游后果 |
|---|---|---|
| `bin/gac/unified-health-score.py` | 运行时轴 `0.0` | 权重 0.10 的假测量拉低 UHS，`--sync` 还把这个假值写进 `system.yaml::health_score` |
| `bin/ssot/health-predict.py` | 退出码 `1` | cron 面把"没跑过"报成"坏了" |
| `bin/gac/maturity-align.py` | `reconciliation_score = 100.0` | 只剩一个可测来源时 spread 恒为 0 ⇒ 缺席冒充满分一致性，再按权重进健康分 |
| `projects/omo/src/omo/omo_doctor.py` | `status: fail` | 新建检出必红 |
| `bin/gac/check-dual-track-purity.py` | 读冻结的根 `BRIEF.md` | 用已废弃的那一份判违规 |

第二类缺陷不是"缺失被折算"，而是**同一份证据在两个读取方那里有两个口径**，它们同样造出假红，
且是台账 goal 里点名的"顺带治一处既有假红"：

| 缺陷 | 机制 | 实测（生产 `~/Workspace`） |
|---|---|---|
| epoch 时间戳判成 9999h | `probe-heartbeat-monitor._age_hours` 只走 `fromisoformat`，而 `system_health.yaml` 的 `last_scan` 是 epoch 浮点 | `系统健康巡检 9999h/48h` → `0.5h/48h`，`rc 1 → 0`，其余 7 项逐字不变 |
| JSON 投影的戳取不到 | `meta-doctor` 行扫描匹配 `generated_at`，而 `governance-data.json` 的键是带引号的 `"generated_at":` | 同一文件 probe 判新鲜 2.8h、meta-doctor 判陈旧 ⇒ 新增该心跳后 `stale 1 → 0` |

PR-3 的统一不变量：**读取方不得自证投影位置；"没生成"与"跑过但老化"必须是两个不同的计；
同一份证据只能有一个口径。**

## 2. 机制（一个表，两侧根）

`bin/lib/repo_root.py` 新增读取侧解析，登记表 `.omo/_truth/registry/runtime-projections.yaml` 是唯一真源：

- `projection_rels(name, *, registry_root=None) -> (canonical_rel, legacy_rel)` —— 返回**相对**路径，
  让每个读取方把自己那一侧的根（`--workspace` / `state_root` / `code_root`）锚上去；未登记名抛 `KeyError`。
- `projection_read(checkout_root, name, *, registry_root=None, state_root=None) -> (Path, "canonical"|"legacy")`
  —— canonical 锚到 `state_root`（缺省为 checkout），legacy 锚到 checkout；canonical 在就读 canonical，
  否则退回 legacy。**不判存在性**：调用方拿 Path 自己判 absent，于是 absent ≠ expired ≠ 满分。
- `projection_name_for(rel)` —— legacy 相对路径反查投影名（probe-heartbeat 的矩阵键仍是 legacy 路径，
  为了报表连续性；读哪个文件这个问题只有一个答案）。
- 登记表解析只用 stdlib（2/4 缩进扫描），**不 import yaml** —— `meta-doctor` 与 cron 用裸 `python3` 跑，
  依赖 pyyaml 会在那里 ImportError。逐名与 `yaml.safe_load_all` 的对拍由测试钉住。
- 登记表不在本检出时（无 `.omo` 的工具克隆）退回 `_PROJECTION_FALLBACK_RELS`，值与今日登记表逐字一致。

`meta-doctor.check_heartbeats(ws_root, now=None, state_root=None)` 的 profile 解析写在**函数内部**：
`state_root` 省略且 `ws_root` 就是本仓时取 `state_root()`，显式 `--workspace` 覆盖时"指哪读哪"，
不叠加 profile。这个位置是被 tracked 守卫 `tests/unit/test_gate_health_roots.py` 钉住的：它把
`check_heartbeats` 猴补成 `lambda ws_root:`，所以 profile 解析不能上提到 `main()` 的参数里（见 §6.6）。

`projects/omo/src/omo/omo_paths.py` 侧同样收成一张表：新增 `projection_rels(name)`，
`projection_path()` 改为 canonical 挂 `STATE_ROOT`、legacy 挂 `WORKSPACE_ROOT`，
删掉此前分叉的内联 `STATE_DIR` / `CONTROL_DIR` 回退（两条锚定规则并存的形态消失）。

## 3. 原地 A/B（spec §4-8）

夹具：`git archive` 出两棵同深度树 —— `before` = `origin/main`，`after` = `HEAD` + 本 PR 工作树文件；
`bin/`、`.omo/`、`.github/`、`docs/scene-cards` 一并铺开（读取方用 `__file__` 上溯两层取根，层深必须一致）。
三档投影形态，其中 **fresh 档就是本机今天的生产形状**（canonical 在、legacy 已被 PR-2 摘走）：

- `none` —— 两档皆无（fresh clone）
- `fresh` —— canonical 在、legacy 无（生产现状）
- `dual` —— 两档都在，legacy 是 2026-03-04 的冻结副本（`service_online_ratio: 0.500`、`health_score: 61`）

字段形状取 `~/Workspace/.omo/state/runtime/health.yaml` 的真实形态，所以两档都能被解析，
唯一变量是**读哪一档**。以下数字是 2026-09-29 收口时同一夹具重跑的。

### 3.1 `unified-health-score.py`

| 形态 | before | after |
|---|---|---|
| none | rc=0，`scores.runtime=0.0`，UHS `31.4`；`--sync` 把 `system.yaml::health_score` 写成 `31` | rc=0，`runtime=null`，`unscored_axes=['runtime']`，UHS `34.9`；`--sync` **不写**（保持检出原值 `46`），stderr `⚠️ sync 跳过: runtime 投影未生成, 不写 system.yaml::health_score` |
| fresh | rc=0，`runtime=0.0`，UHS `31.4`；`--sync` 写 `31`（**现成的 canonical 测量被记成 0**） | rc=0，`runtime=100.0`，UHS `41.4`；`--sync` 写 `41` |
| dual | rc=0，`runtime=50.0`（读冻结 legacy），UHS `36.4`；`--sync` 写 `36` | rc=0，`runtime=100.0`（读 canonical），UHS `41.4`；`--sync` 写 `41` |

### 3.2 `bin/ssot/health-predict.py`

| 形态 | before | after |
|---|---|---|
| none | **rc=1** `⚠️ health.yaml 不存在或无有效字段` | rc=0 `health 投影未生成: .omo/state/health.yaml (canonical 与 legacy 皆缺) — 跳过预测` |
| fresh | **rc=1**（同上，读不到 canonical） | rc=0，`current_scores={health_score: 74.0, freshness_score: 100.0, drift_score: 5.0}` |
| dual | rc=0，报冻结值 `61.0 / 12.0 / 40.0` | rc=0，报现值 `74.0 / 100.0 / 5.0` |

### 3.3 `bin/gac/maturity-align.py`

| 形态 | before | after |
|---|---|---|
| none | rc=0，读 `.omo/state/health.yaml`，`health_score=null`，**`reconciliation_score=100.0`** | rc=0，同路径但显式 `projection_source=legacy`，`health_score=null`，`reconciliation_score=null` |
| fresh | rc=0，`health_score=null`（**现成的 canonical 测量没被读**），`reconciliation=100.0` | rc=0，读 `.omo/state/runtime/health.yaml`，`health_score=74`，`reconciliation=92.0` |
| dual | rc=0，读 legacy=61，`reconciliation=95.0` | rc=0，读 canonical=74，`reconciliation=92.0` |

`reconciliation_score` 的口径修正：**一致性是两个观测之间的性质**。health 投影缺席时只剩
scorecard 一个来源，spread 恒为 0，那是"无从比较"而不是"完全一致"，所以 `100.0 → null`；
两档都有可测来源时才给出真值（`92.0`）。`drift_detected` 各档均为 `false`，未因缺来源而误报漂移。

### 3.4 `bin/gac/check-dual-track-purity.py`

| 形态 | before | after |
|---|---|---|
| none | rc=0，`ok=true`（无 brief 也无 legacy，恰好"对"） | rc=0，`ok=true`，`complete=false`，`status="skipped"` |
| fresh | rc=0 `ok=true`（读不到任何 brief，判成纯净） | rc=0 `ok=true`，`status="pass"`，读 canonical `.omo/state/runtime/brief.md` |
| dual | **rc=1**，2 条 `brief_throughput_leak`（`source: scenario`、`构造场景`）—— 全部来自已废弃的根 `BRIEF.md` | rc=0 `ok=true` `status="pass"`，findings 0 |

after 侧把"未生成"如实报成 `status="skipped"` + `complete=false`，不再伪装成一次成功的纯净检查。
`.omo/state/collab-dualtrack.yaml` 保持字面路径：它没有投影条目（`projection_rels` 会 `KeyError`），
且它是 tracked SSOT 而非生成态。

### 3.5 `projects/omo/src/omo/omo_doctor.py::_check_key_files`

按真实包深度铺 `<fx>/projects/omo/src/omo`（`WORKSPACE_ROOT = _MODULE_DIR.parents[3]` 自动落到 `<fx>`），
只变 health 投影的形态：

| health 投影 | before | after |
|---|---|---|
| none | `status=fail`，`missing: state/health.yaml` | `status=ok`，`5 key files present; health projection not generated (optional)` |
| 仅 canonical | **`status=fail`**（投影明明在，只是不在 legacy 位） | `status=ok`，`… health projection present` |
| 仅 legacy | `status=ok`，`6 key files present` | `status=ok`，`… health projection present` |
| dual | `status=ok`，`6 key files present` | `status=ok`，`5 key files present; health projection present` |

跟踪的关键文件仍是 fail-on-missing（那是权限面缺失，不是生成态缺失）；本轮只把投影从必存在清单里摘出来。

### 3.6 `probe-heartbeat-monitor.py` — 生产实测 + epoch 口径

同一份生产状态（`~/Workspace`，canonical 在、legacy 摘走），before/after 只差脚本版本：

| | before | after |
|---|---|---|
| 汇总 | `total=8 ok=7 failed=1 absent=0`，rc=1 | `total=8 ok=8 failed=0 absent=0`，rc=0 |
| 系统健康巡检 | `age=9999`（SLA 48h）→ 计为异常 | `age=0.5` → 正常 |
| 其余 7 项 | 逐字不变 | 逐字不变（且每项都带 `source=canonical\|legacy`） |

`absent` 语义（"未生成"不计为异常）由 `tests/unit/test_projection_reader_resolution.py` 的
`test_probe_heartbeat_monitor_reports_absent_projections_without_failure` 在 tmp 夹具里钉住；
生产这台机器上 8 项全在，所以它测的是同一函数的另一支。

### 3.7 `meta-doctor.py` — 心跳登记表化 + JSON 口径

- **absent ≠ stale 这一半是 PR-1（#4515）落的**：before 版已有 `absent` 标志与
  `stale_beats = [b for b in beats if not b["ok"] and not b.get("absent")]`。合成 fresh clone
  （只铺登记表与 tracked 文件）实测 before/after 均 `stale=0 / absent=3`，PR-3 没有把它改坏。
- PR-3 在这里做的是：删掉 meta-doctor 自己那份 `CANONICAL_HEARTBEATS` 映射，改走
  `projection_rels` / `projection_read`（登记表成为唯一真源）；把写根交给 profile（`state_root`）；
  并把 `governance_data` 纳入心跳。
- 新增心跳必须同时修戳口径，否则它是**新造的假红**：用 before 的行扫描逻辑读 PR-3 的心跳表，
  生产实测 `stale=1`（`.omo/state/runtime/governance-data.json`，实际 2.8h 新鲜）；
  `_stamp_field()` 走 `json.loads` 后 `stale=0 / absent=0`。同一份文件两个读取方口径一致。

## 4. done_when 逐条（spec §4）

| # | 判据 | 状态 | 由哪个 PR 关闭 |
|---|---|---|---|
| 1 | `omo_ingress_state.py` 三次 `_mirror_projection()` 与 `legacy_*_path` 消失 | ✅ | PR-2（omo #202） |
| 2 | 三个门禁读取方经解析器取路，且"canonical 尚无"与"跑过但老化"分计 | ✅ | PR-1 起头 + PR-3 收口（§3.6/§3.7） |
| 3 | `panorama-collect.py` 两处 `git checkout` pathspec 不再含 `BRIEF.md` | ✅ | **PR-2（`cf6d4ac78` / #4524）**，实测 `git log -S BRIEF.md -- bin/panorama/panorama-collect.py` 唯一命中 |
| 4 | `compass_radar` 两份副本 history_dir 锚定到根 | ✅ | PR-3（见 §6.4 的测试约束） |
| 5 | `git ls-files` 不含三件 legacy、`.gitignore` 同批、`git status --short` 干净 | ✅ | PR-2（实测 `.gitignore:393/411/413` 与 `:281` 命中） |
| 6 | 门禁不再以 `git show origin/main:BRIEF.md` 作测量来源 | ✅ | PR-3 |
| 7 | `test_omo_ingress_state.py` 断言改为"legacy 不再被写"并绿 | ✅ | PR-2 |
| 8 | PR-3 四个读取方给出原地 A/B 前后退出码 | ✅ | 本报告 §3.1–§3.5（2026-09-29 同夹具重跑） |

台账 `done_when` 的编号与此表不同，其中**本表未列的一条**是「`.gitignore:295` 的死规则
`!.omo/state/system_health.yaml` 删除」—— 实测由 PR-2 `cf6d4ac78` 关闭
（`git log -S` 该字符串命中它与此前的 #1237；main 上现在只剩 `:393`
的忽略行，无反向豁免行）。

## 5. 测试与门禁

- `tests/unit/test_projection_reader_resolution.py` —— **18 passed**（新建，453 行）。含登记表 stdlib 扫描 vs
  `yaml.safe_load_all` 逐名对拍、`projection_read` 的 canonical→legacy→absent 三态、外置 `state_root`
  与 checkout 分侧锚定、登记表缺失时的打包回退、`omo_paths.projection_path` 同两侧解析（含登记表
  缺项不回落）、五个读取方的 absent 语义、UHS 的 sync 跳过与跨 state root 目标、
  `meta-doctor` 的 absent≠stale 与 JSON 戳解析、probe-heartbeat 的 absent 不计与 epoch 老化。
- 根仓触及面集合（上条 18 项 + `test_repo_root_profile` / `test_gate_health_roots` /
  `gac/test_meta_doctor` / `gac/test_state_freshness_canonical` / `test_maturity_align` /
  `test_compass_radar_history` / `test_compass_radar_t1005` / `tests/bin/test_health_predict`）：
  **943 passed in 21.24s**，0 fail 0 skip。
- omo 侧（`test_omo_doctor_path_acl` / `test_blueprint_control` / `test_omo_ingress_state` /
  `test_omo_ingress` / `test_engineering_delivery_consumer_projection` / `test_episode_projection` /
  `test_phase11_wave4_absolute_paths` / `test_opc_phase_paths`）：**139 passed, 1 skipped**。
- `python -m compileall` 全部触及脚本无语法告警；CI 口径的 ruff 选择
  （`--select E4,E7,E9,F --ignore F401,F821,E402,E722,F841,F541`）对触及脚本零命中。
- `make gac-local-gate` 按 lane 分批取绿：code lane（4 文件）与 governance_code lane（7 文件）
  各自 `change-lane-check: PASS` + `GaC local gate: PASS (68 checks executed, ALL GREEN)`；
  全部文件一起暂存时唯一 hard fail 就是 `change-lane-check: FAIL mixed lanes=code,docs,governance_code`
  （§9 逐笔记录）。

## 6. 记录在案的残留（本轮不做，理由不是"忘了"）

1. **`compass_radar` 的写出侧仍默认落 legacy**：`bin/compass_radar.py` / `bin/meta/compass_radar.py`
   的 `--output` 缺省仍是 `.omo/state/health.yaml`。读取侧已改走 `system_health` canonical；
   写侧改道会同时移动 history 与外部消费者路径，属 F1（写入侧单根），另立 BET。
2. **`system_health.yaml` 两档并存在生产**（`~/Workspace/.omo/state/system_health.yaml` 与
   `.omo/state/runtime/system_health.yaml` 同时在）—— 即 dual-write 残留的实测形态，同归 F1。
3. **brief 的写侧仍指向 legacy**：`bin/mof/generate-brief.py:12` 缺省 `WORKSPACE/BRIEF.md`，
   `lib/workspace_watch_dispatch.py:76` 与 `crontab.new:76` 显式传同一个 legacy 输出。
   已安装的 crontab 里**没有**该条（实测 `crontab -l` 零命中），所以根 `BRIEF.md` 今天不会自动重生；
   但 `crontab.new` 是下次安装的源，改它需要 cron 面授权，不在本 BET 的 write_surfaces。
4. **`tests/test_compass_radar_history.py` 不在 write_surfaces**：它把 history 文件钉在
   `tmp_path/state/history/health.jsonl`（夹具里没有 `.omo` 层）。因此 `_health_history_dir()` 的
   根锚定是关键字参数 `root`：**生产路径恒传**（`main()` 传 `ws_root`），只在省略 `root`
   的仓外调用形态保留按 `state` 目录名反推的旧行为。spec §2.4 的"不得由投影文件位置反推"
   对生产路径成立，对该测试的调用形态不成立 —— 这是刻意的、可被读出来的让步。
5. **`bin/gac/gac-local-gate.py:653` 的 `SNAPSHOT_PATHS` 仍写死三件 legacy 字面量**
   （`.omo/state/health.yaml`、`.omo/state/system_health.yaml`、`.omo/_control/governance-data.json`）。
   它喂的是 `_read_state_fingerprint()` / `_check_drift()` 的 P79 并发写隔离指纹（warn-only），
   摘库后这三个路径在生产恒缺 ⇒ 指纹恒为空。该文件不在本 BET 的 write_surfaces，
   所以只记录不动；改它属于 B1 未收口的 F1 半边。
6. **`check_heartbeats` 的签名形状受 tracked 守卫约束**（§2）：profile 解析只能在函数体内，
   不能上提成 `main()` 的关键字参数 —— `tests/unit/test_gate_health_roots.py` 猴补的是
   `lambda ws_root:` 位置参数形态。后续若要给 meta-doctor 加更多 root 参数，得同时改那份测试。
7. **其余 `bin/` 与 `projects/**` 里仍有若干硬编码 legacy 字面量**（30+ 文件），不在本轮文件清单内；
   本轮的守卫只覆盖本 PR 触及的读取面。收敛判据（"无读取方硬编码 legacy 路径"）需后续 BET 推广。

## 7. 偏差

- 台账 `write_surfaces` 列出的 `docs/reports/2026-09-28-projection-plane-phase2-closeout.md`
  实际未落盘（PR-1/PR-2 都没写 receipt）。本报告覆盖 PR-1..PR-3 全段，充当 evidence matrix 的 receipt；
  该 phantom 条目在收尾 PR 里从 `write_surfaces` 删除（见 §9-2）。
- 台账 `verify` 里 `meta-doctor.py --workspace . --json` 这条命令不存在 `--json` 选项（实测
  `unrecognized arguments`）。在收尾 PR 里改为可复跑的真实命令。
- 台账 goal 里"顺带治一处既有假红"举的两个数字（`meta-doctor stale_beats 1→2`、
  `probe-heartbeat 9999h/48h`）口径不同：probe 那条是本轮真修的（§3.6）；meta-doctor 那条
  实测是 PR-1 已落的 absent 拆分，本轮的真实缺陷是 JSON 戳口径（§3.7）。

## 8. 回滚

代码面：revert 本 PR commit 即回到"读取方各自硬编码"的形态，无数据动作。
git 跟踪面：回滚需与 `.gitignore` 同批 revert（PR-2 的摘库与忽略是一条判据的两半），
单独 revert 其一会让 `gac-gate.yml` 的 porcelain 断言失效或把生成态重新扫进 commit。

## 9. 交付状态（2026-09-29 收口）

- 本节数字全部是本轮重跑的：reader **18 passed**；根仓触及面集合 **943 passed**；
  omo 侧 **139 passed, 1 skipped**；`meta-doctor` 生产 `stale=0 / absent=0`（Python 3.9.6 与 3.14.7 各一遍）；
  `probe-heartbeat` 生产 `rc 1 → 0`。
- 交付按 lane 分批 commit，实测（2026-09-29）：
  1. **omo 源码一笔** `a7ca8ce`：子模块此前 detached 在 `6bbb908`（== 它的 `origin/main`），
     故在新分支 `agent/governance-agent/b5-pr3-readers-omo` 上提交（2 文件 +52/−33）。
  2. **根仓 code lane** `cc8e91320`：暂存 `bin/lib/repo_root.py`、`bin/meta/compass_radar.py`、
     `bin/ssot/health-predict.py`、`tests/unit/test_projection_reader_resolution.py`
     ⇒ `change-lane-check: PASS (4 files, lanes=code)`，`make gac-local-gate` rc=0
     `PASS (68 checks executed, ALL GREEN)`。
  3. **根仓 governance_code lane** `854062e03`：暂存 `bin/compass_radar.py` + 六个 `bin/gac/*.py`
     ⇒ `PASS (7 files, lanes=governance_code)`，同一门禁 rc=0。
  4. **docs lane** `1de20febc`：本报告一笔 ⇒ `PASS (1 files, lanes=docs)`，门禁 rc=0
     （`PASS (69 checks executed, ALL GREEN)`；比 code lane 多一条 docs surface）。
  5. **submodule_pointer lane** `a2cf9f368` → `d6184ea6d`：根仓 `projects/omo` gitlink 两笔。
     第一笔钉 omo 分支头 `8b0ae0f`；omo #203 squash 合并后改钉 main 上的 `e3537ca`
     （与 `8b0ae0f` 树逐字节相同），使 `merge-base --is-ancestor <gitlink> origin/main` 成立，
     指针不依赖 agent 分支存活。
     ⚠️ `gac-worktree.sh bump-pointer` 在这个 worktree 里把指针**倒退**到了 `6bbb908`
     （`PASW_SUBTREE_DIR` 下它读的是另一份 omo 检出）—— 该 gitlink 是本次手工 `git add projects/omo`
     重做的，不是脚本产物。
  全部一起暂存时门禁只红在 `change-lane-check: FAIL mixed lanes=code,docs,governance_code`
  这一条 hard fail 上 —— 分批不是偏好，是 `bin/change-lane-check.py` 的强制。
  `.omo/state/system.yaml` 是 hook 的纯时间戳产物，按 AGENTS.md §7 不进任何一笔。
- 远端效应（实测）：omo **#203** 首轮 `lint` 红（`ruff format --check` 要求那行条件表达式合行），
  修成 `8b0ae0f` 后 lint/test/test-cov 全绿，squash 合并为 omo main `e3537ca`；
  根仓 **#4534** head `d6184ea6d`，`interface-check` 之外的 checks 全 pass、两条 docs surface 为
  path-filter skip，`mergeStateStatus=CLEAN`，squash 合并为 **`ebea1fd18`**。
  合并前对这批 commit 跑过 L3 深度安全评审，两仓均零发现。
- BET closeout（本 PR 承担，2026-09-29 实测）：
  1. **台账 `verify` 第 2 条**改为可复跑的真实命令 `python3 bin/gac/meta-doctor.py --workspace .`
     （`--json` 不存在，§7）。
  2. **`write_surfaces` 去掉计划期预填的 phantom report 路径**。`bet-ledger.py lint` 自带
     `PHANTOM_REPORT_PATH` 检查（lint 里的 warning 段，非阻断），它抓到台账注册时写下的
     `docs/reports/2026-09-28-projection-plane-phase2-closeout.md` 从未落盘 —— 实测
     `git log --all -- <path>` 零命中，PR-1 `18c355e06` / PR-2 `cf6d4ac78` 都没有 `A` 状态的
     报告文件。receipt 由本报告承担，路径条目删除而不是"补一份报告凑数"。
  3. **D0 前置与摘库交付语义冲突**（这条是本 BET 收尾真正的收获，也是 retro Q3-10）：
     `bet-ledger.py complete` 在置 `done` 前要求每条 `write_surfaces` 都能在根 index 里
     `ls-files --error-unmatch`，而 `.omo/state/health.yaml` / `.omo/_control/governance-data.json`
     / `BRIEF.md` 三件的"不在 index"正是 done_when-5 的判据 —— 一个成功交付的摘库 BET 会被
     完成闸按其成功的证据判死。处理：三件**保留**在 `write_surfaces`（删掉等于抹掉"本 BET
     动过它们"的记录），改跑 `complete --force`；但 `--force` 会连 vision→retro 链检一起跳过，
     所以链检先独立跑 —— `chain_bind.evaluate_complete(bet, WS, force=False)` ⇒
     **`ok=True, reasons=[]`**（绑定 run `20260928T153338Z-project-code-change-15187bd7`、
     北极星文档在位、retro 在盘）。**不改共享闸来让自己通过**；D0 缺"删除型交付物"这一格
     登记为后续项。
     `--force` 不会把红留给 CI：`.github/workflows/bet-done-gate.yml:38-59` 的硬失败只有
     `BASE_LEDGER_UNREADABLE` / `BET_DONE_*` / `META_TOTAL_BETS_DRIFT`，都不查 D0 —— 实测读源码，
     非推断。
  4. **lane 分批**：docs lane（本报告 + `.omo/_knowledge/retros/BET-Y2Q4-T10-212.md`）一笔，
     governance_state lane（`docs/plans/3y-bet-ledger.yaml`，由 `complete` 写 `status: done` +
     `done_at`）一笔；`.omo/state/system.yaml` 仍是 hook 的纯时间戳产物，不进任何一笔。
  5. **evidence matrix**：engineering `VERIFIED`（`merged_reachable_commit:
     git://origin/main@ebea1fd187dad6266c0aecbba528f240a8da9a62`，tests/diff/rollback 三键指向
     本报告）；operational `PROVEN`（live_canary / fresh_receipt / cleanup 指向本报告，
     replay 指向 retro）；value `NOT_PROVEN`；`value_indicator_policy: false`；
     `overall_state: delivery_accepted`。
  6. **workflow run**：PR-3 代码面 `20260929T044531Z-project-code-change-e23ad439`、
     收尾文档面 `20260929T073730Z-project-doc-change-3a7a7ec8`；两者的 `closeout` 在本 PR
     合并后执行，不在合并前声称已闭环。

