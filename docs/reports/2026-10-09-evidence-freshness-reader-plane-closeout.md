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
| 台账注册与 evidence 回填 | `docs/plans/3y-bet-ledger.yaml` |

- 主交付：**PR #4689** → squash 合并为 `08c177b2c37955b69ea0798be676d54e973f9484`。
  CI 终态 29 pass / 2 skipping（`Documents domain projects`、`doc-freshness` 由 `on.paths` 过滤，非本轮写面），
  `mergeable=MERGEABLE`、`mergeStateStatus=CLEAN`。
- 追加交付（ISC-6，见 §3）与本轮 receipt/retro/ledger 同 PR 走 lane-pure commit。

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

`uv run --with pyyaml python bin/gac/gac-local-gate.py --scope files --file <checker> --file <test> --json`：
`checks=68`，`ok=false`，hard_fails = `['change-lane-check', 'service-config-drift']`。

- `change-lane-check`：**测量装置的面，不是回归**。`--scope files` 把两个 lane 的文件并成一次检查
  （`code` + `governance_code` 不在 `ALLOWED_COMBOS`）。同一并集读法跑在**已合并**的 `bbcb4e279…`（25 文件）
  与 `d56ff1540`（11 文件）上同样 FAIL mixed lanes ⇒ 与该 commit 内容无关。
  真实执行面是 pre-commit 的 `--staged` **逐 commit** 检查：本轮四个 commit 各自 lane-pure，
  逐条 `change-lane-check --staged` 预验 PASS。pre-push 不调用它，也没有任何调用方传 `--allow-lane`。
- `service-config-drift`：`com.omostation.zhixing-projection-fullrefresh` 的 plist 与 `services.yaml` 不一致。
  在主工作区用稳定解释器复现同样读数，且**不在**本 BET 的任何写面上 ⇒ 机器面预存债。
  修法是重装 plist（`bin/mof/gen-service-configs.py --write`），属授权门操作，本轮**没有**执行，
  也**没有**为了让门禁好看而改窄任何判据。已在 PR #4689 body 内向夏明星报出。

本 BET 自己那条检查在门禁里是绿的：`check-evidence-freshness: PASS (score=100.0, age=0d)`。

## 5 安全与清理

- 推送前 L3 deep security review 覆盖 3 个 commit：**0 findings**（追加的 ISC-6 commit 单独再走一次门禁）。
- 生成态未随本轮走：`git status --short` 交付前后为空；`.omo/state/**`、`.omo/_delivery/**`、
  `BRIEF.md`、子模块 gitlink 一条未入 commit。
- affected-graph receipt 落 `runtime/affected/`（真实目录、非 symlink），用毕删除，未提交。

## 6 rollback

单条反向即可，读侧与被它替换的历史行为等价：

1. `git revert -n 08c177b2c` 生成反向 diff（或把 `bin/gac/check-evidence-freshness.py` 恢复为
   `git show d56ff1540:bin/gac/check-evidence-freshness.py`）。
2. 同批撤 `interface-check` argv 里那一行与注释行，撤 `tests/unit/test_evidence_freshness_reader_plane.py`。
3. 台账条目 `BET-Y2Q4-T10-238` 回 `status: pending`、清空 `completion_evidence`。
4. 回退后判据-4 自动成立（读侧回到检出根），但「声明 profile 每跑必绿」的洞会重新打开 ——
   回退是止血，不是修复。
