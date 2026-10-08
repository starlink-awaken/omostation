---
schema: md/v1
status: completed
lifecycle: report
owner: governance-team
last-reviewed: 2026-10-07
type: closeout-receipt
bet_id: BET-Y2Q4-T10-235
title: BET-Y2Q4-T10-235 closeout receipt — system.yaml 创建者 + 检出侧摘库（PR #4671）
---

# BET-Y2Q4-T10-235 closeout receipt

- **交付**：PR #4671 → squash merge `bbcb4e2795dce3ec30eec76bc1250e15dc109f7d`（2026-10-07T10:41:16Z）
- **分支**：`agent/governance-agent/b5-system-yaml-materialize`（`1a27f4e45..39b6471f7`，已随 squash 删除）
- **契约**：`docs/superpowers/specs/2026-10-07-system-yaml-materializer-untrack.md`
  （`sha256:cf4fc22dcfc5e27f2d7266044e73dc91f34eb6e2e5ff75811914158095f6dfb5`）
- **本 receipt 的读数全部取自合并后的新建检出** `ws-t10-235-closeout` @ `bbcb4e279`（16 个子模块 PASW 齐备），
  不是交付分支上的自证。
- **机器可读读数**：`docs/reports/2026-10-07-bet-235-canary.json`（`canary-reading/v1`，同一棵检出 +
  同一份 `git archive HEAD` 复刻，脚本化采集，含 `measured_at_utc` 与 head sha）。§2–§5 的每个读数都能在该
  JSON 里找到对应键；两处命令写法不同（`bin/mof/generate-brief.py` 不带 `--protect`）已在该 JSON 里逐字记下。

## 1 diff 面（rollback 依据）

`git show --stat bbcb4e279` = **25 文件**，其中唯一生成态条目是**有意**的 `D .omo/state/system.yaml`（58 行）。

| 面 | 文件 |
|---|---|
| 创建者 | `bin/gac/materialize-system-state.py` (+263)、`bin/_registry/scripts/governance/materialize-system-state.yaml` (+34) |
| 摘库 | `.gitignore`（正向忽略 `:297`）、`.omo/state/system.yaml`（-58） |
| 读者接线 | `Makefile`（`state-materialize` / `debt-check`）、`bin/arch-health-meter.py`、`bin/check_health_ssot.py`、`bin/gac/m1-closeout-report.py`、`bin/gac/session-recovery.py`、`bin/meta/compass_radar.py`、`bin/panorama/panorama-collect.py`、`bin/ssot-watcher.py`、`bin/ssot/ssot-guardian.py` |
| CI 接线 | `.github/workflows/{gac-gate,architecture-check,state-goals-enforce,governance-check}.yml`（创建者步骤排在读者之前） |
| 登记面 | `.omo/_truth/registry/{ci-surfaces,governance-checks}.yaml` |
| 用例 | `tests/unit/test_system_yaml_materializer.py`、`tests/unit/test_system_yaml_consumer_inputs.py`（新） |
| 文档 | `docs/plans/3y-bet-ledger.yaml`、spec、`AGENTS.md`（§7「扫源码的门禁」⑨） |

**Rollback**：`git revert -m 1 bbcb4e279` 不可用（squash 无第二父），回滚单位是内容级 ——
重新跟踪 `.omo/state/system.yaml`（撤 `.gitignore:297`）+ 四条 workflow 的创建者步骤可独立摘除；
创建者脚本本体无人强依赖（8 个写者仍是「存在才改、缺席即跳」），删它即回到 #4671 之前的形状。

## 2 tests 面

| 命令 | 读数 |
|---|---|
| `python3 -m pytest tests/unit/test_system_yaml_materializer.py tests/unit/test_projection_reader_resolution.py tests/unit/test_system_yaml_write_plane.py tests/unit/test_system_yaml_consumer_inputs.py -q -p no:randomly` | **81 passed** |
| `git grep -n test_system_yaml_materializer -- .github/workflows/` | 命中 `governance-check.yml:196` 一行 pytest 调用（`tests/unit/**` 不在 CI 白名单，未点名即不算交付） |
| `python3 bin/gac/omo-state-write-guard.py --json` | `ownership: undeclared-key 0 / ghost-declaration 0`，rc=0 |
| `timeout 300 python3 bin/ssot/gen-capability-registry.py --check` | `✅ 能力注册表无漂移`（新登记条目未把生成态推离跟踪值） |
| `make gac-local-gate` | **PASS（68 checks executed, 2 SOFT WARN）**，rc=0 —— ⚠️ 本笔交付收尾复跑时变为 **FAIL**，唯一 hard fail 是 `service-config-drift`（host 面、CI 不执行、非本笔引入，逐条定性见 §7.1） |
| `make gac-local-gate-strict`（`--strict`，与 CI 同装置，86 checks） | **rc=1，5 条 hard fail** —— 逐条归类见 §4.1；`.omo/state` 跑后仍空 |

