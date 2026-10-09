---
schema: md/v1
status: completed
lifecycle: report
owner: governance-team
last-reviewed: 2026-10-09
type: closeout-receipt
bet_id: BET-Y2Q4-T10-238
title: BET-Y2Q4-T10-238 closeout receipt — evidence-freshness 读侧根分裂与「生成即豁免分数」
---

# BET-Y2Q4-T10-238 closeout receipt

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-238`
契约：`docs/superpowers/specs/2026-10-09-evidence-freshness-reader-plane.md`（spec_version 1.1.0）
机器可读读数：`docs/reports/2026-10-09-bet-238-canary.json`
Retro：`.omo/_knowledge/retros/BET-Y2Q4-T10-238.md`

## 1 交付

| 面 | 位置 |
|---|---|
| 读侧根改按 profile 在调用时刻解析 | `bin/gac/check-evidence-freshness.py` |
| 用例（10 条，含变异对照与检测器自证） | `tests/unit/test_evidence_freshness_reader_plane.py` |
| 把 `tests/unit/**` 平面接进 CI | `.github/workflows/governance-check.yml`（`interface-check` job 的 pytest argv） |
| 机器可读判据读数 | `docs/reports/2026-10-09-bet-238-canary.json` |
| 台账注册与 evidence 回填 | `docs/plans/3y-bet-ledger.yaml` |

- 主交付：**PR #4689** → squash 合并为 `08c177b2c37955b69ea0798be676d54e973f9484`。
  CI 终态 29 pass / 2 skipping（`Documents domain projects`、`doc-freshness` 由 `on.paths` 过滤，非本轮写面），
  `mergeable=MERGEABLE`、`mergeStateStatus=CLEAN`。
- 追加交付（ISC-6，见 §3）与本轮 receipt/retro/ledger 同 PR 走 lane-pure commit：
  **PR #4690** → squash 合并为 `10fc057220d46fa7092d3783e8b78c26bb600b10`（7 commits），
  23 条检查逐条 conclusion 全 `SUCCESS`、两条 `skipping` 属 `on.paths` 过滤，
  `mergeable=MERGEABLE`、`mergeStateStatus=CLEAN`；push 前 L3 深度审查 0 findings（见 §7）。读数见 §2.2 与 canary `post_merge_pin_and_ci`。
- 合并后回查发现台账 `merged_reachable_commit` 绑在 `08c177b2c`（不含终态），已改绑 `10fc05722` —— 见 §6。
- 台账 done 翻转由机制本身放行，不是手写：`python3 bin/plan/bet-ledger.py complete BET-Y2Q4-T10-238`
  实跑 **RC=0**（spec binding digest 校验 + evidence matrix 派生 `delivery_accepted` +
  7 条 `write_surfaces` 全部入库的 D0 守卫 + vision→retro 链闭合），它写出的只有
  `status: done` 与 `done_at: 2026-10-09` 两行。

## 2 判据逐项读数（2026-10-09 实测，装置见 canary 的 `measurement_device`）

| 判据 | 读数 | 结论 |
|---|---|---|
| 判据-1 正向落点 | state 根独物化 8 天前报告 ⇒ `rc=1 ok=false age_days=8 violations=[stale_report]`，`report_path` 指向那棵树 | PASS（不再是硬写的 0） |
| 判据-2 生成不豁免分数 | 空根 + 生成 42 分（与陈旧叠加）⇒ `rc=1 violations=[stale_report, low_score] score=42.0` | PASS |
| 判据-3 分裂可见 | 生成 rc=0 且返回合法 JSON、读路径无产物 ⇒ `violations=[evidence_unreadable] ok=false` | PASS（用例 `test_split_becomes_visible_instead_of_tolerated`，同一注入下改造前副本 `rc=0 ok=true`） |
| 判据-4 未声明 profile 等于历史 | `evidence_dir == <checkout>/.omo/_delivery/evidence-smoke` ⇒ `equals_checkout_path=true`，`rc=0 ok=true score=100.0 age_days=0` | PASS |
| 判据-5 用例全绿 | `python3 -m pytest tests/unit/test_evidence_freshness_reader_plane.py -q -p no:randomly` ⇒ `10 passed in 0.12s` | PASS |
| 判据-6 检测器自证 | `test_import_time_checkout_anchor_is_gone_and_detector_is_not_a_no_op`：当前源码 import 期 `__file__` 赋值 = `[]`，冻结副本命中 `WORKSPACE` | PASS（非空绿） |
| 判据-7 CI 点名 | `/usr/bin/grep -n` 命中 `governance-check.yml:128`（注释）与 `:153`（argv），落在 `interface-check` job | PASS |
| 判据-8 阈值未放宽 | `d56ff1540` 与 `08c177b2c` 两侧 `MAX_AGE = timedelta(days=7)` / `MIN_SCORE = 90.0` 逐字符相同；`git diff -U0` 中触碰常量行的 hunk = `[]` | PASS |
| 判据-9 门禁不瞎、不带生成态 | 见 §4 | 分类后 PASS（带一条与本 BET 无关的预存机器面红） |

CI 侧的独立证据：`interface-check` 日志 `320 passed, 9 skipped in 126.13s`。
`-q` 不打印用例名，所以「我的 9 条在不在 320 里」用差分证：把 CI 的那串 argv 原样交给 pytest
`--collect-only -q`，含该文件 **217 collected**、摘掉该文件 **208 collected**，差值恰为 9。

### 2.1 在最终树上重跑（2026-10-09T02:31:11Z，5 个 commit 全在枝上）

判据不留在「合并前那一版树上」，同装置重跑一遍，逐条复现（原始读数进 canary `final_branch_readings`）：

| 支路 | 读数 |
|---|---|
| 未声明 profile | `rc=0 ok=true score=100.0 age_days=0`，`evidence_dir` 以检出根开头 ⇒ `equals_checkout_path=true` |
| 空 state 根，跑到生成支路 | `rc=0 ok=true age_days=0`，产物落在注入的那棵树里 |
| 同根第二遍（走读支路） | `rc=0 ok=true age_days=0` |
| 把报告 `os.utime` 成 8 天前 | `rc=1 ok=false age_days=8 violations=[stale_report]` |
| 再写低分数（与陈旧叠加） | `rc=1 ok=false score=42.0 age_days=8 violations=[stale_report, low_score]` |
| 用例 | `10 passed`（本轮重跑 02:30:30Z；表中 0.12s 是首次读数） |

**这次重跑自己贡献了一条装置误差**：第一次复测把分数写成 `"score": 42.0`，low_score **没命中**、
读数仍是 `score=100.0`。读支路取的是 `evidence_health_score`（`bin/gac/check-evidence-freshness.py:55`），
不是 `score`。按源码修正注入键后才有上面那行。教训与判据-8 那条同源：**两次读数不同，先疑装置**——
差别在于这次是装置**少**报了一个违规，若直接采信会得到「生成支路只比龄不比分」的假结论。

### 2.2 合并侧的 CI 读数（PR #4690，2026-10-09T03:00Z）

分支 push 后 23 条检查逐条 conclusion 全 `SUCCESS`（两条 `skipping` 是 `on.paths` 过滤，不是失败），
`mergeable=MERGEABLE`、`mergeStateStatus=CLEAN`，squash 合并为 `10fc05722`，无 admin merge、无 `--no-verify`。

`interface-check` 的读数从 #4689 的 `320 passed` 变成 **`321 passed, 9 skipped in 121.31s`**。
这条差分正是「CI 跑了我的用例」的正面证据：本分支相对 #4689 只新增 1 条用例（钉时钟的那条），
`320 + 1 = 321`，且 argv 里逐字点名 `../../tests/unit/test_evidence_freshness_reader_plane.py`，
工作树该文件 `grep -c "^def test_"` = 10。`-q` 不打印用例名，所以**计数差分**是唯一不靠肉眼读日志的手段。

⚠️ 取这条读数时又撞了 AGENTS.md §7⑤ 那个别名坑：Bash 工具里 `grep -E` 命中的是 `rg`，报
`unknown encoding`；改 `/usr/bin/grep` 与 python 剥 ANSI 后才拿到那行 summary。

## 3 ISC-6：负龄读数（合并后重测才暴露的一条）

第一次 profile 实测（prod 根无报告）得到 **`age_days: -1`**。
根因与本轮主题同源：`main()` 在**运行开始**拍 `now`，生成支路里 `evidence-smoke` 在此之后落盘，
`(now - mtime).days` 对负的 `timedelta` **向下取整** ⇒ `-1`。

改造前的冻结副本在这条支路硬写 `age_days = 0`，所以这个形状**不可能由变异对照发现**，
只有「如实测量」之后才现形 —— 这也是本轮把读数写进 receipt 而不是只写「用例全绿」的理由。

修法：时钟移到**读取时刻**（`_read_report(report_path, datetime.now(UTC))`），删掉 `main()` 开头的快照。
判据不缩：`age_days == -1` 的初始哨兵仍表示「没测到」，生成失败时不变。
钉住它的用例 `test_generated_report_age_is_measured_at_read_time`；
修后同一注入 ⇒ `age_days=0`，且第二遍走读支路 `age_days=0`、8 天陈旧注入仍 `age_days=8 → rc=1`。

**台账 `done_when` 的措辞为什么不跟着改**：判据-5 写的是「含 ISC-1..ISC-5」，现实际覆盖到 ISC-6。
`done_when` / `verify` 是 WorkPacket 投影字段，claim 之后再改，后续 claim 会报
`WORK_PACKET_SOURCE_DRIFT`（`bin/plan/bet-ledger.py:2336`）；而 `refresh-packet`
（`bin/agent-workflow.py:1031`）要求 ledger+spec **已在 `origin/main`**，所以本分支内没有合法的改法。
ISC-6 的约束力由 spec `1.1.0` + 重算的 `content_digest` 承载（台账 `accepted_specifications` 已指向它），
措辞订正在本轮合并后的下一轮用 `refresh-packet` 落。

## 4 门禁读数与两条红的归属

`uv run --with pyyaml python bin/gac/gac-local-gate.py --scope files --file <7 个 branch delta 文件> --json`
（2026-10-09T02:29:49Z 在本分支重跑，原始 JSON 的摘要逐字段进 canary `gate_scoped`）：`checks=68`，`ok=false`，
门禁自己给出的 `hard_fails = ['change-lane-check', 'service-config-drift']`，`soft_warns` 2 条
（`test-mcp-kos` rc=78 skipped、`current-state-coherence` rc=2）。

- `change-lane-check`：**测量装置的面，不是回归**。`--scope files` 把 5 个 lane 的文件并成一次检查
  （`code,docs,docs_data,governance_code,governance_state` 不在 `ALLOWED_COMBOS`）。同一并集读法跑在**已合并**的 `bbcb4e279…`（25 文件）
  与 `d56ff1540`（11 文件）上同样 FAIL mixed lanes ⇒ 与该 commit 内容无关。
  真实执行面是 pre-commit 的 `--staged` **逐 commit** 检查。本轮交付 commit 逐条实测
  （`python3 bin/change-lane-check.py --file <该 commit 的文件>`，2026-10-09T02:30:12Z，全部 `rc=0`）：

  | commit | 文件数 | 门禁首行读数 |
  |---|---|---|
  | `2cf72d97a` | 1 | `PASS (1 files, lanes=governance_code)` |
  | `26576e75d` | 1 | `PASS (1 files, lanes=code)` |
  | `9e0d92a2b` | 4 | `PASS (4 files, lanes=docs,docs_data)` |
  | `c6d1f5691` | 1 | `PASS (1 files, lanes=governance_state)` |
  | `608dd5fe2` | 1 | `PASS (1 files, lanes=docs_data)` |

  这 5 条之后还有两笔收尾 commit，都落在他自己的执行面上：`d9abbb336`（retro 补两条装置侧教训，
  单文件 `governance_state`）与本次纯文档修订（canary 读数补全 + 本节措辞 + 台账 8 处 digest 重绑，
  `docs` + `docs_data`）。它们各自的存在即是 pre-commit `--staged` 放行过的证据，不需要另造装置。
  pre-push 不调用它，也没有任何调用方传 `--allow-lane`。
- `service-config-drift`：`com.omostation.zhixing-projection-fullrefresh` 的 plist 与 `services.yaml` 不一致。
  在主工作区用稳定解释器复现同样读数，且**不在**本 BET 的任何写面上 ⇒ 机器面预存债。
  修法是重装 plist（`bin/mof/gen-service-configs.py --write`），属授权门操作，本轮**没有**执行，
  也**没有**为了让门禁好看而改窄任何判据。已在 PR #4689 body 内向夏明星报出。
- `current-state-coherence` 这条 **not-ok 但不进 hard_fails**，本轮实测它为什么 not-ok：
  报 `missing input: <checkout>/.omo/state/system.yaml`。对照量 —— 把 `origin/main` 用 `git archive`
  导到干净临时树再跑同一脚本，**同样 rc=2 同样缺输入**，且 `git ls-files --error-unmatch .omo/state/system.yaml`
  在 `origin/main` 上返回 1（T10-235 已把它摘库）。所以这是「检出里没有那份生成态」的环境面，
  不是本分支引入的回归；把它写进 receipt 是因为「不在 hard_fails 里」不等于「看过」。

本 BET 自己那条检查在门禁里是绿的：`check-evidence-freshness: PASS (score=100.0, age=0d)`，
同批 `check-evidence-honest-closure` 亦 ok。

## 5 本次复核与收口边界（2026-10-09 02:20 UTC）

- 在交付工作树复核本 Run 的唯一未提交文件并执行 `agent-workflow verify <run-id> --from-diff --execute`：文档 SSOT 与 doc claims 检查通过；`make gac-local-gate` 未通过。
- 同一时点在当前主 Workspace 重跑 `make gac-local-gate`，结果仍为 FAIL：唯一硬失败是 `service-config-drift`（`com.omostation.zhixing-projection-fullrefresh` 的已安装 plist 与当前 `services.yaml` 不一致）；治理语义检查另提示 16 个历史/活动 Run、治理演进包有 2 个 unknown。其余列出的本地检查通过，`current-state-coherence` 在主 Workspace 通过。
- 交付 worktree 的门禁还报告 `.omo/state/system.yaml` 缺失；该隐藏运行态在此 worktree 没有物化。没有复制或伪造这类状态文件，也没有执行 plist 重装、LaunchAgent reload、工作树同步或清理来掩盖门禁结果。
- 因实现已由 PR #4689 合并，但正式 closeout 的 required `gac-local-gate` 尚未 PASS，本次 Run 只按 `blocked` 记录并释放原锁；这不改变代码 PR 已合并的事实，也不把门禁判作通过。后续应在带齐权威运行态、消除 service-config drift 的新鲜工作树中重跑完整门禁，再单独裁决该门是否可关闭。

## 6 合并后回查：`merged_reachable_commit` 指向的树不含终态

合并 `10fc05722` 之后回查台账 `engineering.merged_reachable_commit`，它绑的是 `08c177b2c`。逐棵树实测（装置：`git show <sha>:<path>`，不信工作树）：

| 绑定 | `check-evidence-freshness.py` 调用点 | 用例数 | 在 main 上可达 | 含本轮终态 |
|---|---|---|---|---|
| 改前 `08c177b2c` | `_read_report(report_path, now)` | 9 | 是 | **否** |
| 改后 `10fc05722` | `_read_report(report_path, datetime.now(UTC))` | 10 | 是 | 是 |

`bet-ledger.py` 对这一字段只校验 **reachability**（`bin/plan/bet-ledger.py:1682`），所以「指针指向更早的那次合并」
在它自己身上永远绿 —— 可达不等于含我担保的改动。这正是本 BET 的主题（证据必须描述它担保的那棵树）
落到台账侧的一次自身实例，retro 记为第 9 条教训。改绑与 8 处 digest 的重绑在同一批交付里做，fixpoint 用
`chain_bind.evaluate_complete` + `bet-ledger.py verify` 复判。

## 7 安全与清理

- 推送前 L3 deep security review 覆盖 **PR #4689 的 3 个 commit：0 findings**。
  本轮二次交付（ISC-6 + 收尾文档）的 L3 复核读数仍须以独立验证证据为准；本报告不以先前 PR 的安全审查替代本轮审查。
- **该句已在 #4690 push 前闭合**：用户授权后对收尾分支全部 **7 个 commit** 跑 L3 深度审查，
  `findings_count: 0`，无发现项因此无修复门；随后才 push、开 PR、squash 合并。读数进 canary
  `post_merge_pin_and_ci.l3_security_review`。
- 生成态未随本轮走：`git status --short` 交付前后为空；`.omo/state/**`、`.omo/_delivery/**`、
  `BRIEF.md`、子模块 gitlink 一条未入 commit。
- affected-graph receipt 落 `runtime/affected/`（真实目录、非 symlink），用毕删除，未提交。

## 7 rollback

单条反向即可，读侧与被它替换的历史行为等价：

1. `git revert -n 08c177b2c` 生成反向 diff（或把 `bin/gac/check-evidence-freshness.py` 恢复为
   `git show d56ff1540:bin/gac/check-evidence-freshness.py`）。
2. 同批撤 `interface-check` argv 里那一行与注释行，撤 `tests/unit/test_evidence_freshness_reader_plane.py`。
3. 台账条目 `BET-Y2Q4-T10-238` 回 `status: pending`、清空 `completion_evidence`。
4. 回退后判据-4 自动成立（读侧回到检出根），但「声明 profile 每跑必绿」的洞会重新打开 ——
   回退是止血，不是修复。
