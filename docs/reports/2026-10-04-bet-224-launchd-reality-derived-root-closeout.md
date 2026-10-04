---
schema: md/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-10-04
type: report
bet_id: BET-Y2Q4-T10-224
title: BET-Y2Q4-T10-224 closeout — launchd 登记双向纠偏 + tests/unit 去 13 处 host 字面量
---

# BET-Y2Q4-T10-224 closeout — 一处登记在说谎，另一个方向也在说谎，而用例用字面量把谎话钉成绿

契约：`docs/superpowers/specs/2026-10-04-bet-224-launchd-reality-and-derived-root-assertions.md`
（`sha256:aae565f29013d63ab8fb95dff0c1ee2a28711ce0eaa737294c09070fc12f6b13`）
台账：`docs/plans/3y-bet-ledger.yaml` 条目 `BET-Y2Q4-T10-224`
run：`20261004T094302Z-project-code-change-0809007c`（八条 path 全 claim，
`--affected-receipt .artifacts/affected-t10224.json`，`receipt_hash=79c09ea5…`）
基线：`origin/main@540783376`（2026-10-04 实测）

## 1. 交付了什么

| 面 | 改动 |
|---|---|
| `.omo/cron/registry.yaml` | 3 条记录向实测纠偏；2 处重复 `reality` 键删除；2 条已收敛的 `ssot_conflict` 撤键；foundry 的段前注释同步 |
| `tests/unit/test_cron_registry_reality_invariants.py` | 新增：I1/I2/I3 全 70 条判定 + 重复键检测器自证 + `safe_load` 反证 + 3 条实测值回归锁 |
| `tests/unit/test_panorama_runtime_scheduler.py` | 8 → 0 处 host 字面量；根从 plist 自身派生；混合根与跨源两个变异对照 |
| `tests/unit/test_agent_cell_scheduler.py` | 5 → 0 处 host 字面量；同一派生法；混合根变异对照 |

## 2. 三条纠偏的独立探针读数（本机、无网络）

每条都用三个互相独立的探针，而不是"哪一侧能让 pytest 绿"：

| job | 探针① `launchctl list <label>` | 探针② `~/Library/LaunchAgents` | 探针③ `runtime/cron/` | 授权面 `services.yaml` | 纠偏 |
|---|---|---|---|---|---|
| `panorama-dashboard-refresh` | 可见（loaded） | 有同名 plist | 有受控产物 | `enabled: true` | `proposed/pending` → **`active` / `installed`**（低报，两面同向） |
| `panorama-dashboard` | `Could not find service` | 无 | 有（骨架） | `enabled: false, lifecycle: retired` + `disabled_reason` | → **`proposed` / `declared_only`** 并在 note 里落退役事实 |
| `knowledge-foundry-6h` | `Could not find service`（按真实 label `com.omostation.knowledge-foundry` 查，非 job 名） | 无 | 有 | 无对应条目 | `installed` → **`declared_only`**（高报，唯一一条 I2 违规） |

foundry 这条差点被探针本身做错：job 名是 `knowledge-foundry-6h`，真实 plist `Label` 是
`com.omostation.knowledge-foundry`（无 `-6h`）。按名字 `grep` 用户域得到"没有装机"这个**碰巧
正确**的结论，但判据是错的。改用真实 label 复核后才成立，并把 label 与 name 不一致记进 note。

## 3. `pending` 的来源：重复键 last-wins（本轮新发现）

两条 panorama 记录各带**两个** `reality` 键（`declared_only`+`pending`、`installed`+`pending`）。
`yaml.safe_load` 在构造 mapping 时静默保留最后一个，因此文件同时印着"已装机"与"待装"，
而所有读者只看到 `pending`。全文件 dup-aware 扫描实测恰好 2 处，其余 68 条干净。

后果直接决定修复形状：只改其中一行，另一行仍会赢。所以做法是删掉被遮蔽的键、
留唯一真值，并把该形态钉成 I3。I3 无法用 `safe_load` 判定，检测器自带 dup-aware
constructor；按 #4606 的教训它必须自证 —— `test_duplicate_key_detector_is_not_a_no_op`
向真实文本注入重复 `reality` 行并断言检测器点名它，
`test_safe_load_alone_would_have_missed_that_violation` 再断言 `safe_load` 折叠成一条、
看不见违规。两者合起来排除"检测器空转的绿"。

## 4. 不变式基线与纠偏后读数

| 不变式 | 判据 | 基线违规 | 纠偏后 |
|---|---|---|---|
| I1 | `status=active ⇒ reality ∈ {installed, crontab_installed}` | 0 | 0 |
| I2 | `reality ∈ {installed, crontab_installed} ⇒ status=active` | **1**（`knowledge-foundry-6h`） | 0 |
| I3 | 每条 job 映射内无重复键 | **2**（`:599`/`:623` 的 `reality`） | 0 |

I1 在基线上已绿，单独不构成证据；它与 I2 成对成立才有方向性（I2 的违规形状正是
"proposed 却声称 installed"）。I2 的基线读数 1 被写进本 receipt，否则无法证明这条 gate
曾经拦到过东西。

## 5. 下游效应：纠偏不是纯文档动作

`status`/`reality` 的真实消费者是实测过的两处（spec 初稿误写为 `scheduler-compile.py` 消费
`reality`，已在纠偏后的契约里改正）：