⚠️ 覆盖面边界（本轮复测订正，先前措辞错在机制）：`brief-protect` 登记在
`bin/gac/gac-local-gate.py:225`，`gac-gate.yml:144-150` 的 `gac-local-gate.py --strict`
**确实调它**（该步无 `continue-on-error`）。让它对红失效的是同一文件里的 `SOFT_CHECKS`
（`:601` 定义、`:602` 收录 `brief-protect`，注释写明「非门禁阻断」）：`:1200` 把
`name in SOFT_CHECKS` 的失败从 blocking 列表剔除、`:1203` 归入 warnings ⇒ 该检查 rc=1 时
门禁仍 rc=0。所以 §2 的「PASS（68 checks，2 SOFT WARN）」和 CI 全绿**都不是** §5 那处红的证据。

## 3 判据逐条读数（合并后检出）

| 判据 | 命令 | 读数 |
|---|---|---|
| 判据-1 创建者存在且可复算 | `python3 bin/gac/materialize-system-state.py --dry-run --json` | rc=0，`key_set_equals_declared: True`，`empty_shape_keys: 13`，`total_tasks: 304` |
| 判据-2 缺失复活（核心） | 新检出 `git ls-files .omo/state` → 仅 `collab-dualtrack.yaml`；`current-state-coherence.py` | **rc=2** `missing input: …/.omo/state/system.yaml` |
| 判据-2 后半 | 物化后 `current-state-coherence.py` | **rc=0** `active phase=29 wave=W1 active=1 planned=0 blocked=0` |
| 判据-3 摘库 | `git ls-files .omo/state/system.yaml` / `git check-ignore -v` / `git status --short .omo/state`（跑完整门禁前后各一次） | `''` / 命中 `.gitignore:297` / **跑前跑后均为空**（0 字节） |
| 判据-4 正向落点 | `OMOSTATION_STATE_ROOT=<tmp>` 跑物化器 | `<tmp>/.omo/state/system.yaml` 出现；检出那份 sha256 `8ae348af63572990…` **逐字节未变**；二次运行 `status: skipped` 且 state 根那份不变 |
| 判据-5 门禁不瞎 | 见 §2 三行 | 81 passed / ownership 双 0 / CI 点名命中 |
| 判据-6 消费面 | 按 CI 步骤顺序：创建者 → `doc-link-check` → `architecture-check --gate` → `current-state-coherence` | `PASS (36 files)` 0 broken / `0 error 0 warning` rc=0 / rc=0 |

判据-6 的两种树对照（`git archive` 复刻 vs 子模块齐备 worktree）见 spec §10；本轮的「合并后新检出」是
第三种树 —— 它同时满足「与 fresh clone 同形」和「子模块齐备」，所以「0 broken links」这一格第一次在
真实检出上取到，而不是在复刻装置里推演。

## 4 operational 面

- **live_canary**：`make gac-local-gate` 在合并后检出 PASS（68 checks，rc=0），跑后 `.omo/state` 空；
  逐项读数（含 `git ls-files` 0 行 / `check-ignore` 命中 `.gitignore:297` / 三读者 rc=0 / 81 passed /
  ownership 三 0 / CI 点名两行 `governance-check.yml:196`、`:200`）落在
  `docs/reports/2026-10-07-bet-235-canary.json` 的 `in_tree` 段。
- **fresh_receipt**：本文件。
- **replay**：`.omo/_knowledge/retros/BET-Y2Q4-T10-235.md`（四问结构 + §3 记录本轮实测读数）。
- **cleanup**：worktree `ws-b5-system-yaml-materialize` 与 16 条 PASW 子树已释放（`release` rc=0）；
  本地分支 `agent/governance-agent/b5-system-yaml-materialize` 已删；affected-graph receipt
  （`runtime/affected/*.json`）已删，未进 commit。

### 4.1 `--strict`（CI 同装置）的本机 5 条 hard fail —— 逐条指认，不靠记忆

上面 live_canary 用的是 `make gac-local-gate`（非 strict，68 checks）。CI 的 `gac-gate.yml:150` 跑的是
`--strict`，所以本轮补取一次同装置读数：`make gac-local-gate-strict` → **rc=1，86 checks，5 条 hard fail**，
跑后 `git status --short .omo/state` 仍为空（判据-3 在 CI 装置下复算成立）。

