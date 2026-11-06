---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-11-06
type: report
bet_id: BET-Y2Q4-T10-291
title: BET-Y2Q4-T10-291 收口收据 —— A4 Scheduler 登记↔安装态按整行比对
---

# BET-Y2Q4-T10-291 收口收据

工程腿 = PR #5086 squash `ed737e423e26c89ebfde84a31c55f57dc7f0b7bb`（base `a59a966e7`）
分支 commit 四枚，按变更车道拆开：

| commit | 车道 | 内容 |
|--------|------|------|
| `92f02fbd0` | code | `bin/scheduler-compile.py` 取消 `[:120]`（`:235` 登记侧 / `:248` 安装侧）+ 新增三条用例 |
| `5e835d639` | docs | `docs/superpowers/specs/2026-11-06-scheduler-drift-full-line-comparison.md` |
| `a6d5e1983` | docs_data | `docs/plans/3y-bet-ledger.yaml` 台账条目 + `accepted_specifications` 绑定 |
| `800052b93` | code | 用例的注入行 stem 改由 registry 派生，去掉 host 字面量（CI 门禁点名，见 §4） |

## 1. 判据改动范围（逐字节核对）

`check_drift()` 只改两处键宽，归一化三段一字未动 —— 由 `git diff` 证明：

```diff
-        reg_set.add(f"{sched} {_normalize_interpreter(_expand_workspace(cmd))}"[:120])
+        reg_set.add(f"{sched} {_normalize_interpreter(_expand_workspace(cmd))}")
-            inst_set.add(_normalize_interpreter(s)[:120])
+            inst_set.add(_normalize_interpreter(s))
```

`_normalize_interpreter` / `_expand_workspace` / `harness-cron.sh` 包装行改写、
`known_orphans` 子串匹配、`ok` 语义、三个计数键名与类型、launchd shadow 段
（不参与 `ok`，ADR-0457 三段式）全部保持原样。

## 2. done_when 对应读数

### 2.1 反例 + 正例（spec 验收 1）

三条用例在 `tests/unit/test_scheduler_compile_launchd_plane.py`，**前提由用例自己断言**：

- `test_full_line_comparison_sees_a_drift_hidden_past_the_old_truncation`
  从 `compile_crontab()` 产物里选一条归一化长度 >120 且不被任何 `known_orphans`
  覆盖的行，只改 120 字符之后一段（插入 `MUTATED`），断言
  `mutated[:120] == base[:120]` 且 `mutated != base`，再断言
  `check_drift(installed_lines=…)` 读 `ok=False / drift_count>=1 / orphan_count>=1`。
- `test_full_line_comparison_keeps_a_synced_machine_green`
  安装态由 `compile_crontab()` 注入 ⇒ `ok=True / drift_count=0 / orphan_count=0`，
  不读本机 crontab（hermetic）。
- `test_known_orphan_count_counts_lines_not_truncated_keys`
  注入 5 条差异全在 120 字符之后的安装行（同一 known_orphans 模式覆盖），
  断言 `known_orphan_count == 5`。

变异对照（同一份新用例放在 `origin/main` 的旧脚本上过，复刻树 base `a59a966e7`）：

```
2 failed, 1 passed
  FAIL test_known_orphan_count_counts_lines_not_truncated_keys  :: known_orphan_count 1 != 5
  FAIL test_full_line_comparison_sees_a_drift_hidden_past_the_old_truncation :: ok=True（截断塌缩，假绿）
  PASS test_full_line_comparison_keeps_a_synced_machine_green   :: 正例不依赖缺陷，两侧都该绿
```

改动后在同一 hermetic 装置上：`test_scheduler_compile_launchd_plane.py` 新增三条全绿；
`test_shadow_segment_never_blocks_the_gate`（spec 验收 3）仍绿且 hermetic。

### 2.2 本机读数迁移（spec 验收 2）

两侧读数在同一分钟内各取一次，`drift_count` / `orphan_count` / `ok` **三项一字未变**，
只有 `known_orphan_count` 从 4 → 10：

| 检测器 base | `ok` | `drift_count` | `orphan_count` | `known_orphan_count` |
|-------------|------|---------------|----------------|----------------------|
| `origin/main`（截断键，`[:120]`） | True | 0 | 0 | **4** |
| 本轮（整行键） | True | 0 | 0 | **10** |

`raw_orphan=10 / truncated_keys=4 / patterns_declared=25`。折叠成因：
`*/2 … omo.cli resident daemon --once --role <X>` 5 条折 1 条，
`*/5 … resident {inbox,ingest,signals}` 3 条折 1 条。
**新增的 6 条不是一条新债**：10 行逐条命中既有 `known_orphans` 模式，`not-covered=0`：

| # | schedule | 长度 | 身份（差异位） | 命中的既有模式 |
|---|----------|------|----------------|----------------|
| 1 | `*/10` | 98 | `pdb-p0-probe` | `pdb-p0-probe` |
| 2 | `*/10` | 284 | `promote` | `PYTHONPATH=/Users/xiamingxing/Workspace/projects/omo/src` |
| 3 | `*/2` | 382 | `decision` | `omo.cli resident daemon --once --role` + 同上兜底 |
| 4 | `*/2` | 380 | `execute` | 同上 |
| 5 | `*/2` | 384 | `heartbeat` | 同上 |
| 6 | `*/2` | 380 | `monitor` | 同上 |
| 7 | `*/2` | 382 | `sediment` | 同上 |
| 8 | `*/5` | 273 | `inbox` | `PYTHONPATH=…/projects/omo/src` |
| 9 | `*/5` | 341 | `ingest` | `omo.cli resident ingest` + 同上兜底 |
| 10 | `*/5` | 275 | `signals` | `PYTHONPATH=…/projects/omo/src` |