- `bin/scheduler-compile.py:46`（crontab 只出 active）、`:147`（launchd 登记集只取 active）、`:183`（drift 只比 active）
- `bin/panorama/panorama-collect.py:1603`、`:2802`（按 `== "installed"` 挑选）、`:2810`（缺省回落 `declared_only`）

改前改后各测一次：

| 读数 | 基线 | 纠偏后 |
|---|---|---|
| launchd 登记集 `registered_count` | 12 | **13**（refresh 进入） |
| `label_match` | 12/12, rate 1.0 | **13/13, rate 1.0**（未引入 label 不匹配） |
| `undeclared_installed_count` | 25 | **24**（少一条未申报的已装机） |
| `check_drift().ok` / `orphan_count` | False / 1 | False / 1（未变，见 §7） |

## 6. 去字面量的做法与代价

13 处 `/Users/xiamingxing` 字面量（panorama 8、agent-cell 5）不是"美化"掉的：它们今天的绿
恰好来自逐字复述 plist 里的 host 根（green-by-literal），换根当天会准时变红。替换成三条闭合判据：

1. R := `payload["WorkingDirectory"]`，派生断言 `PYTHONPATH == R + "/projects/omo/src"`、
   `PANORAMA_ROOT == R`、日志两键以 `R + "/"` 为前缀、agent-cell 状态文件 == `R + "/.omo/state/agent-cell/cell_states.json"`；
2. D := `ProgramArguments` 里那个 `.py` 参数的父目录；R 与 D 互不包含；脚本路径、
   `PANORAMA_CODE_ROOT`、registry `command` 三者字符串逐字相等（跨源一致，替掉 5 处字面量）；
3. `PATH` 用 `Path.home()/".local"/"bin"` 派生。

另加两条纯结构判据：`StartInterval % 60 == 0` 且 `schedule == f"*/{StartInterval//60} * * * *"`
（cron 与 plist 的间隔同源，不再各写一份 240 与 `*/4`）。

反字面量自锁落在**三个**文件（两个既有的 + 新不变式文件），各断言自身源码不含
`"/Use" + "rs/"`。拆成两截是必须的：该断言若写成整串， needle 会命中自己这一行 ——
第一轮实跑就当场红了，这是本轮的一个真实小坑。

R 特意不从 `__file__` 推：`parents[2]` 在 worktree 里是 `ws-…` 检出根，而 plist 写的是 canonical 根，
两者本就不等。用 `__file__` 派生会造出一条"在 worktree 里必红"的断言 —— 比它替换掉的
字面量更糟，因为它看起来是派生的、因而是可信的。

## 7. 边界与本 BET 不做的事

- 不碰 `runtime/cron/**` 任何一个 plist（改道属 B4b 批次 2，逐批授权）；`services.yaml` 一行未动。
  交付 diff 的 `git diff --name-only origin/main...HEAD` 即这条边界的证明。
- 不装/卸/`launchctl` 任何 job：registry 向实测靠拢。
- 不扩 `status`/`reality` 枚举；不新增门禁脚本；不动 `.github/workflows/**`。
- `tests/unit/**` 不在 CI 白名单（`governance-check.yml:118-127`），所以本 BET 的证据只有本地 pytest 实跑：
  目标三文件 `23 passed`，加邻域 5 个同读 registry 的文件 `1 failed, 36 passed`。

唯一那条红是**基线即红、与本 BET 无关**的 `test_scheduler_compile_launchd_plane.py::
test_shadow_segment_never_blocks_the_gate`：它自己就是 §"查机器即破坏 hermeticity" 那一类
（直接调 `check_drift()` 读本机 launchd），`orphan_count: 1` 使它拿不到 `ok is True`。
不静默修、不静默 skip，登记为后续 BET。

## 8. 后续 BET 登记（本轮实测发现，不在本轮修）

1. **跨面 launchd 归属裁定**：`services.yaml` 有 27 条 `com.omostation.*` label，其中 20 条在
   `.omo/cron/registry.yaml` 按名找不到对应行；编译器口径 `undeclared_installed_count` 现值 24。
   两个 SSOT 面都在定义 launchd 对象。**对 B4b 批次 2 的直接后果：只按一个面枚举 plist/cron
   会漏掉 20+ 条活着的 job，那个批次的"43 plist"基线是下界而非真值。**
2. `test_shadow_segment_never_blocks_the_gate` 的 hermetic 化或 `known_orphans` 补齐。
3. **8 条 launchd job 缺显式 `label`**（`zhixing-dashboard-refresh`、`knowledge-foundry-6h`、
   `omo-health-refresh`、`panorama-dashboard`、`panorama-dashboard-refresh`、
   `agent-cell-pool-live-smoke`、`agent-cell-semantic-smoke`、`reference-cell-direct-local-smoke`），
   `:147` 按 `com.omostation.{name}` 合成。今天只有 `status=active` 的会被比对，故暂无破坏；
   但 foundry 一旦激活，合成 label 与真实 Label 不等（差 `-6h`）会立刻成为 label 不匹配。
4. 把 I1/I2/I3 从 `tests/unit/` 提升到 CI 可见面（需要动 `.github/workflows/**`，超出本轮边界）。