| 检查 | 本机读数 | CI 是否执行 | 归类 |
|---|---|---|---|
| `agent-workflow-doctor` | rc=1（打印的是用法帮助） | **否** | host |
| `state-freshness-check` | rc=2 `files_checked 5 / missing 0 / stale 1 / expired 1 / avg_score 0.0` | **否** | 见下注 |
| `service-config-drift` | rc=1，1 条 `com.omostation.zhixing-projection-fullrefresh` plist 与 services.yaml 不一致 | **否** | host launchd |
| `agent-workflow-compliance` | rc=1 `escalate`，`runs=223 events=1528` | 是 | 读本机全局协调面 |
| `agent-workflow-observe` | rc=1 `escalate`，`locks=6`，含一条过期锁 `…registry_omo-governance-surfaces.yaml` | 是 | 同上，锁不是本 BET 的 |

装置差实测：`gate_checks(strict=True)` 在 `_is_ci_env()` 假/真两侧分别给 **86 / 79** 条，差集正是
`agent-workflow-doctor`、`state-freshness-check`、`service-config-drift` 三条 `ci_skip`（外加
`check-index-drift` / `gac-consensus-inject-check` / `matrix-consistency` / `zones-check` 四条本机绿）。
后两条 CI 也执行，但它们的对象是 `.omo/_delivery/agent-workflows/` —— 本检出里它是指向 canonical 检出的
symlink，而 `git ls-files .omo/_delivery/agent-workflows` 返回 **0 行** ⇒ CI 干净检出里没有 run / lock /
event，这两条在 CI 按构造绿。**结论**：5 条红无一条由 #4671 引入，也没有一条是 §5 那处红 ——
`brief-protect` 在同一次 strict 运行里落在 `soft_warns`（rc=1，不进 blocking），与 §2 的措辞一致。

⚠️ 顺带一条 G9 实证补料：`state-freshness-check` 在真实树上 5 条目标里 4 条缺席（`optional` ⇒ `ok: true`，
`files_missing` 恒 0），唯一存在的是 tracked 快照 `.omo/_control/debt-dashboard/current.yaml`
（`generated_at: 2026-09-16T07:54:59Z`，age 519h）⇒ `avg_score` 被单条拖到 `0.0`。
与合成树那格「1 条新鲜 + 4 条缺席 ⇒ 100.0/100」合起来读：**缺席项不进均值**（否则均分应是 20），
单条陈旧独自决定整块面板。这条不是本轮交付的判据，登记给 G9。

## 5 新发现（实测，非推测）—— 已登记为后续 BET

物化器给 6 个键写空形（`health_score` / `health_score_source` / `health_score_generated_at` /
`governance_anomaly_score` / `governance_feedback_last_run` / `service_online_ratio`），
而 `bin/mof/generate-brief.py:398-399` 用的是 `data.get(key, default)` —— 键**存在但为 null** 时
`.get` 返回 `None` 而不是默认值，于是 `:509` `if health_score >= 90` 抛
`TypeError: '>=' not supported between instances of 'NoneType' and 'int'`，rc=1。

崩溃发生在内容生成阶段（`:573 content = generate_brief_content()`），**不是** protect 判定：
门禁给的命令是 `["bin/mof/generate-brief.py", "--protect"]`（无 `--write`），而 protect 分支的前置
是 `:576 if args.protect and args.write and BRIEF_MD.exists()` ⇒ 该分支今天恒不进入，这条检查
的实际内容只有「brief 生成器对着当前 state 根跑不跑得过」。合并后检出里直跑复现：
rc=1，stderr 末行即上面那条 TypeError，`health_score` 读回 `None`。

三态对照实测（同一棵合并后检出，只换 `.omo/state/system.yaml` 的内容）：

| 文件状态 | `python3 bin/mof/generate-brief.py --protect` |
|---|---|
| 缺文件（#4671 之后、未跑创建者） | **rc=0**（脚本 `:390` 自有默认 90） |
| #4671 之前的跟踪快照（`health_score: 46`） | **rc=0** |
| 创建者物化后的空形（`health_score: null`） | **rc=1 TypeError** |

⇒ 失效形状恰好落在「两种本来能跑的状态中间」：摘库本身不坏、恢复跟踪也不坏，是**空形 + `.get(key, default)`**
这对组合是新的。全库扫描 `bin/**` + `projects/*/**` 中读这 6 个键且带默认值的站点：**24 处**，其中
13 处在子模块（cockpit 4 / model-driven 3 / omo 6，跨仓，另议），root 侧 `bin/` 11 处里**只有这 1 处**在空形下从 rc=0 变 rc=1
（`governance-readiness.py` / `unified-health-score.py` / `weekly-review.py` / `quarterly-report.py`
在两种内容下读数相同；`m1-closeout-report.py --help` 的失败在两侧同为 rc=1，是 `repo_root` 的
PYTHONPATH 预存问题，与本 BET 无关）。
拆分装置是 AST 而非正则（`ast.walk` 找 `Call(func=Attribute(attr="get"))` 且 `len(args) >= 2`、
首参为这 6 个键之一的 `Constant`）：同一份文本用正则按引擎/换行写法不同得到过 10 / 11 / 13 三种读数，
这正是 AGENTS.md §7⑦「同一判据换装置读数不同 ⇒ 判据要写明用哪个尺」的形状；
逐条站点清单见 `docs/superpowers/specs/2026-10-07-brief-null-shape-consumer.md` §3。
先前本节把拆分写成「11 处子模块 / root 侧 13 处」，两侧数字对调了 —— 那是把 rg 输出按出现顺序抄反，
不是重新扫过的读数，现已按上面的 AST 装置订正。