本 BET 未新增 `known_orphans` 条目（spec 非目标 2），只把计数改准。

### 2.3 门禁调用方（spec 验收 4）

`bin/gac/gate-health-check.py` A4 段的 `ok` 值不因本 BET 改变，改变的只有计数；
消费面在同一 hermetic 装置上 `31 passed`，被跑的四个文件：
`tests/test_scheduler_compile.py`、`tests/unit/gac/test_install_cron_plane.py`、
`tests/unit/test_gate_health_roots.py`、`tests/unit/test_scheduler_collector_registry_root.py`。

## 3. hermetic 装置与复刻纪律

复跑命令（依赖由最小 venv 供给，host 面全脱钩）：

```
env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB \
  HOME=$(mktemp -d) GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null \
  UV_CACHE_DIR=$(mktemp -d) uv run --no-project \
  --with pytest --with pytest-timeout --with pyyaml python -m pytest <files> -q -p no:randomly
```

基线复刻第一次漏了 `.omo/_truth/registry/services.yaml` 与 `runtime/cron`，
多出一条 `FileNotFoundError` 假「预存红」（读数 `3 failed / 3 passed`）；补齐后
基线 `2 failed / 4 passed`，与改动后 `2 failed / 7 passed` **失败集合逐名相同**。
那两条预存红按名逐字复算过（基线复刻树与改动后树**同名为这两条**）：
`test_every_active_launchd_entry_resolves_to_an_installed_label`（`:194` AssertionError）与
`test_launchd_bidirectional_drift_structure` —— 前者直读 `~/Library/LaunchAgents`，
后者调 `check_drift()` **不注入**，于是读真实 `crontab -l` 与 launchd 面，
在 `HOME=<空目录>` 装置下按构造不可满足。属 AGENTS.md §7「用例断言 host 运行态」类，
不是本 BET 引入。同一条命令在**本机原样环境**下读 `9 passed`（改后）—— 见 §4 边界 2。

## 4. 已知边界（不假装成 CI 证据）

1. `tests/unit/test_scheduler_compile_launchd_plane.py` **不在** `governance-check.yml`
   的 pytest 白名单里 —— §3 那两条 host-state 用例使它无法 hermetic 入册。
   因此本 BET 的三条新用例只有本地 hermetic 这一种证据（AGENTS.md §7
   「判据不被任何 CI 路径跑 = 不存在」）。把它收进白名单的前置条件是先把那两条改成注入缝。
2. 台账 `verify[0]` 开台时有两处失真，本收口腿在同一 docs_data 车道 commit 里改正：
   ① cmd 漏写 `--with pytest-timeout`，按原文跑不动（根 `pyproject.toml` 的 `addopts`
   带 `--timeout`，缺包时 pytest 直接拒收参数）；② cmd 声明了 hermetic env，`expect`
   却写「全部通过」—— 这两件事在同一把装置下互相否证。实测读数：
   **本机原样环境 `9 passed`（改后全文件绿）；同一条命令在 cmd 自己声明的
   `HOME=<空目录>` 装置下 `2 failed, 7 passed`，两条红逐名为 §3 那两条 host-state 用例，
   且基线复刻树（base `a59a966e7`）逐名同为这两条 `2 failed, 4 passed`。**
   订正后的 `expect` 按判据本体（三条新用例 + shadow 段 hermetic）表述，并点名那两条预存红。
   `verify` 在 WorkPacket 投影里，故只能等 claim 完成后改（AGENTS.md「顺序纪律」）。
3. CI 第一轮 `governance-verify` 红在 `tests/unit host-literal confinement gate`
   （`test_tests_unit_host_anchors.py`）：新用例在 `:259` 写了
   `cd /Users/xiamingxing/Workspace` 字面量，被冻结的 `LEGITIMATE_HITS` 集合点名。
   处置是**去掉字面量**（改由 registry 里最短的 `known_orphans` 模式派生注入行），
   **不是**给 `LEGITIMATE_HITS` 加豁免 —— 加豁免等于收窄那把尺。
   修后复算：confinement gate 5 条全绿，变异对照读数不变（§2.1）。

## 5. 观测到的重复控制面（未动手，只登记）

新计到的 6 条属于 legacy cron 常驻控制面，与已注册 launchd 常驻任务**同时在跑**：

- cron 侧 9 条 resident 行：`--role` decision/execute/heartbeat/monitor/sediment
  + `resident` inbox/ingest/promote/signals；
- launchd 侧 6 个 label：`com.l4.resident.{decision,execute,signals,inbox,promote,event-ingest}`，
  `launchctl print gui/<uid>/…` 读数 `runs=846 / 846 / 339`、`last exit code=0`。

即两侧都是活的，不是「launchd 已接管、cron 只是残渣」。其中
`heartbeat / monitor / sediment` 三角色只存在于 cron，`event-ingest` 只存在于 launchd。
撤任一侧都是机器实装变更，归 principal 决定；本 BET 明确不做（spec 非目标 1）。

## 6. 遗留判据缺陷（建议另开 BET）

`projects/omo/src/omo/workflow/lifecycle.py:1422` 的 A2A Path Lock 冲突谓词只看
run `status == "active"`，不看锁的 `expires_at` / 心跳 TTL。本轮据此被一条已交付 BET
（BET-Y2Q4-T10-285，`origin/main` 上 `done / delivery_accepted`）的死 run 拦住 claim；
而 `.omo/_truth/registry/agent-workflows/_root.yaml` 的 `compliance_slo.stale_locks: 0`
说明本仓**期望**零陈旧锁。谓词应改成「run active **且** 锁未过期」。
处置方式（不拆别人的锁 + 走 `claim_policy.mode: advisory` 降级）已写进 retro。