修复方向（判据-6 同侧：补消费面，不动 §7.1 的空形语义、不撤摘库）：
消费方把 `None` 折叠成「未测量」= 走它已有的缺省分支；判据用**等价性**表达，比「不报错」难变 ——
null 空形下生成的 BRIEF 内容，经 `normalize_brief_content()` 去掉时间戳后与**缺文件**那份逐字节相等。
可见性那半边的措辞也随之订正：不是「纳入 CI 面」（§2 已证它被调用），而是**让这条 rc=1 成为阻塞信号** ——
照 `governance-check.yml:196`/`:200` 的先例加一条显式点名的 pytest 用例，而不是把 `brief-protect`
摘出 `SOFT_CHECKS`（那会让所有 BRIEF 噪声一起变阻塞，且 protect 分支恒不进入，等于放大一条本来没在
做保护的检查）。登记为 **BET-Y2Q4-T10-236**（同批入台账）。

## 6 台账闭环处置（`complete` 前的三笔账，逐条实测）

1. **`write_surfaces` 里的 `.omo/state/system.yaml` 在本笔交付中摘除**。原因是测量而不是偏好：
   `bin/plan/bet-ledger.py::cmd_complete` 的 D0 铁律对每条 exact 写入面调
   `_d0_surface_tracked()`（`git ls-files --error-unmatch` → 否则查 pinned gitlink），该路径在
   `bbcb4e279` 上返回 `(False, "not tracked")` —— **28 条里唯一一条**。而「不被跟踪」正是判据-3 的交付本体，
   所以留它在清单里只有两种过法：`--force`（同时跳过 `vision→retro` 链校验，不可接受），或让 D0 永远测不到这条契约。
   先例 BET-Y2Q4-T10-212 把三件已摘库生成态（`.omo/state/health.yaml` /
   `.omo/_control/governance-data.json` / `BRIEF.md`）留在 `write_surfaces` 里至今 `done`，
   实测它们今天同样报 `not tracked` —— 那笔账没被结算，只是当时 `--force` 或守卫尚未生效。
   摘除后该路径的**事实仍在台账里**：`done_when` 判据-3 断言 `git ls-files .omo/state/system.yaml` 为空、
   `goal` ② 记录 `!.omo/state/system.yaml` 是空操作、正向忽略由 `.gitignore` 这条写入面承载。
2. **AGENTS.md 本轮不再改动**（closeout 前的待办之一被实测否证）。待办写的是「§7 尾句仍断言该路径
   仍被跟踪 / `.gitignore:294`」；实测 `AGENTS.md:351` 已含 ③（#4671 交付时一并改写），其措辞是
   「**已摘库** … `.gitignore:297` 正向忽略 … #4606 那句『仍被跟踪是显式反选的结果』到此失效」，
   并把三处指针逐条对拍：现值 `:293` = `system.yaml.bak-*`、`:297` = 本体忽略规则、
   基线 `bbcb4e279~1` 的 `:295` = `!.omo/state/system.yaml`（三条全部逐字命中，`git show` 可复算）。
   ⇒ 记这一笔的原因是**判据本身差点错**：写「就地修正陈旧指针」时我没有先读那行，而 §7 第 ⑥ 条要求
   引用行号前先 `git show origin/main:<path>` 核一遍 —— 这条纪律这次保护的是我自己，别去重复修一处已经正确的文本。
3. **不宣布 B1 / B5 完成**（spec §8 非目标）：本轮只把 B5 的最后一件生成态做实；
   G9（`state-freshness-check.py` 的 optional-missing 记满分）与 B4b 批次 2+ 仍待逐批授权。

## 7 `done` 之后的复算与订正（同批交付，2026-10-07 深夜）

本 receipt 与 retro 在 `complete` 落账后又改了四处，逐条是**重测**而非改写结论：

| # | 订正 | 从（先前写的） | 到（复算后） | 装置 |
|---|---|---|---|---|
| 1 | §5 站点拆分 | 「11 处子模块 / root 侧 13 处」 | **root 11 / 子模块 13**（总数 24 不变） | AST 按侧分组计数，每侧先印计数再印明细 |
| 2 | §5 可见性措辞 | 「`brief-protect` 在 `.github/workflows/` 零调用」 | 被 `gac-gate.yml:144-150` 调用，失效点是 `SOFT_CHECKS` | `git grep -n gac-local-gate.py -- .github/workflows/` + `:601-602/:1200/:1203` |
| 3 | §2 live_canary | 只有非 strict 一条（68 checks，rc=0） | 增 `--strict`（86 checks，rc=1）一条，5 项红逐条归类见 §4.1 | `make gac-local-gate-strict` |
| 4 | retro G9 输入 | 只有合成树读数 | 增「该检查在 CI 不执行」+ 真实检出读数（`files_missing 0` / 519.46h 单份快照决定 `avg_score 0.0`） | `gate_checks(strict=True)` 在 `_is_ci_env()` 两侧对拍（86/79） |
| 5 | §2 门禁行 | `make gac-local-gate` PASS rc=0 当作收尾读数 | 同一命令收尾复跑为 **FAIL**（hard fail `service-config-drift`），已按 §7.1 三条实测定性 | `gen-service-configs.py --check --json` + `gen_launchd_plist()` 内存产物与已安装 plist 的 `unified_diff` |
| 6 | §7.1 首稿的两处定性 | 「unified_diff **60 行**」／「**第三个未登记**的安装位 `~/.local/opt/omostation-publisher`」 | **63 行**（同一装置重跑，且两侧缩进指纹相反：盘 tab 40 / 生成 4 空格 15）；publisher **不是未登记** —— 它声明在同一条服务的 `notes` 里（T10-227 原话），缺的是它在 ADR-0456 根词汇里没有位置 | `gen_launchd_plist(svc)` vs 盘上 `unified_diff` + `yaml.safe_load_all` 读该条 `notes` + `bin/panorama/projection-full-refresh.py:33-36` 的 `CHECKOUT` 默认值 |
| 7 | 摘要重算装置本身 | 用「路径命中行 ±3 行内任意 `sha256:[0-9a-f]{64}`」批量替换 | **换掉装置**：按 YAML 子映射配对（`ref` 与它的 `sha256` 是**同列兄弟键**）重导，实测跨键串写 **2 处**（`engineering.rollback`、`operational.fresh_receipt` 指向 receipt 却带着 retro 的摘要）；两台独立装置（列配对行扫 + `yaml.safe_load` 结构走查）读数一致 **refs=11 stale=0** | `/tmp/repair_digests_structural.py` + `yaml.safe_load` 遍历三笔 `accepted_specifications` 与全部 `receipt://` 轴键 |

第 1 条值得单独记：**总数对得上，所以任何「与别处对一下」的复核都抓不到它** —— 错在抄写而非测量，
处置只能是重测（retro lesson 11）。第 7 条是同一课的**装置版**：`±3 行`这个近邻启发式在
`ref`/`sha256` 相邻、且三种摘要各只出现一到两次时会「大部分时候对」，所以它**交付时是绿的**；
真正把错误暴露出来的不是重跑它，而是换一台**由结构而非距离**配对的装置 —— 与 §7 第 6 条
「负向断言要读完全部字段」同族：**用自己的输出当自己的证据，等于没有证据**。

台账侧同批四笔：① `BET-Y2Q4-T10-236` 由 `python3 bin/gac/ledger-safe-insert.py --file <entry>` 插入
（dry-run 先行，插入点 41056 = bets 序列末、`campaigns:` 之前；`bets now 532`），条目 `status: pending`
+ `completion_evidence.overall_state: evaluating`（该工具对**任何**插入条目都无条件要求三轴与
`overall_state`，与 `status` 无关 —— 先前只见过 `done` 条目带它，这次是被 lint 教出来的）；
② `BET-Y2Q4-T10-237`（§7.1 那条 host 面）同装置插入于 41151，`bets now 533`，
`human_gate: true`（判哪一侧是真值要 panorama/dashboard 线的署名裁定，不是我能替别人定的）；
③ 本 receipt 与 retro 的 `sha256` 各 4 处 / 2 处已重算写入；
④ `write_surfaces` 未再改动；
⑤ ③ 的那次重算**用错了装置**（见订正表第 7 条），已按子映射配对重导全部 11 条绑定摘要
（含 T10-237 spec 那条新绑定），两台装置读数一致 `refs=11 stale=0`，`bet-ledger.py lint`
仍报 **533 bets no errors**。

⚠️ 该工具还教出第二条：`accepted_specifications` **必须恰好一条且文件按摘要存在**
（`bin/gac/ledger-safe-insert.py:77-98`：`SPEC_FILE_MISSING` / `SPEC_DIGEST_MISMATCH`）。
所以「先登记一条发现、之后再补 spec」这个形状**在插入这一步就走不通** —— T10-237 的 spec
`docs/superpowers/specs/2026-10-07-launchd-label-collapsed-to-inner-step.md` 是先写后插的，
这是好事（判据在被登记的那一刻就已经是可跑的），不是仪式。

⚠️ **摘要重算是有意的人工行为，装置不会再替我校**：`bet_status == "done"` 之后
`_validate_evidence_reference()` 跳过 sha 校验（`bin/plan/bet-ledger.py`），所以「evidence 里的摘要与文件
不一致」这件事**没有任何检查会红**。复算命令（改完这两份文件必跑）：

```bash
shasum -a 256 docs/reports/2026-10-07-system-yaml-materializer-closeout.md \
              .omo/_knowledge/retros/BET-Y2Q4-T10-235.md
```

本笔交付落盘后的读数与台账 `completion_evidence` 一致（两份各 4 / 2 处引用）。

### 7.1 复跑门禁时新增的一条 hard fail —— 归类为 host 面，不是本笔交付引入

`make gac-local-gate` 在本轮早些时候是 `PASS（68 checks, 2 SOFT WARN）`，复跑变成
`FAIL | 2 SOFT WARN`（rc=1）。唯一的 hard fail 是 `service-config-drift`
（`bin/mof/gen-service-configs.py --check`，`drift_count=1`）。三条实测把它定性成与 §4.1 同类、
且**不由本笔交付引入**：

1. **CI 不执行它**：该检查在 `bin/gac/gac-local-gate.py:198-205` 带 `ci_skip: True`，
   属于 §4.1 已量出的 7 条「本机 strict 才有」的面 ⇒ 对 PR 的 CI 判定零影响。
2. **git 侧无漂移**：`git diff HEAD origin/main -- .omo/_truth/registry/services.yaml bin/mof/gen-service-configs.py`
   **空输出**（`git fetch origin main` 后实测）⇒ 不是我分支落后于 main 造成的。
3. **漂移的两边不是「字段不同」而是「不是同一个服务」**：注册表声明该 label
   （`com.omostation.zhixing-projection-fullrefresh`）跑
   `bin/panorama/projection-full-refresh.py`、`StartInterval 21600`、无 env；本机那份 plist
   （mtime `7 Oct 23:34`，即本轮两次门禁之间）跑
   `~/.local/opt/omostation-publisher/bin/panorama/panorama-collect.py --json`、`StartInterval 180`，
   并注入 `PANORAMA_ROOT` / `PANORAMA_CODE_ROOT` / `OMOSTATION_ROOT` / `OMOSTATION_STATE_ROOT`
   四者指向 publisher，`OMO_EVENT_LEDGER_DB` 回指 `Workspace/runtime/omo/event-ledger.sqlite3`，
   另带 `OMO_MANAGED_PYTHON` / `PYTHONDONTWRITEBYTECODE` 与 `WorkingDirectory`。
   对照装置（只读，不写 `~/Library/LaunchAgents`）：`gen_launchd_plist(svc)` 的内存产物与已安装文件
   `unified_diff` **63 行**，且**缩进指纹相反**（盘上 tab 缩进 40 行 / 4 空格 0 行，生成侧 tab 0 / 4 空格 15）
   ⇒ 盘上那份**不是这台装置的产物**。注册表 371 条里没有任何一条声明 `interval_sec` ∈ {180, 240}，
   唯一声明 `panorama-collect.py` 的 `omostation.panorama-dashboard-refresh` 是 `generate: false`
   且指向**另一个**路径（`~/.local/share/zhixing-dashboard/panorama-collect.py`）。
   `launchctl list` 侧该 label **PID 24697 正在跑**，`com.omostation.panorama-dashboard-refresh`
   PID 23373 同时在跑；相隔 3 分钟两次读 `~/.local/log/projection-fullrefresh.log`，
   `projection_revision` 从 `466002b9…` 变成 `fd1e3834…`，`out` 恒为同一份 `current-revision.json`
   ⇒ 不是「装了没跑」，是按 3 分钟节奏真实发布，且两条 label 写同一份产物。

⇒ 结论是**同一个 label 被本机侧改成了「driver 的第 3 步」并被提为服务本体**：
`projection-full-refresh.py::main()` 的 0) `flock` 防重入、1) remote 卫生校验、
2) `fetch + reset --hard origin/main + clean -fdx + 浅子模块对齐` 三步在调度路径上整体消失，
频率 6h → 3min（720 次/天）。env 里还固化了 `ZHIXING_DASHBOARD_CODE_ROOT` =
`~/.local/share/zhixing-dashboard-runtime-clean-20261008`（**带今天日期**；driver 计算的是
`str(DEPLOY_DIR)` = `~/.local/share/zhixing-dashboard`，`:111`）⇒ 一份每天在变的临时面被固化进机器级配置。
属 ADR-0456 的 launchd 现实面（与 G8「注册在案但从未安装」正好是镜像：这条是「装着、且与注册表说的
不是一回事」）。⚠️ 措辞订正：publisher 检出**不是未登记** —— 它就写在该 label 的 `notes` 里
（BET-Y2Q4-T10-227 原话「维护专用洁净检出 `~/.local/opt/omostation-publisher`…机器属主，不进 ws-* 卫生面」）
，也是 driver 的 `CHECKOUT` 默认值（env seam `OMOSTATION_PUBLISHER_CHECKOUT`）；缺的是它在
**ADR-0456 的根词汇**里没有位置（`install_root()` 只认 `~/.local/opt/omostation`，B4a）
⇒ 真实形状是「双根契约在机器级进程里被部分采用、部分绕过」，而不是「多出第三个根」。
本轮**不修**：判「哪一侧是真值」要问 panorama/dashboard 那条线的作者，改注册表等于替别人裁定，
重装 plist 是机器级写操作且落在 B4b 批次 2+ 的逐批授权面上。已登记为 **BET-Y2Q4-T10-237**（同批入台账），
判据与全部读数见 `docs/superpowers/specs/2026-10-07-launchd-label-collapsed-to-inner-step.md`。

## 8 PR #4686 撞车与干净室重放（2026-10-08）

首版交付推分支后 `gh pr view --json mergeable,mergeStateStatus` = **`CONFLICTING` / `DIRTY`**，
`gh pr checks` 报 "no checks reported" —— 这正是 §7④ 那条判据的第二次命中：**第一因是冲突，
不是 `on.paths` 过滤**，未解冲突的 PR 根本不排队。

冲突面只有一处、且性质明确：`git merge-tree --write-tree --name-only` 只点名
`docs/plans/3y-bet-ledger.yaml`。两侧都在 `bets` 序列**尾部追加** ——
`origin/main` 自我的 base 之后只前进了一笔台账提交 `06d6c6f81`（**补插 `BET-Y2Q4-T10-234`**，
`total_bets` 532），我这一笔追加 T10-236/T10-237（533）。**号不撞，位置撞**。

处置走的是**干净室重放**，不是 rebase：本仓 `pre-rebase` 钩子直接拒绝
（`❌ 拒绝 rebase onto origin/main / 应走 merge/PR 合流`，逃生口 `SWARM_ESCAPE_ID=rebase-<reason>`）。
逃生口是留给「结构上无别的通道」的场景，而这里 merge/PR 合流通道**存在**，
所以**没有**用逃生口、也没有 force-push。步骤与读数：

1. `gac-worktree.sh claim t10-235-followup` 起新 worktree（base = `origin/main` `09a459a97`）。
   ⚠️ claim 的浅 init 超时后回退完整 init 也失败（rc=143），脚本「拒绝 PASW claim」
   —— 但 worktree 与分支**已建成**（`git worktree list` 命中），照 §7 那条「claim 可能超时但实际已建成」
   补跑 `git submodule update --init` 对齐即可，**没有重复 claim**。
2. 五份新文档按**内容**取（`git show 42539bf66:<path>`），不是 cherry-pick ——
   cherry-pick 跨 base 会带 parent reverse（PITFALL-COO-005），而这次 base 恰好动了同一个尾部。
3. 台账的 T10-235 块替换**先自证**：脚本比对 `origin/main` 与该块在**我 base 上**的字节，
   相等才替换（`T10-235 block: main == base? True`，9,444 → 11,063 字符）。
   这一步是为了排除「我覆盖掉别人对同一笔的改动」——按块替换在没有这个前置检查时是**静默**的。
4. T10-236/T10-237 用**同一个装置** `ledger-safe-insert.py` 在新 base 上重插（dry-run 先行 →
   插入点 41170），读数 `bets now 533` → `bets now 534`。
   本 receipt §7 里「bets 533」是**旧 base 当时的读数**，合并后的权威读数是 **534**，在此订正而不改史。

一条顺带的观察，写下来免得下一轮又撞：`origin/main` 最新提交 `09a459a97`（PR #4685）标题带
「**(BET-Y2Q4-T10-236 scope)**」，而 `git show origin/main:docs/plans/3y-bet-ledger.yaml` 里
**没有** `BET-Y2Q4-T10-236` 这条（`rg -c` = 0），`git grep -l "BET-Y2Q4-T10-236" origin/main`
也**零命中** —— 那个号只在 commit message 里被使用，台账（SSOT）里没有。
⇒ 判据：**撞号只看台账与绑定对象，不看提交标题**。本笔按台账取 236/237；若 #4685 那条线随后正式登记，
它会撞到已存在的 id 而由**后登记者**改铸（与本仓「234 撞号已改铸」同一条规则的对称面）。

## 9 #4671 自己带出去的两个缺陷，和第三个「CI 看不见」（2026-10-08 收尾轮）

§8 的重放不是白跑的：在新 base 上跑 `tests/unit/` 全量时暴露了两件**合并那天就带出去**的事，
两者的共同形状是「**判据所在的平面 ≠ 交付所在的平面**」。

**① 两个脚本在 main 上每次调用都 `ModuleNotFoundError`。** #4671 给 `bin/gac/` 下这两个读者
接了 `from repo_root import state_file_read`，`sys.path` 那行照 `bin/` 顶层脚本的拼法写成
`parents[2]` —— 而 `bin/gac/x.py` 的 `parents[2]` 是**仓库根**，仓库根下又真有一个 `lib/`
（另一批 helper，被跟踪）：目录存在、模块不在里面，于是 `is_dir()` 类检查全过、执行全崩。
实测修复前 / 后（同一命令，`--help`）：

| 脚本 | 修复前 | 修复后 |
|---|---|---|
| `bin/gac/m1-closeout-report.py` | rc=1 `ModuleNotFoundError: repo_root` | rc=0 |
| `bin/gac/session-recovery.py` | rc=1 同上 | rc=0 |

**② 五个用例继承了一份已经不存在的检出前提。** #4671 把 `.omo/state/system.yaml` 摘库
（`.gitignore:297`）后，`tests/unit/test_system_yaml_write_plane.py` 里 **10 处**
`CHECKOUT_SNAPSHOT.read_bytes()`（AST 归属：5 个用例各 2 处 —— 前后各读一次字节再比对），
外加 `test_state_file_read_never_hijacks_a_foreign_checkout` 那句
`assert (ROOT / STATE_REL).is_file()`，一共**六处**默认「检出侧那份在」——
实测 10 个用例红在 `FileNotFoundError`。处置**不是**把断言删窄，而是让用例**自己物化**前提
（`_materialize_checkout_copy()`），并把「没被碰过」表达成**缺席即保持缺席**
（`_checkout_state() -> bytes | None`，10 处读字节全换）。修后 25 passed。

**③ 第三个平面：CI 从来没看过 `tests/unit/`。** `.github/workflows/governance-check.yml` 的
显式白名单（`interface-check` step 5，`09a459a97`/PR #4685 刚加的那段）**只点名 root `tests/`**，
唯一跑到 ①那两个脚本的用例 `tests/test_m1_closeout_report.py` 不在名单里 ——
所以「CI 绿」对这类交付**结构性不构成证据**（与 §7 里 `:118-127` 那条同一事实）。

固化 = 新增类守卫 `tests/unit/test_bin_syspath_resolution.py` + 把**两件**点名进白名单
（`../../tests/unit/test_bin_syspath_resolution.py`、`../../tests/unit/test_system_yaml_write_plane.py`）。
守卫的实测读数与牙齿：

- 扫描面**不收窄**：`rglob("*.py")` 在完整检出里 descend 进 `.git`/`node_modules`/`.venv`，
  数出 **151,970** 个文件、5.4 s；改剪枝遍历后同一仓 **1,552** 个文件、0.06 s ⇒ 代价不是收窄的理由。
- 站点普查（本机检出）：**36 处** = 25 `ok` + 11 `unresolvable-here` + **0 `arith-bug`**；
  11 处未定全部是子模块未 init 那类（`projects/omo/src` 在本 worktree 里根本不存在，
  `ls projects/omo` 空），判据把「环境」与「算错」分开：**某个别的 K 可达而当前 K 不可达**才算错。
- detector 自证三轮才立住（每条都是**假绿**，写下来是因为形状各异）：
  `is_dir()` 谓词（目录存在即通过，正是 ① 的失效面）、AST 装置（`checked=0`）、
  exec 前缀 hack（`broken=0`，且 `MUTATION-PROOF: FAIL` —— 谓词只认 `ModuleNotFoundError`，
  对 `IndexError` 视而不见）。最终形状是**执行装置 + 变异对照**：
  重放 ① 的 `parents[2]` ⇒ 当场 2 红（`..._at_every_site` 与 `..._are_invocable`），还原 ⇒ 7 全绿。
- 两条写法级自证：`test_detector_covers_both_join_shapes`（`/"a"` 与 `/"a"/"b"` 都要命中 ——
  旧正则只认单段，多段形状下的算错会**伪装成"没有站点"**）；
  `test_relative_import_sites_are_not_judged`（`from .x import` 不经 `sys.path`，
  拿它当消费方会既漏又假报：3 处 domain-cartridge 被空名判成 bug）。
- 白名单口径核验：`bash -n` 该 step 的 run 体 rc=0；`yaml.safe_load` 后确认两件在
  `interface-check` step 5；两件在该 step 的解释器下 **7 + 25 passed**。

顺带两条本机陷阱在本轮**再次**命中（§7⑤ 的复发，不是新债）：zsh 别名 `cp → cp -iv` 让
「还原变异」那一步打印 `overwrite …? not overwritten` 后 rc=1 且**文件逐字节未变**，
变异体因此还留在盘上——改用 Python `write_bytes` 还原并 `sha` 复核；`grep -n "A|B"` 走的是
`rg`，返回空不等于没有。
